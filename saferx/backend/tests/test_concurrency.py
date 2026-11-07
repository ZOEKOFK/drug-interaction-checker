"""并发安全回归测试。

背景（真实事故）：线上 10 并发压测出现约 10% 的 500，错误为
    sqlite3.ProgrammingError: SQLite objects created in a thread can only be used
    in that same thread.
根因是 FastAPI 把「同步生成器依赖」的 enter / exit 分段丢进线程池，高并发时会落到
不同线程；sqlite3 默认禁止连接跨线程。低并发时线程池空闲、恰好同线程，所以长期未被发现。

这两条测试锁死该行为：一旦有人去掉 check_same_thread=False，会立刻红。
"""
import threading

from app.core import db


def test_connection_usable_across_threads():
    """连接在一个线程创建、在另一个线程查询并关闭，都必须成功。"""
    gen = db.get_conn()
    conn = next(gen)  # 模拟依赖 __enter__：线程 A
    assert conn.execute("SELECT 1").fetchone()[0] == 1

    errors: list[BaseException] = []

    def use_in_other_thread():
        try:
            assert conn.execute("SELECT COUNT(*) FROM drug").fetchone()[0] > 0
        except BaseException as e:  # noqa: BLE001 - 收集后统一断言
            errors.append(e)

    t = threading.Thread(target=use_in_other_thread)
    t.start()
    t.join()

    def close_in_third_thread():
        try:
            next(gen, None)  # 模拟依赖 __exit__：线程 C，触发 finally 里的 conn.close()
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    t2 = threading.Thread(target=close_in_third_thread)
    t2.start()
    t2.join()

    assert not errors, f"连接跨线程使用失败：{errors[0]!r}"


def test_open_conn_cross_thread():
    """open_conn（脚本/测试用）同样必须支持跨线程。"""
    conn = db.open_conn()
    errors: list[BaseException] = []

    def q():
        try:
            conn.execute("SELECT COUNT(*) FROM ddi").fetchone()
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    t = threading.Thread(target=q)
    t.start()
    t.join()
    conn.close()

    assert not errors, f"open_conn 跨线程失败：{errors[0]!r}"
