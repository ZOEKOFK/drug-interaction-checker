"""pytest 共享夹具：数据库连接 + FastAPI TestClient。

若数据库不存在则提示先运行数据管道（make data && make initdb）。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # saferx/
sys.path.insert(0, str(ROOT / "backend"))

from app.core.db import open_conn  # noqa: E402
from app.main import app  # noqa: E402

DB_PATH = ROOT / "data" / "saferx.sqlite"


@pytest.fixture(scope="session")
def conn():
    if not DB_PATH.exists():
        pytest.exit(
            f"数据库不存在: {DB_PATH}\n请先运行: python pipelines/download_ddinter.py && "
            "python pipelines/clean_ddinter.py && python pipelines/build_alias_table.py && "
            "python pipelines/init_db.py",
            returncode=2,
        )
    c = open_conn()
    yield c
    c.close()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    with TestClient(app) as tc:
        yield tc
