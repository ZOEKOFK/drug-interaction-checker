"""SQLite 连接与查询封装（唯一数据访问点）。"""
import sqlite3
from collections.abc import Generator

from ..config import DB_PATH


def get_conn() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI 依赖：每请求一个连接，请求结束关闭。"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")  # API 层只读，写入仅经数据管道
    try:
        yield conn
    finally:
        conn.close()


def open_conn() -> sqlite3.Connection:
    """脚本/测试用：手动管理生命周期的连接。"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn
