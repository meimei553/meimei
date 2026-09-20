"""润色接口：POST /api/polish

把"气话"润色成高情商版本。防生硬的关键设计：
先理解情绪（可结合 /api/analyze 的分析结果），再动笔润色；
用户没指定语气时，由 AI 自动判断并组合 2~3 种语气；
支持多轮微调（"太正式了，要温柔但坚定"）。
"""
from fastapi import APIRouter, HTTPException

from backend import config, glm_client, prompts, storage
from backend.models import PolishRequest, PolishResponse, PolishVersion

router = APIRouter(prefix="/api", tags=["润色"])

# 演示模式下返回的示例数据
DEMO_VERSIONS = [
    {
        "tone": "温柔但坚定",
        "text": (
            "我很在乎我们能不能好好吃顿饭。最近你总晚归，"
            "我心里有点失落，也有点担心。我们能不能聊聊，"
            "怎么安排对两个人都好？"
        ),
    },
    {
        "tone": "幽默化解",
        "text": (
            "报告家属，你点的'回家吃饭'订单已超时多次，"
            "本厨房准备给你最后一次五星好评的机会，今晚约吗？"
        ),
    },
    {
        "tone": "简洁直接",
        "text": "我希望你能早点回家吃饭，这对我很重要。我们今晚谈谈？",
    },
]


def build_user_message(req: PolishRequest) -> str:
    """把请求参数组装成发给 AI 的用户消息。"""
    parts = [f"【要润色的原话】\n{req.text}"]

    if req.analysis_context:
        parts.append(f"【情绪分析结果】\n{req.analysis_context}")

    if req.tone:
        # 预设 key 转成具体描述；自然语言描述则原样传给 AI
        tone_desc = prompts.POLISH_TONES.get(req.tone, req.tone)
        parts.append(f"【用户指定的语气】\n{tone_desc}")

    if req.previous and req.feedback:
        parts.append(
            f"【上一版润色结果】\n{req.previous}\n"
            f"【用户的意见】\n{req.feedback}\n"
            "请按意见重新润色，语气上要有明显变化。"
        )

    return "\n\n".join(parts)


@router.post("/polish", response_model=PolishResponse)
def polish(req: PolishRequest) -> PolishResponse:
    """润色一段话，返回 2~3 个不同语气的版本。

    传入分析接口返回的 record_id，润色结果会合并到那条反思记录里；
    不传则自动新建一条记录。
    """
    auto_tone = req.tone is None

    if config.is_demo_mode():
        versions = DEMO_VERSIONS
        # 演示模式下也尊重用户的选择：指定语气时只返回对应版本
        if req.tone:
            tone_desc = prompts.POLISH_TONES.get(req.tone, req.tone)
            tone_name = tone_desc.split("：")[0]
            versions = [v for v in DEMO_VERSIONS if v["tone"] == tone_name] or DEMO_VERSIONS[:1]
        record_id = _save_polish(req, versions)
        return PolishResponse(
            versions=[PolishVersion(**v) for v in versions],
            auto_tone=auto_tone,
            record_id=record_id,
            demo=True,
        )

    messages = [
        {"role": "system", "content": prompts.build_polish_prompt()},
        {"role": "user", "content": build_user_message(req)},
    ]

    try:
        # 润色需要一点灵气，随机性比分析略高
        result = glm_client.chat_json(messages, model=config.MODEL_POLISH, temperature=0.8)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"调用 GLM 失败：{exc}") from exc

    versions = [
        PolishVersion(tone=v.get("tone", ""), text=v.get("text", ""))
        for v in result.get("versions", [])
        if v.get("text")
    ]
    if not versions:
        raise HTTPException(status_code=502, detail="AI 没有返回可用的润色结果，请重试")

    record_id = _save_polish(req, [v.model_dump() for v in versions])
    return PolishResponse(
        versions=versions, auto_tone=auto_tone, record_id=record_id, demo=False
    )


def _save_polish(req: PolishRequest, versions: list[dict]) -> int:
    """保存润色结果：有 record_id 就合并到已有记录，否则新建一条。"""
    polish_data = {"versions": versions, "auto_tone": req.tone is None}
    if req.record_id is not None and storage.attach_polish(req.record_id, polish_data):
        return req.record_id
    # 没有 record_id（或记录不存在）时新建一条记录
    return storage.save_record(original_text=req.text, polish=polish_data)
