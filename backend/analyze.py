"""分析分枝：POST /api/analyze —— 产品核心功能（施工图节点 1）。

流程：输入校验 → 危机识别 → 演示/真实分析 → 占比归一化 → 自动存记录。
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import config, glm_client, prompts, safety, storage

router = APIRouter(prefix="/api", tags=["情绪分析"])

# 库外词日志（情绪库自增长机制：AI 自创的词记录到文件，定期补进库）
# 用独立日志器，避免 SDK 的 HTTP 日志混入
_library_logger = logging.getLogger("meimei.library_out")
_library_handler = logging.FileHandler("library_out.log", encoding="utf-8")
_library_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
_library_logger.addHandler(_library_handler)
_library_logger.setLevel(logging.INFO)
_library_logger.propagate = False


class GuessInput(BaseModel):
    """用户的情绪猜想（创新点：先猜后揭示，可跳过）。"""

    emotion: str = Field(..., description="用户猜的最主要情绪")
    intensity: str = Field(..., description="用户猜的强度：轻微/明显/强烈/非常强烈")


class AnalyzeRequest(BaseModel):
    """分析接口的请求参数。"""

    text: str = Field(..., description="聊天记录或想说的话，自由粘贴")
    background: str | None = Field(default=None, description="可选背景：这是在什么情况下发生的")
    guess: GuessInput | None = Field(default=None, description="可选：用户的情绪猜想")


class AnalyzeResponse(BaseModel):
    """分析接口的返回结果（字段含义见 BLUEPRINT.md 节点 1）。"""

    crisis: bool = Field(..., description="是否命中危机信号（命中时只有 crisis_response）")
    crisis_response: str | None = None
    emotions: list[dict] = Field(default_factory=list, description="top 6~8 情绪：名称/占比/强度/人话/解释")
    my_analysis: str | None = None
    other_analysis: str | None = None
    key_sentences: list[dict] = Field(default_factory=list, description="最关键的 2~3 句原话及原因")
    comfort: str | None = None
    guiding_questions: list[str] = Field(default_factory=list)
    review_advice: str | None = None
    summary: str | None = None
    guess_comparison: str | None = None
    cooldown_needed: bool = Field(default=False, description="先降温标记：情绪激烈时引导与复盘延后")
    record_id: int | None = None
    demo: bool = Field(..., description="是否演示数据")
    notes: list[str] = Field(default_factory=list, description="固定声明文案（占比说明/波动提示等）")


# 演示模式的完整示例分析（内容原创虚构，决策 88）
DEMO_ANALYSIS = {
    "emotions": [
        {"name": "委屈", "percent": 35, "intensity": 78, "reason": "付出没被看见，攒了很久"},
        {"name": "在乎", "percent": 25, "intensity": 85, "reason": "话越冲，越说明把对方放在心上"},
        {"name": "愤怒", "percent": 15, "intensity": 60, "reason": "带刺的表达是情绪的出口"},
        {"name": "期待", "percent": 15, "intensity": 66, "reason": "希望对方改变、关系变好"},
        {"name": "焦虑", "percent": 10, "intensity": 50, "reason": "担心关系变远"},
    ],
    "my_analysis": "你说那句话的时候，心里其实攒了很多委屈——你一直在付出，却没被看见。那句听起来有点冲的话，更像是想被在乎的一次呼喊。",
    "other_analysis": "对方那句'随便你'，可能是不知道该怎么接住你的情绪选择了躲开，也可能是他自己也有点慌。与其猜，不如找个时机直接问问他。",
    "key_sentences": [
        {"sentence": "你到底还回不回家吃饭？", "note": "重点不在吃饭，在'你到底还'——攒了很久的失望"},
    ],
    "comfort": "先抱抱你。会生气、会委屈，恰恰说明你很在乎这段关系，这不是你的错。",
    "guiding_questions": ["当时你最希望对方做的，其实是什么？", "如果重来一次，你希望自己第一句话先说什么？"],
    "review_advice": "下次可以试试：先说出自己的感受，再提出具体的请求，比如'我这周很想和你一起吃顿饭'。",
    "summary": "一句带刺的话背后，是攒了很久的委屈和深深的在乎。",
    "guess_comparison": None,
    "cooldown_needed": False,
}


def _normalize_emotions(raw_emotions: list[dict]) -> list[dict]:
    """整理情绪列表：限 6~8 个、占比归一化（总和 100）、补强度人话。

    AI 给的占比加总可能不是 100，代码层归一化兜底（可行性评估的对策）。
    """
    emotions = raw_emotions[:8]
    total = sum(max(0, int(e.get("percent", 0))) for e in emotions) or 1
    library = set(prompts.all_emotions())
    result = []
    for e in emotions:
        name = e.get("name", "未知")
        # 库外词记录日志（库自增长机制：定期把高频库外词补进 prompts.py 情绪库）
        if name not in library:
            _library_logger.info("库外词：%s", name)
        intensity = max(0, min(100, int(e.get("intensity", 0))))
        result.append({
            "name": name,
            "percent": round(max(0, int(e.get("percent", 0))) * 100 / total),
            "intensity": intensity,
            "intensity_text": prompts.intensity_text(intensity),
            "reason": e.get("reason", ""),
        })
    return result


def _build_user_message(req: AnalyzeRequest) -> str:
    """组装发给 AI 的用户消息：内容 + 可选背景 + 可选猜想 + 用户称呼。"""
    parts = [f"【内容】\n{req.text}"]
    if req.background:
        parts.append(f"【背景】\n{req.background}")
    if req.guess:
        parts.append(f"【用户的情绪猜想】\n最主要情绪：{req.guess.emotion}；强度：{req.guess.intensity}")
    # 称呼系统：用户设置过称呼时，AI 用这个称呼回应（决策 13）
    nickname = storage.get_setting("user_nickname")
    if nickname:
        parts.append(f"【用户称呼】\n回应时请称呼用户为“{nickname}”")
    return "\n\n".join(parts)


def _crisis_response(req: AnalyzeRequest) -> AnalyzeResponse:
    """危机回应：中断常规分析，返回求助渠道与陪伴话术，并留存记录。"""
    record_id = storage.save_record(original_text=req.text, background=req.background)
    return AnalyzeResponse(crisis=True, crisis_response=prompts.CRISIS_RESPONSE,
                           record_id=record_id, demo=config.is_demo_mode())


def _save_analysis(req: AnalyzeRequest, analysis: dict) -> int:
    """自动保存记录（决策：全部自动保存），返回记录 id。"""
    record_id = storage.save_record(original_text=req.text, background=req.background)
    if req.guess:
        storage.update_record_json(record_id, "guess_json", req.guess.model_dump())
    storage.update_record_json(record_id, "analysis_json", analysis)
    return record_id


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """分析一段内容，返回情绪雷达图数据和温柔解读。"""
    # 防线 1：输入校验（空/超长/乱码，不花 AI 费用）
    input_error = safety.check_input(req.text)
    if input_error:
        raise HTTPException(status_code=400, detail=input_error)

    # 防线 0：危机关键词识别（命中则中断分析，走危机回应）
    if safety.check_crisis(req.text):
        return _crisis_response(req)

    if config.is_demo_mode():
        # 演示模式：返回内置示例；示例数据也过归一化，保证与真实结构一致
        demo_data = {**DEMO_ANALYSIS, "emotions": _normalize_emotions(DEMO_ANALYSIS["emotions"])}
        record_id = _save_analysis(req, demo_data)
        return AnalyzeResponse(crisis=False, record_id=record_id, demo=True,
                               notes=[prompts.COPY_PERCENT_NOTE, prompts.COPY_RESULT_DISCLAIMER],
                               **demo_data)

    # 真实模式：调用 GLM 分析
    messages = [
        {"role": "system", "content": prompts.build_analyze_prompt()},
        {"role": "user", "content": _build_user_message(req)},
    ]
    try:
        result = glm_client.chat_json(messages, model=config.MODEL_ANALYZE)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"我刚刚走神了，我们再试一次好吗？（{exc}）") from exc

    # AI 判断的隐晦危机信号（第二重保险）
    if result.get("crisis_detected"):
        return _crisis_response(req)

    analysis = {
        "emotions": _normalize_emotions(result.get("emotions", [])),
        "my_analysis": result.get("my_analysis", ""),
        "other_analysis": result.get("other_analysis"),
        "key_sentences": result.get("key_sentences", []),
        "comfort": result.get("comfort", ""),
        "guiding_questions": result.get("guiding_questions", []),
        "review_advice": result.get("review_advice", ""),
        "summary": result.get("summary", ""),
        "guess_comparison": result.get("guess_comparison"),
        "cooldown_needed": bool(result.get("cooldown_needed", False)),
    }
    record_id = _save_analysis(req, analysis)
    return AnalyzeResponse(crisis=False, record_id=record_id, demo=False,
                           notes=[prompts.COPY_PERCENT_NOTE, prompts.COPY_RESULT_DISCLAIMER],
                           **analysis)
