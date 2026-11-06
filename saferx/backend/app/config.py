"""集中配置：读取 .env（可选），路径统一从仓库根解析。"""
import os
from pathlib import Path

# app/config.py -> backend/app -> backend -> saferx（仓库根）
BASE_DIR = Path(__file__).resolve().parents[2]

DB_PATH = Path(os.getenv("SAFERX_DB", BASE_DIR / "data" / "saferx.sqlite"))
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

DEBUG = os.getenv("SAFERX_DEBUG", "0") in ("1", "true", "yes")


def get_data_version(conn) -> str:
    """从 meta 表读取数据版本描述（页面常驻显示用）。"""
    try:
        rows = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        return (
            f"DDInter 2.0 · {rows.get('drugs', '?')} 种药物 · "
            f"{int(rows.get('ddi_pairs', 0)):,} 条 DDI · 构建于 {rows.get('built_at', '?')}"
        )
    except Exception:  # noqa: BLE001 - meta 表缺失时兜底
        return "DDInter 2.0"
