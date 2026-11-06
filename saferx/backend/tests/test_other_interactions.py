"""其他相互作用测试：DDSI / DFI / 重复用药。

数据来自 DDInter 2.0 网页接口（官方无 CSV），断言以库内实际记录为准，
避免把「官方宣传口径」写死进测试。
"""
from app.services.other_interactions import (
    check_disease,
    check_duplication,
    check_food,
    list_diseases,
)


def test_disease_list_sorted_by_count(conn):
    items = list_diseases(conn, limit=20)
    assert len(items) == 20
    counts = [i["count"] for i in items]
    assert counts == sorted(counts, reverse=True)
    # 肾脏/肝脏疾病是收录最多的两类，且都有中文名
    assert {"Kidney Diseases", "Liver Diseases"} <= {i["name_en"] for i in items}
    assert all(i["name_cn"] for i in items[:10])


def test_disease_risk_hit(conn):
    """华法林 × 出血/糖尿病 在 DDInter 中均为 Major 禁忌。"""
    drug = conn.execute("SELECT * FROM drug WHERE name_en = 'Warfarin'").fetchone()
    risks = check_disease(conn, [drug], ["Hemorrhage", "Diabetes Mellitus"])
    assert risks, "华法林应命中至少一条疾病禁忌"
    assert all(r["level"] == "Major" for r in risks)
    assert {r["disease_en"] for r in risks} == {"Hemorrhage", "Diabetes Mellitus"}
    # 中文摘要与等级文案必须自洽
    for r in risks:
        assert r["disease_cn"] and r["disease_cn"] in r["summary_cn"]
        assert r["level_cn"] in r["summary_cn"]
        assert r["description_en"]


def test_disease_risk_no_context(conn):
    drug = conn.execute("SELECT * FROM drug WHERE name_en = 'Warfarin'").fetchone()
    assert check_disease(conn, [drug], []) == []


def test_food_risk_warfarin(conn):
    """华法林与富含维生素 K 的食物是经典拮抗，必须命中。"""
    drug = conn.execute("SELECT * FROM drug WHERE name_en = 'Warfarin'").fetchone()
    risks = check_food(conn, [drug])
    foods = {r["food_en"] for r in risks}
    assert "food high in vitamin K" in foods
    assert all(r["summary_cn"] and r["food_cn"] for r in risks)


def test_food_risk_amiodarone_grapefruit(conn):
    drug = conn.execute("SELECT * FROM drug WHERE name_en = 'Amiodarone'").fetchone()
    risks = check_food(conn, [drug])
    hit = [r for r in risks if r["food_en"] == "grapefruit juice"]
    assert hit and hit[0]["level"] == "Major"
    assert hit[0]["mechanism_cn"] == "代谢"


def test_duplication_detected(conn):
    """胺碘酮 + 地高辛 同属 antiarrhythmics，应触发治疗重复告警。"""
    drugs = [
        conn.execute("SELECT * FROM drug WHERE name_en = ?", (n,)).fetchone()
        for n in ("Amiodarone", "Digoxin")
    ]
    groups = check_duplication(conn, drugs)
    assert groups, "同类别两药应产生重复用药告警"
    assert groups[0]["category_en"] == "antiarrhythmics"
    assert len(groups[0]["drugs"]) == 2
    assert "抗心律失常药" in groups[0]["summary_cn"]


def test_duplication_single_drug(conn):
    drug = conn.execute("SELECT * FROM drug WHERE name_en = 'Warfarin'").fetchone()
    assert check_duplication(conn, [drug]) == []


def test_duplication_different_categories(conn):
    """华法林（抗凝）+ 二甲双胍（降糖）不构成治疗重复。"""
    names = ("Warfarin", "Metformin")
    drugs = [conn.execute("SELECT * FROM drug WHERE name_en = ?", (n,)).fetchone() for n in names]
    assert check_duplication(conn, drugs) == []


def test_api_check_with_diseases(client):
    r = client.post(
        "/api/check",
        json={
            "medications": ["华法林", "胺碘酮", "地高辛", "阿司匹林"],
            "diseases": ["Hemorrhage", "Kidney Diseases"],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["diseases_checked"] == ["Hemorrhage", "Kidney Diseases"]
    assert data["disease_risks"]
    assert data["food_risks"]
    assert data["duplications"]
    assert data["other_summary"]["disease"]["Major"] >= 1
    assert data["overall_all"] in {"red", "orange", "green", "gray"}
    # 原有 DDI 字段不受影响
    assert data["summary"]["Major"] >= 1


def test_api_check_without_diseases(client):
    r = client.post("/api/check", json={"medications": ["华法林", "阿司匹林"]})
    assert r.status_code == 200
    data = r.json()
    assert data["disease_risks"] == []
    assert "跳过" in data["other_note"]
    assert data["food_risks"], "食物相互作用不依赖疾病上下文"


def test_api_diseases_endpoint(client):
    r = client.get("/api/drugs/diseases?limit=30")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 30
    assert {"name_en", "name_cn", "count", "major"} <= set(items[0])


def test_api_diseases_limit_guard(client):
    assert client.get("/api/drugs/diseases?limit=5").status_code == 422
