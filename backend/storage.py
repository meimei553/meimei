"""SQLite 记录存储：自动保存每一次分析和润色，形成反思日记。

设计说明：
- 一条记录 = 原文 + 分析结果 + 润色结果（润色可后补，通过 record_id 关联）
- MVP 阶段是单机单用户，不做账号隔离；二期微信登录后再加用户字段
- 数据库文件（默认 meimei.db）已被 .gitignore 排除，不会提交
"""
import json
import sqlite3
from datetime import datetime, timezone

from backend import config

# 建表语句：一条反思记录包含原文、分析结果、润色结果
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    scene TEXT,
    original_text TEXT NOT NULL,
    analysis_json TEXT,
    polish_json TEXT
)
"""


def _connect() -> sqlite3.Connection:
    """每次操作新建连接（sqlite3 连接不能跨线程共享，这样最省心）。"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # 查询结果按列名访问
    return conn


def init_db() -> None:
    """初始化数据库表（服务启动时调用一次）。"""
    with _connect() as conn:
        conn.execute(_CREATE_TABLE)


def save_record(
    original_text: str,
    scene: str | None = None,
    analysis: dict | None = None,
    polish: dict | None = None,
) -> int:
    """新建一条记录，返回记录 id。"""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO records (created_at, scene, original_text, analysis_json, polish_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                scene,
                original_text,
                json.dumps(analysis, ensure_ascii=False) if analysis else None,
                json.dumps(polish, ensure_ascii=False) if polish else None,
            ),
        )
        return cursor.lastrowid


def attach_polish(record_id: int, polish: dict) -> bool:
    """把润色结果补充到已有记录上（先分析后润色时，两条结果合并成一条反思日记）。"""
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE records SET polish_json = ? WHERE id = ?",
            (json.dumps(polish, ensure_ascii=False), record_id),
        )
        return cursor.rowcount > 0


def _row_to_dict(row: sqlite3.Row) -> dict:
    """把数据库行转成字典，JSON 字段还原为对象。"""
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "scene": row["scene"],
        "original_text": row["original_text"],
        "analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else None,
        "polish": json.loads(row["polish_json"]) if row["polish_json"] else None,
    }


def list_records(limit: int = 20, offset: int = 0) -> list[dict]:
    """按时间倒序查询记录列表（最新的在前）。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM records ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_record(record_id: int) -> dict | None:
    """查询单条记录详情，不存在时返回 None。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM records WHERE id = ?", (record_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete_record(record_id: int) -> bool:
    """删除一条记录，返回是否删除成功。"""
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        return cursor.rowcount > 0
