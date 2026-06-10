# 对话历史管理 -- SQLite 多会话管理
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


def init_db(db_path=None):
    """
    初始化数据库连接并创建表结构
    参数:
      - db_path: 数据库文件路径，默认使用 config 中的路径
    返回:
      - Connection: SQLite 连接对象
    """
    if db_path is None:
        from config import HISTORY_DB_PATH
        db_path = str(HISTORY_DB_PATH)
        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")  # WAL 模式提升并发性能

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            msg_type TEXT NOT NULL CHECK(msg_type IN ('input', 'result')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, created_at);
    """)

    return conn


def create_session(conn, title=None):
    """
    创建新会话
    参数:
      - conn: 数据库连接
      - title: 会话标题，默认使用当前时间戳
    返回:
      - session_id: UUID 字符串
    """
    if title is None:
        title = datetime.now().strftime("%Y-%m-%d %H:%M")

    session_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions (id, title) VALUES (?, ?)",
        (session_id, title)
    )
    conn.commit()
    return session_id


def delete_session(conn, session_id):
    """
    删除会话及其所有消息
    参数:
      - conn: 数据库连接
      - session_id: 会话ID
    返回:
      - bool: 是否成功删除
    """
    cursor = conn.execute(
        "DELETE FROM sessions WHERE id = ?", (session_id,)
    )
    conn.commit()
    return cursor.rowcount > 0


def get_sessions(conn):
    """
    获取所有会话列表，按 updated_at 降序
    参数:
      - conn: 数据库连接
    返回:
      - list[dict]: 会话列表
    """
    cursor = conn.execute(
        "SELECT id, title, created_at, updated_at "
        "FROM sessions ORDER BY updated_at DESC"
    )
    sessions = []
    for row in cursor.fetchall():
        sessions.append({
            "id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
        })
    return sessions


def add_message(conn, session_id, role, content, msg_type):
    """
    添加一条消息
    参数:
      - conn: 数据库连接
      - session_id: 会话ID
      - role: 'user' 或 'assistant'
      - content: 消息内容
      - msg_type: 'input' 或 'result'
    返回:
      - msg_id: 消息ID（整数）
    """
    cursor = conn.execute(
        "INSERT INTO messages (session_id, role, content, msg_type) "
        "VALUES (?, ?, ?, ?)",
        (session_id, role, content, msg_type)
    )
    # 更新会话的 updated_at 时间戳
    conn.execute(
        "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (session_id,)
    )
    conn.commit()
    return cursor.lastrowid


def get_session_messages(conn, session_id):
    """
    获取会话的完整消息历史（按时间排序）
    参数:
      - conn: 数据库连接
      - session_id: 会话ID
    返回:
      - list[dict]: 消息列表
    """
    cursor = conn.execute(
        "SELECT id, session_id, role, content, msg_type, created_at "
        "FROM messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    )
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row[0],
            "session_id": row[1],
            "role": row[2],
            "content": row[3],
            "msg_type": row[4],
            "created_at": row[5],
        })
    return messages


def update_session_title(conn, session_id, title):
    """
    更新会话标题
    参数:
      - conn: 数据库连接
      - session_id: 会话ID
      - title: 新标题
    返回:
      - bool: 是否成功更新
    """
    cursor = conn.execute(
        "UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (title, session_id)
    )
    conn.commit()
    return cursor.rowcount > 0
