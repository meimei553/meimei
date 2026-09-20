"""反思记录接口：查询历史、查看详情、删除。

记录由 /api/analyze 和 /api/polish 自动保存，这里只负责读取和删除。
"""
from fastapi import APIRouter, HTTPException

from backend import storage
from backend.models import RecordOut

router = APIRouter(prefix="/api/records", tags=["反思记录"])


@router.get("", response_model=list[RecordOut])
def list_records(limit: int = 20, offset: int = 0) -> list[dict]:
    """查询记录列表，最新的在前。limit 控制条数，offset 用于翻页。"""
    return storage.list_records(limit=limit, offset=offset)


@router.get("/{record_id}", response_model=RecordOut)
def get_record(record_id: int) -> dict:
    """查看一条记录的完整详情。"""
    record = storage.get_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


@router.delete("/{record_id}")
def delete_record(record_id: int) -> dict:
    """删除一条记录（私密工具的基本修养：想删就删得掉）。"""
    if not storage.delete_record(record_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"deleted": True, "id": record_id}
