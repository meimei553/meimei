"""接口的数据模型（请求和响应的格式定义）。"""
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """情绪分析接口的请求参数。"""

    text: str = Field(..., description="聊天记录或想说的气话，自由粘贴即可")
    scene: str | None = Field(
        default=None,
        description="场景，可选：情侣/职场/家庭/朋友/其他，帮助 AI 更准确地理解语境",
    )


class AnalyzeResponse(BaseModel):
    """情绪分析接口的返回结果。"""

    dimensions: dict[str, int] = Field(..., description="8 个情绪维度的分数（0-100），前端用来画雷达图")
    my_analysis: str = Field(..., description="对用户（我）的情绪解读：当时为什么这样说")
    other_analysis: str | None = Field(..., description="对对方的心理推测和言外之意")
    comfort: str = Field(..., description="安慰的话")
    guiding_questions: list[str] = Field(..., description="引导式反思问题，邀请用户往深处想")
    summary: str = Field(..., description="一句话总结情绪核心")
    demo: bool = Field(..., description="是否为演示数据（未配置 API Key 时为 true）")


class PolishRequest(BaseModel):
    """润色接口的请求参数。"""

    text: str = Field(..., description="要润色的原话（气话/想说但没说好的话）")
    analysis_context: str | None = Field(
        default=None,
        description="可选：情绪分析结果摘要，AI 会结合它来判断语气",
    )
    tone: str | None = Field(
        default=None,
        description="可选：指定语气。可以填预设 key（gentle_firm/humorous/concise/formal/soft），"
                    "也可以直接用自然语言描述，比如'温柔但坚定，像心理咨询师一样'。"
                    "不填则由 AI 分析后自动判断并组合 2~3 种语气",
    )
    feedback: str | None = Field(
        default=None,
        description="可选：多轮微调时，用户对上一版的意见，比如'太正式了，像写公文'",
    )
    previous: str | None = Field(
        default=None,
        description="可选：多轮微调时，上一版的润色结果",
    )


class PolishVersion(BaseModel):
    """一个润色版本。"""

    tone: str = Field(..., description="这个版本用的语气")
    text: str = Field(..., description="润色后的话")


class PolishResponse(BaseModel):
    """润色接口的返回结果。"""

    versions: list[PolishVersion] = Field(..., description="2~3 个不同语气的润色版本")
    auto_tone: bool = Field(..., description="语气是否由 AI 自动判断组合（用户未指定时为 true）")
    demo: bool = Field(..., description="是否为演示数据")
