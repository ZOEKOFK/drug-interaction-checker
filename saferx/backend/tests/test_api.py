"""接口测试（FastAPI TestClient）：正常流 / 未命中 / 空药单 / n=1 / n>20 边界。"""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_check_normal_flow(client):
    r = client.post("/api/check", json={"medications": ["华法林", "胺碘酮", "地高辛"]})
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["Major"] >= 2
    assert data["summary"]["overall"] == "red"
    for p in data["pairs"]:
        assert p["level"] in ("Major", "Moderate", "Minor", "Unknown")
        assert p["drug_a"]["name_cn"] and p["drug_b"]["name_cn"]
        assert p["source_id"].startswith("DDInter2.0:")


def test_check_with_ids(client):
    r = client.post("/api/check", json={"medications": ["DDInter1951", "DDInter1675"]})
    assert r.status_code == 200
    assert len(r.json()["pairs"]) >= 1


def test_check_unresolved(client):
    r = client.post("/api/check", json={"medications": ["不存在的药xyz", "华法林"]})
    assert r.status_code == 200
    data = r.json()
    assert data["unresolved"][0]["input"] == "不存在的药xyz"


def test_check_empty_list(client):
    r = client.post("/api/check", json={"medications": []})
    assert r.status_code == 200
    assert r.json()["pairs"] == []


def test_check_single_drug(client):
    r = client.post("/api/check", json={"medications": ["华法林"]})
    assert r.status_code == 200
    assert r.json()["pairs"] == []  # C(1,2) = 0


def test_check_over_20_rejected(client):
    meds = [f"drug{i}" for i in range(21)]
    r = client.post("/api/check", json={"medications": meds})
    assert r.status_code == 422  # pydantic max_length


def test_search(client):
    r = client.get("/api/drugs/search", params={"q": "warfarin", "limit": 5})
    assert r.status_code == 200
    rows = r.json()
    assert any(x["name_en"] == "Warfarin" for x in rows)


def test_search_pinyin(client):
    r = client.get("/api/drugs/search", params={"q": "hfl", "limit": 5})
    assert any(x["name_en"] == "Warfarin" for x in r.json())


def test_templates(client):
    r = client.get("/api/drugs/templates")
    assert r.status_code == 200
    tpls = r.json()
    assert len(tpls) == 4
    assert tpls[0]["name"].startswith("高血压")
    assert all(t["drugs"] for t in tpls)


def test_graph(client):
    r = client.get("/api/graph", params={"ids": "DDInter1951,DDInter1675,DDInter79"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) == 3
    assert data["links"]
    for l in data["links"]:
        assert l["lineStyle"]["color"]


def test_report(client):
    r = client.get("/api/report", params={"ids": "DDInter1951,DDInter1675"})
    assert r.status_code == 200
    assert "summary" in r.json()


def test_lab_extract(client):
    text = "患者长期口服华法林抗凝，近期因房颤加用胺碘酮，需警惕INR升高。"
    r = client.post("/api/lab/extract", json={"text": text})
    assert r.status_code == 200
    data = r.json()
    texts = [e["text"] for e in data["entities"]]
    assert "华法林" in texts and "胺碘酮" in texts
    assert data["triples"][0]["status"] == "known"


def test_lab_extract_new_pair(client):
    text = "慢性心衰患者长期服用地高辛，近日加用美托洛尔控制心室率。"
    r = client.post("/api/lab/extract", json={"text": text})
    data = r.json()
    # 地高辛+美托洛尔在主库有收录（DDInter 数据稠密），断言抽取闭环本身可用
    assert r.status_code == 200
    assert len(data["triples"]) >= 1
    assert data["triples"][0]["status"] in ("known", "new")


def test_lab_extract_empty_rejected(client):
    r = client.post("/api/lab/extract", json={"text": ""})
    assert r.status_code == 422


def test_unknown_api_path_returns_404_json(client):
    """未知 /api/* 必须回 404 JSON；若回 index.html，前端会拿到 200+HTML，
    在 JSON.parse 处抛无关错误，掩盖真实问题。仅在生产托管模式（有 dist）下断言。"""
    from app.config import FRONTEND_DIST

    r = client.get("/api/this-endpoint-does-not-exist")
    if (FRONTEND_DIST / "assets").exists():
        assert r.status_code == 404
        assert r.headers["content-type"].startswith("application/json")
    else:
        assert r.status_code in (404, 405)
