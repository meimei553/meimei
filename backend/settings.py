"""设置分枝：称呼设置与反馈入口（施工图节点 4）。

称呼系统 MVP 最简版：用户设置"希望 AI 怎么称呼你"，
之后分析和对话都会用这个称呼（AI 自己不用名字，自称"我"）。
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend import storage

router = APIRouter(prefix="/api", tags=["设置与反馈"])


class SettingsIn(BaseModel):
    """设置项的写入参数。"""

    user_nickname: str = Field(..., description="希望 AI 怎么称呼你")


class FeedbackIn(BaseModel):
    """反馈的提交参数。"""

    content: str = Field(..., description="反馈内容")


@router.get("/settings")
def get_settings() -> dict:
    """读取当前设置。"""
    return {"user_nickname": storage.get_setting("user_nickname")}


@router.put("/settings")
def put_settings(req: SettingsIn) -> dict:
    """修改设置（目前只有称呼，后续慢慢完善）。"""
    storage.set_setting("user_nickname", req.user_nickname)
    return {"user_nickname": req.user_nickname, "saved": True}


@router.post("/feedback")
def submit_feedback(req: FeedbackIn) -> dict:
    """提交反馈，存进数据库（决策：设置页极简反馈框）。"""
    feedback_id = storage.save_feedback(req.content)
    return {"saved": True, "id": feedback_id, "thanks": "谢谢你的反馈，我会认真看的。"}
