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


def get_stats(conn) -> dict:
    """库内真实规模与覆盖度（首页/关于页展示，避免硬编码官方口径）。"""
    def _one(sql: str, default=0):
        try:
            row = conn.execute(sql).fetchone()
            return row[0] if row and row[0] is not None else default
        except Exception:  # noqa: BLE001 - 表缺失时返回默认值
            return default

    meta = {}
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    except Exception:  # noqa: BLE001
        pass

    levels = {}
    try:
        levels = dict(conn.execute("SELECT level, COUNT(*) FROM ddi GROUP BY level").fetchall())
    except Exception:  # noqa: BLE001
        pass

    drugs = _one("SELECT COUNT(*) FROM drug")
    drugs_cn = _one("SELECT COUNT(*) FROM drug WHERE name_cn IS NOT NULL")
    ddi_pairs = _one("SELECT COUNT(*) FROM ddi")
    mechanisms = _one("SELECT COUNT(*) FROM mechanism")
    mech_covered = _one("SELECT COUNT(*) FROM ddi WHERE mechanism_id IS NOT NULL")

    return {
        "drugs": drugs,
        "drugs_with_cn": drugs_cn,
        "ddi_pairs": ddi_pairs,
        "mechanisms": mechanisms,
        "mechanisms_covered_pairs": mech_covered,
        "aliases": _one("SELECT COUNT(*) FROM alias"),
        "aliases_cn": _one("SELECT COUNT(*) FROM alias WHERE kind = 'cn'"),
        "templates": _one("SELECT COUNT(*) FROM template"),
        "levels": {
            "Major": levels.get("Major", 0),
            "Moderate": levels.get("Moderate", 0),
            "Minor": levels.get("Minor", 0),
            "Unknown": levels.get("Unknown", 0),
        },
        "built_at": meta.get("built_at", ""),
        "source": meta.get("source", "DDInter 2.0"),
    }
