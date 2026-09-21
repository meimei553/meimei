"""数据层：SQLite 记录存取。

一条记录 = 一次完整反思：原文 + 背景 + 猜想 + 分析结果 + 对话历史 + 润色结果 + 改分轨迹。
MVP 阶段单机单用户，不做账号隔离；二期微信登录后再加用户字段。
数据库文件（默认 meimei.db）已被 .gitignore 排除，不会提交。
"""
import json
import sqlite3
from datetime import datetime, timezone

from backend import config

# 建表语句：JSON 字段统一存字符串，读出时还原为对象
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    background TEXT,
    original_text TEXT NOT NULL,
    guess_json TEXT,
    analysis_json TEXT,
    chat_history_json TEXT,
    polish_json TEXT,
    score_revisions_json TEXT
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


def save_record(original_text: str, background: str | None = None) -> int:
    """新建一条记录（只含原文和背景），返回记录 id。"""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO records (created_at, background, original_text) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), background, original_text),
        )
        return cursor.lastrowid


def update_record_json(record_id: int, field: str, value: object) -> bool:
    """更新记录的某个 JSON 字段（如分析结果、对话历史、润色结果、改分轨迹）。

    field 只允许是白名单里的列名，防止 SQL 注入。
    """
    allowed = {"guess_json", "analysis_json", "chat_history_json", "polish_json", "score_revisions_json"}
    if field not in allowed:
        raise ValueError(f"不允许更新的字段：{field}")
    with _connect() as conn:
        cursor = conn.execute(
            f"UPDATE records SET {field} = ? WHERE id = ?",
            (json.dumps(value, ensure_ascii=False), record_id),
        )
        return cursor.rowcount > 0


def _row_to_dict(row: sqlite3.Row) -> dict:
    """把数据库行转成字典，JSON 字段还原为对象。"""
    result = {"id": row["id"], "created_at": row["created_at"],
              "background": row["background"], "original_text": row["original_text"]}
    for field in ("guess_json", "analysis_json", "chat_history_json",
                  "polish_json", "score_revisions_json"):
        raw = row[field]
        # 字段名去掉 _json 后缀作为对外键名
        result[field.removesuffix("_json")] = json.loads(raw) if raw else None
    return result


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
        row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_record(record_id: int) -> bool:
    """删除一条记录（决策：私密工具，想删就删得掉）。"""
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        return cursor.rowcount > 0
