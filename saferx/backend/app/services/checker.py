"""
核心检查器（方案 §3.3，纯函数式，无 Web 依赖）。

输入: 药单 M = [m1, ..., mn]（药名或 DDInter ID）
输出: 风险列表 + 整体分级 + 未收录组合（诚实边界）

流程: 归一化(alias) -> 组合 C(n,2) -> 查 ddi 表(复合唯一索引) -> 聚合分级。
存储侧已按无序对规范化（id_a < id_b），查询 O(1) 命中唯一索引。
"""
import datetime

from ..config import get_data_version
from .alias import drug_brief, resolve_one
from .other_interactions import check_other

LEVEL_CN = {"Major": "严重", "Moderate": "中度", "Minor": "轻微", "Unknown": "分级未知"}
LEVEL_ORDER = {"Major": 0, "Moderate": 1, "Minor": 2, "Unknown": 3}  # 展示排序（严重在前）

FALLBACK_MECHANISM_CN = (
    "该组合收录于 DDInter 2.0 审编数据库（分级：{level}）。"
    "官方未提供该记录的详细机制描述，可凭下方来源 ID 到 DDInter 官网查看，或咨询医师/药师。"
)
FALLBACK_MANAGEMENT = "请咨询医师或药师；如出现不适应及时就医，勿自行停药或调整剂量。"


def check_meds(conn, meds: list[str], diseases: list[str] | None = None) -> dict:
    # 1) 归一化
    resolved: list = []
    seen: set[str] = set()
    unresolved: list[dict] = []
    for m in meds:
        row, candidates = resolve_one(conn, m)
        if row is None:
            unresolved.append(
                {"input": m, "candidates": [drug_brief(c) for c in candidates[:6]]}
            )
        elif row["ddinter_id"] not in seen:
            seen.add(row["ddinter_id"])
            resolved.append(row)

    # 2) 两两组合 C(n,2)
    pairs: list[dict] = []
    unrecorded: list[dict] = []
    n = len(resolved)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = resolved[i], resolved[j]
            lo, hi = sorted((a["ddinter_id"], b["ddinter_id"]))  # 无序对规范化
            rec = conn.execute(
                """
                SELECT d.level, d.source_id,
                       m.text_cn AS mech_cn, m.text_en AS mech_en, m.management_cn AS mgmt
                FROM ddi d
                LEFT JOIN mechanism m ON m.id = d.mechanism_id
                WHERE d.ddinter_id_a = ? AND d.ddinter_id_b = ?
                """,
                (lo, hi),
            ).fetchone()
            if rec is None:
                unrecorded.append({"drug_a": drug_brief(a), "drug_b": drug_brief(b)})
                continue
            if rec["mech_cn"]:
                mechanism_cn = rec["mech_cn"]
                mechanism_en = rec["mech_en"]
                management = rec["mgmt"]
            else:
                mechanism_cn = FALLBACK_MECHANISM_CN.format(level=LEVEL_CN[rec["level"]])
                mechanism_en = None
                management = FALLBACK_MANAGEMENT
            pairs.append(
                {
                    "drug_a": drug_brief(a),
                    "drug_b": drug_brief(b),
                    "level": rec["level"],
                    "level_cn": LEVEL_CN[rec["level"]],
                    "mechanism_cn": mechanism_cn,
                    "mechanism_en": mechanism_en,
                    "management": management,
                    "source_id": rec["source_id"],
                }
            )

    # 3) 排序（严重在前）+ 汇总分级
    pairs.sort(key=lambda p: (LEVEL_ORDER[p["level"]], p["drug_a"]["name_en"]))

    summary = {
        "Major": sum(1 for p in pairs if p["level"] == "Major"),
        "Moderate": sum(1 for p in pairs if p["level"] == "Moderate"),
        "Minor": sum(1 for p in pairs if p["level"] == "Minor"),
        "Unknown": sum(1 for p in pairs if p["level"] == "Unknown"),
        "overall": _overall(pairs),
    }

    if unrecorded:
        coverage_note = (
            f"以下 {len(unrecorded)} 个药物组合在数据库中无收录记录，"
            "不代表无相互作用（数据覆盖 2,310 种已批准药物）。"
        )
    elif pairs:
        coverage_note = "当前药单所有组合均有收录记录；「分级未知」条目为官方未标注严重度的记录，同样不代表安全。"
    else:
        coverage_note = "药单内无收录记录——未收录不代表无相互作用，请咨询医师或药师。"

    # 4) 其他相互作用（DDSI / DFI / 重复用药）
    other = check_other(conn, resolved, diseases)

    return {
        "unresolved": unresolved,
        "pairs": pairs,
        "unrecorded_pairs": unrecorded,
        "summary": summary,
        "checked_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "data_version": get_data_version(conn),
        "coverage_note": coverage_note,
        **other,
        "overall_all": _combine(summary["overall"], other["other_summary"]["overall"]),
    }


_SEVERITY = {"red": 3, "orange": 2, "green": 1, "gray": 0}


def _combine(a: str, b: str) -> str:
    """DDI 与「其他相互作用」的等级取更高者（宁高报不漏报）。"""
    return a if _SEVERITY.get(a, 0) >= _SEVERITY.get(b, 0) else b


def _overall(pairs: list[dict]) -> str:
    levels = {p["level"] for p in pairs}
    if "Major" in levels:
        return "red"
    if "Moderate" in levels:
        return "orange"
    if "Minor" in levels:
        return "green"
    return "gray"
