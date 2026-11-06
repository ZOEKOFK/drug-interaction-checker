"""checker 核心逻辑单测：方案 §9 七个经典案例 + 安全对照（§8.6 软件测试计划）。"""
from app.services.checker import check_meds


def _level_of(result, name_a, name_b):
    for p in result["pairs"]:
        pair_names = {p["drug_a"]["name_cn"], p["drug_b"]["name_cn"]}
        if pair_names == {name_a, name_b}:
            return p["level"]
    return None


CLASSIC_CASES = [
    # (药A, 药B, 期望分级) —— 期望值与 DDInter 2.0 真实数据核对（2026-11-06）
    ("华法林", "阿司匹林", "Major"),      # 抗凝+抗板叠加，出血风险
    ("华法林", "胺碘酮", "Major"),        # CYP2C9 抑制，INR 升高
    ("辛伐他汀", "克拉霉素", "Major"),    # CYP3A4 强抑制，横纹肌溶解
    ("氯吡格雷", "奥美拉唑", "Major"),    # CYP2C19 抑制，抗板效应降低
    ("左氧氟沙星", "胺碘酮", "Major"),    # QT 延长叠加
    ("碳酸锂", "氢氯噻嗪", "Major"),      # 锂清除率下降
    ("帕罗西汀", "曲马多", "Major"),      # 5-羟色胺综合征
]


def test_classic_cases(conn):
    result = check_meds(conn, [a for a, _, _ in CLASSIC_CASES] + [b for _, b, _ in CLASSIC_CASES])
    for a, b, expected in CLASSIC_CASES:
        assert _level_of(result, a, b) == expected, f"{a}+{b} 应为 {expected}"


def test_safe_controls(conn):
    """安全对照：无记录组合进入 unrecorded 而非 pairs（未收录 ≠ 安全）。"""
    result = check_meds(conn, ["华法林", "碳酸锂"])
    assert result["pairs"] == []
    assert len(result["unrecorded_pairs"]) == 1
    assert result["summary"]["overall"] == "gray"
    assert "未收录" in result["coverage_note"] or "无收录" in result["coverage_note"]


def test_unknown_level(conn):
    """分级未知（DDInter 官方 Unknown）正确透传，且不影响 overall 分级。"""
    result = check_meds(conn, ["氨氯地平", "二甲双胍"])
    assert _level_of(result, "氨氯地平", "二甲双胍") == "Unknown"
    assert result["summary"]["Unknown"] == 1
    assert result["summary"]["overall"] == "gray"  # 仅 Unknown 不改变总体色


def test_mechanism_curated_vs_fallback(conn):
    """经典组合挂接人工审编机制；其余组合回退到诚实提示文本。"""
    result = check_meds(conn, ["华法林", "胺碘酮", "二甲双胍"])
    curated = [p for p in result["pairs"] if set([p["drug_a"]["name_cn"], p["drug_b"]["name_cn"]]) == {"华法林", "胺碘酮"}][0]
    assert curated["mechanism_en"] is not None and "CYP2C9" in curated["mechanism_cn"]

    fallback = [p for p in result["pairs"] if "二甲双胍" in (p["drug_a"]["name_cn"], p["drug_b"]["name_cn"])][0]
    assert fallback["mechanism_en"] is None
    assert "DDInter 2.0" in fallback["mechanism_cn"]


def test_summary_and_order(conn):
    """模板一（高血压+房颤）：多条 Major、红色总体、按严重度降序。"""
    result = check_meds(conn, ["华法林", "胺碘酮", "地高辛", "氨氯地平", "氢氯噻嗪"])
    assert result["summary"]["Major"] >= 3
    assert result["summary"]["overall"] == "red"
    levels = [p["level"] for p in result["pairs"]]
    order = {"Major": 0, "Moderate": 1, "Minor": 2, "Unknown": 3}
    assert levels == sorted(levels, key=lambda x: order[x])


def test_unresolved_input(conn):
    result = check_meds(conn, ["nosuchdrug123", "华法林"])
    assert len(result["unresolved"]) == 1
    assert result["unresolved"][0]["input"] == "nosuchdrug123"
    assert _level_of(result, "华法林", "华法林") is None  # 单药无组合


def test_dedup_and_id_input(conn):
    """重复输入去重；DDInter ID 直连。"""
    result = check_meds(conn, ["华法林", "华法林", "DDInter1951", "胺碘酮"])
    assert len(result["pairs"]) == 1
