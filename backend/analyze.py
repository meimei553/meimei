"""情绪分析接口：POST /api/analyze

这是产品的核心功能：分析为主，对话为辅。
流程：用户粘贴内容 -> AI 打分（雷达图）+ 双向解读 + 安慰 + 引导式提问
"""
from fastapi import APIRouter, HTTPException

from backend import config, glm_client, prompts
from backend.models import AnalyzeRequest, AnalyzeResponse

router = APIRouter(prefix="/api", tags=["情绪分析"])

# 演示模式下返回的示例数据（没有 API Key 时也能看到完整的分析效果）
DEMO_RESULT = {
    "dimensions": {
        "攻击性": 65, "委屈": 85, "焦虑": 55, "厌恶": 30,
        "意外": 40, "期待": 70, "愉悦": 10, "在乎": 90,
    },
    "my_analysis": (
        "你说那句话的时候，心里其实攒了很多委屈——你一直在付出，"
        "却没被看见。那句听起来有点冲的话，更像是想被在乎的一次呼喊，"
        "而不是真的想指责对方。"
    ),
    "other_analysis": (
        "对方那句'随便你'，听起来冷淡，但更像是不知道该怎么接住你的情绪，"
        "选择了躲开。ta 可能也有点慌，怕自己说什么都是错。"
    ),
    "comfort": (
        "先抱抱你。会生气、会委屈，恰恰说明你很在乎这段关系，"
        "这不是你的错。情绪没有对错，它只是提醒你：有些需要没被满足。"
    ),
    "guiding_questions": [
        "当时你最希望对方做的，其实是什么？",
        "如果重来一次，你希望自己第一句话先说什么？",
        "这份委屈里，有没有一部分是很久以前就攒下的？",
    ],
    "summary": "一句带刺的话背后，是攒了很久的委屈和深深的在乎。",
}


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """分析一段聊天记录或气话，返回情绪雷达图分数和温柔解读。"""
    if config.is_demo_mode():
        # 演示模式：直接返回内置示例，不调用 GLM
        return AnalyzeResponse(**DEMO_RESULT, demo=True)

    # 组装发给 GLM 的消息：人设+分析要求 -> 用户内容
    user_content = req.text
    if req.scene:
        user_content = f"【场景：{req.scene}】\n{req.text}"
    messages = [
        {"role": "system", "content": prompts.ANALYZE_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        result = glm_client.chat_json(messages, model=config.MODEL_ANALYZE)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"调用 GLM 失败：{exc}") from exc

    # 只保留我们定义的 8 个维度，防止 AI 自由发挥多出字段
    dimensions = {
        dim: int(result.get("dimensions", {}).get(dim, 0))
        for dim in prompts.EMOTION_DIMENSIONS
    }

    return AnalyzeResponse(
        dimensions=dimensions,
        my_analysis=result.get("my_analysis", ""),
        other_analysis=result.get("other_analysis"),
        comfort=result.get("comfort", ""),
        guiding_questions=result.get("guiding_questions", []),
        summary=result.get("summary", ""),
        demo=False,
    )
