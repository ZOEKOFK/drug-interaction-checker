"""alias 归一化四条路径：中文 / 拼音首字母 / 大小写 / 未命中候选。"""
from app.services.alias import resolve_one, search_drugs


def test_cn_exact(conn):
    row, _ = resolve_one(conn, "华法林")
    assert row["ddinter_id"] == "DDInter1951"
    assert row["name_en"] == "Warfarin"


def test_pinyin(conn):
    row, _ = resolve_one(conn, "hfl")
    assert row["name_en"] == "Warfarin"


def test_case_insensitive_en(conn):
    row, _ = resolve_one(conn, "WARFARIN")
    assert row["ddinter_id"] == "DDInter1951"


def test_synonym(conn):
    row, _ = resolve_one(conn, "Aspirin")
    assert row["ddinter_id"] == "DDInter20"  # 官方名 Acetylsalicylic acid


def test_ddinter_id(conn):
    row, _ = resolve_one(conn, "DDInter1951")
    assert row["name_en"] == "Warfarin"


def test_miss_with_no_candidates(conn):
    row, candidates = resolve_one(conn, "nosuchdrug123")
    assert row is None
    assert candidates == []


def test_miss_gives_candidates(conn):
    row, candidates = resolve_one(conn, "华法")
    assert row is None or row["name_en"] == "Warfarin"
    assert candidates, "前缀未完整命中时应给出候选"


def test_search_cn_prefix(conn):
    rows = search_drugs(conn, "华法", 10)
    assert rows and rows[0]["name_cn"] == "华法林"


def test_search_empty_returns_curated(conn):
    rows = search_drugs(conn, "", 40)
    assert len(rows) >= 30
    assert all(r["name_cn"] for r in rows)
