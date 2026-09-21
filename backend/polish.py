"""润色分枝：POST /api/polish（施工图节点 3）。

把"气话"润色成温柔基调的高情商版本。防生硬的关键设计：
先理解情绪（可结合分析结果/背景），再动笔润色；
用户没指定语气时由 AI 自动判断组合；支持多轮微调。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import config, glm_client, prompts, safety, storage

router = APIRouter(prefix="/api", tags=["润色"])


class PolishRequest(BaseModel):
    """润色接口的请求参数。"""

    text: str = Field(..., description="要润色的原话")
    background: str | None = Field(default=None, description="可选背景：这是在什么情况下发生的")
    tone: str | None = Field(default=None, description="可选：预设 key 或自然语言描述（如'温柔但坚定'）")
    feedback: str | None = Field(default=None, description="可选：多轮微调时，用户对上一版的意见")
    previous: str | None = Field(default=None, description="可选：多轮微调时，上一版的润色结果")
    record_id: int | None = Field(default=None, description="可选：分析记录 id，传入则润色结果合并进该记录")


class PolishResponse(BaseModel):
    """润色接口的返回结果。"""

    versions: list[dict] = Field(..., description="2~3 个润色版本，每个含 tone（语气）和 text（润色后的话）")
    auto_tone: bool = Field(..., description="语气是否由 AI 自动判断组合")
    record_id: int = Field(..., description="本次润色保存到的记录 id")
    demo: bool = Field(..., description="是否演示数据")


# 演示模式的示例润色版本（内容原创虚构，决策 88）
DEMO_VERSIONS = [
    {
        "tone": "温柔但坚定",
        "text": "我很在乎我们能不能好好吃顿饭。最近你总晚归，我心里有点失落，也有点担心。我们能不能聊聊，怎么安排对两个人都好？",
    },
    {
        "tone": "幽默化解",
        "text": "报告家属，你点的'回家吃饭'订单已超时多次，本厨房准备给你最后一次五星好评的机会，今晚约吗？",
    },
    {
        "tone": "简洁直接",
        "text": "我希望你能早点回家吃饭，这对我很重要。我们今晚谈谈？",
    },
]


def _build_user_message(req: PolishRequest, analysis: dict | None) -> str:
    """组装发给 AI 的用户消息：原话 + 可选背景/分析/语气/微调意见。"""
    parts = [f"【要润色的原话】\n{req.text}"]
    if req.background:
        parts.append(f"【背景】\n{req.background}")
    if analysis:
        emotions = "、".join(f"{e['name']}占{e['percent']}%" for e in analysis.get("emotions", []))
        parts.append(f"【情绪分析结果】\n情绪：{emotions}\n解读：{analysis.get('my_analysis', '')}")
    if req.tone:
        # 预设 key 转成具体描述；自然语言描述则原样传给 AI
        parts.append(f"【用户指定的语气】\n{prompts.TONE_PRESETS.get(req.tone, req.tone)}")
    if req.previous and req.feedback:
        parts.append(f"【上一版润色结果】\n{req.previous}\n【用户的意见】\n{req.feedback}\n请按意见重新润色，语气上要有明显变化。")
    return "\n\n".join(parts)


def _save_polish(req: PolishRequest, versions: list[dict]) -> int:
    """保存润色结果：有 record_id 且记录存在就合并，否则新建一条记录。"""
    polish_data = {"versions": versions, "auto_tone": req.tone is None}
    if req.record_id is not None and storage.get_record(req.record_id) is not None:
        storage.update_record_json(req.record_id, "polish_json", polish_data)
        return req.record_id
    record_id = storage.save_record(original_text=req.text, background=req.background)
    storage.update_record_json(record_id, "polish_json", polish_data)
    return record_id


@router.post("/polish", response_model=PolishResponse)
def polish(req: PolishRequest) -> PolishResponse:
    """润色一段话，返回 2~3 个不同语气的版本。"""
    input_error = safety.check_input(req.text)
    if input_error:
        raise HTTPException(status_code=400, detail=input_error)

    auto_tone = req.tone is None

    if config.is_demo_mode():
        versions = DEMO_VERSIONS
        # 演示模式下也尊重用户选择：指定语气时只返回对应版本
        if req.tone:
            tone_name = prompts.TONE_PRESETS.get(req.tone, req.tone).split("：")[0]
            versions = [v for v in DEMO_VERSIONS if v["tone"] == tone_name] or DEMO_VERSIONS[:1]
        record_id = _save_polish(req, versions)
        return PolishResponse(versions=versions, auto_tone=auto_tone,
                              record_id=record_id, demo=True)

    # 真实模式：如果带了记录 id，把该记录的分析结果一并给 AI 参考
    analysis = None
    if req.record_id is not None:
        record = storage.get_record(req.record_id)
        if record:
            analysis = record.get("analysis")

    messages = [
        {"role": "system", "content": prompts.build_polish_prompt()},
        {"role": "user", "content": _build_user_message(req, analysis)},
    ]
    try:
        # 润色需要一点灵气，随机性比分析略高
        result = glm_client.chat_json(messages, model=config.MODEL_POLISH, temperature=0.8)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"我刚刚走神了，我们再试一次好吗？（{exc}）") from exc

    versions = [{"tone": v.get("tone", ""), "text": v.get("text", "")}
                for v in result.get("versions", []) if v.get("text")]
    if not versions:
        raise HTTPException(status_code=502, detail="我没有润色出满意的版本，我们换个说法再试一次好吗？")

    record_id = _save_polish(req, versions)
    return PolishResponse(versions=versions, auto_tone=auto_tone,
                          record_id=record_id, demo=False)
