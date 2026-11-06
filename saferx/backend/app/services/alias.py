"""
药名归一化（别名/拼音/ID 命中，未命中给候选）。

四条路径：
1. DDInter ID 精确命中
2. 别名精确命中（中文通用名 / 英文原名 / 同义词，含大小写归一）
3. 拼音首字母精确命中
4. 未命中 -> 前缀/包含模糊候选（供用户确认）
"""
import re

_ID_RE = re.compile(r"^DDInter\d+$", re.IGNORECASE)


def drug_brief(row) -> dict:
    """drug 表行 -> 前端展示结构（name_cn 缺失时回退英文名）。"""
    if row is None:
        return None
    return {
        "ddinter_id": row["ddinter_id"],
        "name_cn": row["name_cn"] or row["name_en"],
        "name_en": row["name_en"],
        "atc": row["atc_name"],
        "category": row["category"] or "药物",
    }


def resolve_one(conn, query: str):
    """单条用户输入 -> (drug_row | None, [候选 drug_row])"""
    q = (query or "").strip()
    if not q:
        return None, []

    # 1) DDInter ID
    if _ID_RE.match(q):
        row = conn.execute(
            "SELECT * FROM drug WHERE ddinter_id = ?", (q,)
        ).fetchone()
        if row:
            return row, []

    # 2) 别名精确（原样 + 小写；英文药名大小写不敏感）
    for key in {q, q.lower()}:
        row = conn.execute(
            "SELECT d.* FROM alias a JOIN drug d ON d.ddinter_id = a.ddinter_id WHERE a.alias = ?",
            (key,),
        ).fetchone()
        if row:
            return row, []

    # 3) 未命中 -> 模糊候选（别名前缀 -> 包含 -> 英文名前缀/包含）
    ql = q.lower()
    candidates: dict[str, object] = {}

    def _merge(sql: str, params: tuple):
        for r in conn.execute(sql, params).fetchall():
            candidates.setdefault(r["ddinter_id"], r)

    _merge(
        "SELECT d.* FROM alias a JOIN drug d ON d.ddinter_id = a.ddinter_id WHERE a.alias LIKE ? LIMIT 8",
        (ql + "%",),
    )
    if not candidates:
        _merge(
            "SELECT d.* FROM drug d WHERE d.name_cn LIKE ? OR lower(d.name_en) LIKE ? LIMIT 8",
            (q + "%", ql + "%"),
        )
    if not candidates:
        _merge(
            "SELECT d.* FROM alias a JOIN drug d ON d.ddinter_id = a.ddinter_id WHERE a.alias LIKE ? LIMIT 8",
            (f"%{ql}%",),
        )
    if not candidates:
        _merge(
            "SELECT d.* FROM drug d WHERE d.name_cn LIKE ? OR lower(d.name_en) LIKE ? LIMIT 8",
            (f"%{q}%", f"%{ql}%"),
        )
    return None, list(candidates.values())


def search_drugs(conn, query: str, limit: int = 10) -> list:
    """搜索框模糊搜索：中文/英文/拼音，按相关度排序。"""
    q = (query or "").strip()
    if not q:
        # 空查询 -> 常用慢病药物（有中文注释的 curated 药）优先
        return conn.execute(
            "SELECT * FROM drug WHERE name_cn IS NOT NULL ORDER BY name_en LIMIT ?",
            (limit,),
        ).fetchall()

    ql = q.lower()
    scored: dict[str, int] = {}
    rows: dict[str, object] = {}

    def _add(sql: str, params: tuple, score: int):
        for r in conn.execute(sql, params).fetchall():
            did = r["ddinter_id"]
            rows[did] = r
            if score > scored.get(did, 0):
                scored[did] = score

    _add("SELECT * FROM drug WHERE name_cn = ?", (q,), 100)          # 中文精确
    _add("SELECT * FROM drug WHERE name_cn LIKE ?", (q + "%",), 90)  # 中文前缀
    _add("SELECT * FROM drug WHERE lower(name_en) = ?", (ql,), 85)   # 英文精确(不区分大小写)
    _add("SELECT * FROM drug WHERE lower(name_en) LIKE ?", (ql + "%",), 75)
    _add(  # 别名精确（拼音首字母/同义词）
        "SELECT d.* FROM alias a JOIN drug d ON d.ddinter_id = a.ddinter_id WHERE a.alias = ?",
        (ql,), 70,
    )
    _add("SELECT * FROM drug WHERE name_cn LIKE ?", (f"%{q}%",), 60)  # 中文包含
    _add(  # 拼音前缀
        "SELECT d.* FROM alias a JOIN drug d ON d.ddinter_id = a.ddinter_id WHERE a.alias LIKE ?",
        (ql + "%",), 55,
    )
    _add("SELECT * FROM drug WHERE lower(name_en) LIKE ?", (f"%{ql}%",), 50)  # 英文包含

    ranked = sorted(scored, key=lambda did: (-scored[did], rows[did]["name_en"].lower()))
    return [rows[did] for did in ranked[:limit]]
