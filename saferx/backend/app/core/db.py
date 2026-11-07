"""SQLite 连接与查询封装（唯一数据访问点）。

关于 check_same_thread=False：
  FastAPI 对「同步生成器依赖」的调度方式是 enter / 端点执行 / exit 三段分别提交给
  线程池（fastapi.concurrency.contextmanager_in_threadpool），高并发下线程池被打满时，
  这三段会落到**不同线程**上。Python 的 sqlite3 默认禁止跨线程使用连接对象，于是抛出
  sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in
  that same thread —— 表现为压测时偶发 500，且负载越低越难复现。

  这里关闭该检查是安全的：连接仍是「每请求独占、请求内顺序使用」，任何时刻只有一个线程
  在用同一个连接，不存在并发访问同一连接的情况；底层 SQLite 以 serialized 模式编译，
  自身具备线程安全。
"""
import sqlite3
from collections.abc import Generator

from ..config import DB_PATH


def _connect() -> sqlite3.Connection:
    # check_same_thread=False：允许 FastAPI 线程池在不同线程间搬运同一连接，原因见模块文档
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_conn() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI 依赖：每请求一个连接，请求结束关闭。"""
    conn = _connect()
    conn.execute("PRAGMA query_only = ON")  # API 层只读，写入仅经数据管道
    try:
        yield conn
    finally:
        conn.close()


def open_conn() -> sqlite3.Connection:
    """脚本/测试用：手动管理生命周期的连接。"""
    return _connect()
