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

# 设置表（键值对：用户称呼等）
_CREATE_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
"""

# 反馈表（用户反馈入口，决策 44）
_CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    content TEXT NOT NULL
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
        conn.execute(_CREATE_SETTINGS_TABLE)
        conn.execute(_CREATE_FEEDBACK_TABLE)


def count_records() -> int:
    """记录总数（用于记录页的陪伴文案"第 N 次"）。"""
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]


def get_setting(key: str, default: str | None = None) -> str | None:
    """读取设置项（如用户称呼），不存在时返回默认值。"""
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    """写入设置项（已存在则覆盖）。"""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def save_feedback(content: str) -> int:
    """保存一条用户反馈，返回反馈 id。"""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO feedback (created_at, content) VALUES (?, ?)",
            (datetime.now(timezone.utc).isoformat(), content),
        )
        return cursor.lastrowid


def list_feedback() -> list[dict]:
    """查询全部反馈（最新在前）。"""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM feedback ORDER BY id DESC").fetchall()
    return [{"id": row["id"], "created_at": row["created_at"], "content": row["content"]}
            for row in rows]


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
