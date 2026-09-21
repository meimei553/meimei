"""记录分枝：反思记录的列表/详情/删除（施工图节点 4）。

记录由 analyze/chat/polish 模块自动保存，这里只负责读取和删除。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import prompts, storage

router = APIRouter(prefix="/api/records", tags=["反思记录"])


class RecordListResponse(BaseModel):
    """记录列表的返回结果。"""

    total: int = Field(..., description="记录总数")
    companion: str = Field(..., description="温和陪伴文案（'第 N 次认真面对自己的情绪'）")
    records: list[dict] = Field(..., description="记录列表，最新在前")


@router.get("", response_model=RecordListResponse)
def list_records(emotion: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    """查询记录列表。传 emotion 参数时只保留含该情绪的记录（决策：按情绪筛选）。"""
    if emotion:
        # 筛选时先取较大范围再过滤（MVP 单机数据量小，内存过滤足够）
        all_records = storage.list_records(limit=200, offset=0)
        filtered = [
            r for r in all_records
            if r.get("analysis") and any(
                e.get("name") == emotion for e in r["analysis"].get("emotions", [])
            )
        ]
        records = filtered[offset:offset + limit]
    else:
        records = storage.list_records(limit=limit, offset=offset)

    total = storage.count_records()
    return {
        "total": total,
        "companion": prompts.COPY_RECORDS_COMPANION.format(count=total),
        "records": records,
    }


@router.get("/{record_id}")
def get_record(record_id: int) -> dict:
    """查看一条记录的完整详情（含分析、对话历史、润色、改分轨迹）。

    回看负面记录时，开头附上温柔承接（决策 38）。
    """
    record = storage.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 占比最高的情绪是负面情绪时，附上温柔承接
    review_comfort = None
    analysis = record.get("analysis")
    if analysis and analysis.get("emotions"):
        top = max(analysis["emotions"], key=lambda e: e.get("percent", 0))
        if top.get("name") in prompts.NEGATIVE_EMOTIONS:
            review_comfort = prompts.COPY_REVIEW_COMFORT

    return {**record, "review_comfort": review_comfort}


@router.delete("/{record_id}")
def delete_record(record_id: int) -> dict:
    """删除一条记录（决策：私密工具，想删就删得掉）。"""
    if not storage.delete_record(record_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"deleted": True, "id": record_id}
