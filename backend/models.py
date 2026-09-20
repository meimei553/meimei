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
