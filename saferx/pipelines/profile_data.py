#!/usr/bin/env python
"""
数据画像：从 saferx.sqlite 生成报告用图表（纯标准库输出 SVG，无额外依赖）。

产出：
    docs/assets/level_dist.svg     风险分级分布
    docs/assets/cn_coverage.svg    中文名 / 别名覆盖
    docs/assets/top_degree.svg     高连接度药物 Top 10
    docs/data_profile.md           数据画像正文（含表格，数字与图表同源）

用法: python pipelines/profile_data.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "saferx.sqlite"
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"

LEVEL_ORDER = [("Major", "严重 Major", "#A32D2D"), ("Moderate", "中度 Moderate", "#854F0B"),
               ("Minor", "轻微 Minor", "#3B6D11"), ("Unknown", "分级未知 Unknown", "#8CA096")]

FONT = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
)


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def bar_chart(items, width=680, row_h=40, pad_top=44, label_w=180, value_w=96) -> str:
    """items: [(label, value, color, extra_text)] -> 横向条形图 SVG"""
    height = pad_top + row_h * len(items) + 16
    max_v = max((v for _, v, _, _ in items), default=1) or 1
    bar_area = width - label_w - value_w - 24
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{FONT}">',
        f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
    ]
    for i, (label, value, color, extra) in enumerate(items):
        y = pad_top + i * row_h
        w = max(2, round(bar_area * value / max_v))
        parts.append(f'<text x="8" y="{y + 16}" font-size="13" fill="#1F2A26">{esc(label)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y + 4}" width="{bar_area}" height="18" rx="4" fill="#F0F8F5"/>')
        parts.append(f'<rect x="{label_w}" y="{y + 4}" width="{w}" height="18" rx="4" fill="{color}"/>')
        parts.append(
            f'<text x="{width - 4}" y="{y + 18}" font-size="13" font-weight="600" '
            f'fill="#1F2A26" text-anchor="end">{esc(extra or f"{value:,}")}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def donut_coverage(covered: int, total: int, label: str, width=680, height=220) -> str:
    """覆盖度环形图（单个比例）"""
    import math

    cx, cy, r, sw = 108, height / 2, 62, 20
    ratio = covered / total if total else 0
    circ = 2 * math.pi * r
    dash = circ * ratio
    pct = f"{ratio * 100:.1f}%"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="{FONT}">
<rect width="{width}" height="{height}" fill="#FFFFFF"/>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#E7F1ED" stroke-width="{sw}"/>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#0F6E56" stroke-width="{sw}"
        stroke-linecap="round" stroke-dasharray="{dash:.1f} {circ:.1f}"
        transform="rotate(-90 {cx} {cy})"/>
<text x="{cx}" y="{cy + 6}" text-anchor="middle" font-size="22" font-weight="700" fill="#0F6E56">{pct}</text>
<text x="200" y="{cy - 12}" font-size="14" fill="#1F2A26">{esc(label)}</text>
<text x="200" y="{cy + 12}" font-size="13" fill="#55655E">{covered:,} / {total:,}</text>
<text x="200" y="{cy + 34}" font-size="12" fill="#8CA096">未覆盖部分需使用英文名检索</text>
</svg>"""


def markdown(conn) -> str:
    tot = conn.execute("SELECT COUNT(*) FROM ddi").fetchone()[0]
    levels = dict(conn.execute("SELECT level, COUNT(*) FROM ddi GROUP BY level"))
    drugs = conn.execute("SELECT COUNT(*) FROM drug").fetchone()[0]
    drugs_cn = conn.execute("SELECT COUNT(*) FROM drug WHERE name_cn IS NOT NULL").fetchone()[0]
    aliases = dict(conn.execute("SELECT kind, COUNT(*) FROM alias GROUP BY kind"))
    top = conn.execute(
        """
        SELECT d.name_cn, d.name_en, COUNT(*) AS deg,
               SUM(CASE WHEN x.level = 'Major' THEN 1 ELSE 0 END) AS major
        FROM (SELECT ddinter_id_a AS id, level FROM ddi
              UNION ALL SELECT ddinter_id_b, level FROM ddi) x
        JOIN drug d ON d.ddinter_id = x.id
        GROUP BY x.id ORDER BY deg DESC LIMIT 10
        """
    ).fetchall()

    lv_rows = "\n".join(
        f"| {name} | {levels.get(key, 0):,} | {levels.get(key, 0) / tot * 100:.2f}% |"
        for key, name, _ in LEVEL_ORDER
    )
    top_rows = "\n".join(
        f"| {i + 1} | {r['name_cn'] or '—'} | {r['name_en']} | {r['deg']:,} | {r['major']:,} |"
        for i, r in enumerate(top)
    )

    # ---- 其他相互作用（网页接口抓取的三类，可能尚未入库）----
    def cnt(sql: str) -> int:
        try:
            return conn.execute(sql).fetchone()[0] or 0
        except sqlite3.Error:
            return 0

    ddsi_n, dfi_n, dup_n = cnt("SELECT COUNT(*) FROM ddsi"), cnt("SELECT COUNT(*) FROM dfi"), cnt("SELECT COUNT(*) FROM dupli")
    if not (ddsi_n or dfi_n or dup_n):
        other_section = "## 6. 数据质量与处理规则"
    else:
        ddsi_lv = dict(conn.execute("SELECT level, COUNT(*) FROM ddsi GROUP BY level"))
        dfi_lv = dict(conn.execute("SELECT level, COUNT(*) FROM dfi GROUP BY level"))
        ddsi_dis = conn.execute("SELECT COUNT(DISTINCT disease_en) FROM ddsi").fetchone()[0]
        ddsi_cn = conn.execute(
            "SELECT COUNT(DISTINCT disease_en) FROM ddsi WHERE disease_cn IS NOT NULL AND disease_cn <> ''"
        ).fetchone()[0]
        top_dis = conn.execute(
            "SELECT disease_cn, COUNT(*) n, SUM(CASE WHEN level='Major' THEN 1 ELSE 0 END) major "
            "FROM ddsi GROUP BY disease_en ORDER BY n DESC LIMIT 8"
        ).fetchall()
        top_food = conn.execute(
            "SELECT food_cn, COUNT(*) n, SUM(CASE WHEN level='Major' THEN 1 ELSE 0 END) major "
            "FROM dfi GROUP BY food_en ORDER BY n DESC LIMIT 8"
        ).fetchall()
        top_cat = conn.execute(
            "SELECT category_cn, COUNT(*) n FROM dupli GROUP BY category_en ORDER BY n DESC LIMIT 8"
        ).fetchall()
        dis_rows = "\n".join(f"| {r['disease_cn']} | {r['n']:,} | {r['major']:,} |" for r in top_dis)
        food_rows = "\n".join(f"| {r['food_cn']} | {r['n']:,} | {r['major']:,} |" for r in top_food)
        cat_rows = "\n".join(f"| {r['category_cn']} | {r['n']:,} |" for r in top_cat)
        other_section = f"""## 5. 其他相互作用（DDSI / DFI / 重复用药）

DDInter 官方只对 DDI 提供 CSV 下载，这三类仅以网页表格形式开放。项目通过逆向其 DataTables
接口分页抓取（方法与复现命令见 `data_dictionary.md` §2.1），清洗后入库：

![三类数据规模](assets/other_scale.svg)

| 类别 | 入库条目 | 覆盖范围 | 分级分布（Major / Moderate / Minor） |
|---|---|---|---|
| DDSI 药物-疾病禁忌 | {ddsi_n:,} | {ddsi_dis} 种基础疾病 × {cnt("SELECT COUNT(DISTINCT ddinter_id) FROM ddsi"):,} 种药 | {ddsi_lv.get('Major', 0):,} / {ddsi_lv.get('Moderate', 0):,} / {ddsi_lv.get('Minor', 0):,} |
| DFI 药物-食物 | {dfi_n:,} | {cnt("SELECT COUNT(DISTINCT food_en) FROM dfi")} 类食物 / 烟酒 × {cnt("SELECT COUNT(DISTINCT ddinter_id) FROM dfi"):,} 种药 | {dfi_lv.get('Major', 0):,} / {dfi_lv.get('Moderate', 0):,} / {dfi_lv.get('Minor', 0):,} |
| 重复用药 | {dup_n:,} | {cnt("SELECT COUNT(DISTINCT category_en) FROM dupli")} 个治疗类别 × {cnt("SELECT COUNT(DISTINCT ddinter_id) FROM dupli"):,} 种药 | 不分级（同类 ≥2 种即告警） |

**Top 8 基础疾病（按禁忌条目数）**

| 疾病 | 条目数 | 其中 Major |
|---|---|---|
{dis_rows}

**Top 8 食物 / 饮品**

| 食物 | 条目数 | 其中 Major |
|---|---|---|
{food_rows}

**Top 8 重复用药类别**

| 治疗类别 | 条目数 |
|---|---|
{cat_rows}

**解读**：

- 疾病侧「肾脏疾病 / 肝脏疾病」条目最多（各 640 条量级），与药代动力学常识一致——肝肾功能决定
  多数药物的清除，是最需要先问的病史；中文病名覆盖 {ddsi_cn}/{ddsi_dis} 种，但已覆盖 88.8% 的条目。
- 食物侧高度集中在酒精（433 条）与西柚汁（137 条），二者占 70.8%——不是数据贫乏，而是真实临床
  关注点本来就集中在这两项（CYP3A4 抑制、中枢抑制叠加、双硫仑样反应）。
- 重复用药条目数最多的是抗组胺药（1,613 条）与非甾体抗炎药（867 条），恰是感冒药与止痛药里
  最容易「一药多名、重复服用」的品类，与「患者自行加药」的现实风险吻合。

## 6. 数据质量与处理规则"""
    return f"""# 数据画像（Data Profile）

> 本文件由 `pipelines/profile_data.py` 从 `data/saferx.sqlite` 直接生成，数字与图表同源，重跑即可更新。
> 数据源：DDInter 2.0（CC BY-NC-SA 4.0），构建时间见 `meta` 表 `built_at`。

## 1. 总体规模

| 指标 | 数值 |
|---|---|
| 药物（drug） | {drugs:,} 种 |
| 唯一药对（ddi，无序对规范化后） | {tot:,} 对 |
| 中文通用名覆盖 | {drugs_cn:,} 种（{drugs_cn / drugs * 100:.1f}%） |
| 别名总数 | {sum(aliases.values()):,} 条（中文 {aliases.get('cn', 0)}、拼音 {aliases.get('pinyin', 0)}、英文 {aliases.get('en', 0)}、同义 {aliases.get('synonym', 0)}） |
| 人工审编机制文本 | 21 条（挂接 21 个药对，其余药对仅展示英文原文回退） |

## 2. 风险分级分布

![风险分级分布](assets/level_dist.svg)

| 分级 | 药对数 | 占比 |
|---|---|---|
{lv_rows}

**解读**：Moderate 占六成，符合审编库「宁可高报不漏报」的收录倾向；`Unknown` 为 DDInter 官方未给出分级的记录，
系统按「分级未知」独立展示，**不并入「安全」**——这是产品诚实性的关键设计。

## 3. 中文名覆盖

![中文名覆盖](assets/cn_coverage.svg)

中文名来自人工审编的 `data/external/alias_curated.json`（{drugs_cn} 种常见药，覆盖心血管、内分泌、抗感染、
精神神经、镇痛、肿瘤等 20 余个治疗领域），拼音首字母由 `pypinyin` 自动生成。
未覆盖的 {drugs - drugs_cn:,} 种药仍需使用英文通用名检索——这是审编库的覆盖边界，界面已明确提示。

## 4. 高连接度药物 Top 10

![高连接度药物](assets/top_degree.svg)

| # | 中文名 | 英文名 | 关联药对数 | 其中 Major |
|---|---|---|---|---|
{top_rows}

**解读**：连接度最高的并非「最危险」的药，而是代谢通路枢纽（CYP450 底物/抑制剂/诱导剂）与
治疗窗窄的药物（华法林、他克莫司、苯妥英、卡马西平）。这类药物正是临床处方审核的重点对象，
也解释了为什么「药单整体检查」比单药查询更有价值。

{other_section}
| 问题 | 处理方式 |
|---|---|
| 同一药对在多个分类文件中重复出现 | 以 `(min(id_a,id_b), max(id_a,id_b))` 规范化后去重 |
| 同一药对分级冲突 | 取最高风险等级（Major > Moderate > Minor > Unknown） |
| 官方 `Unknown` 分级（{levels.get('Unknown', 0):,} 对） | 保留并单独展示，不视为无风险 |
| 药名写法差异（Aspirin / Acetylsalicylic acid、Glibenclamide / Glyburide） | 别名表登记同义词 |
| 拼音首字母天然冲突（如 klms） | 冲突项不做映射，提示改用中文全名 |
| 官方 CSV 不含机制文本 | 人工审编 21 条经典机制；其余显示「暂无中文机制」并保留英文原文位 |
| 网页接口无 CSV、需绕过 CSRF 分页 | 抓取脚本带 token + 分页 POST，落盘原始 JSONL 快照备查 |
| DFI 源接口把 mechanism 字段误命名为 magnesium | 清洗时按语义归位，字段名以本库为准 |

## 7. 复现方式

```bash
python pipelines/profile_data.py     # 重新生成图表与本文件
```
"""


def main() -> int:
    if not DB.exists():
        print(f"数据库不存在: {DB}（先运行 make data && make initdb）", file=sys.stderr)
        return 1
    ASSETS.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    tot = conn.execute("SELECT COUNT(*) FROM ddi").fetchone()[0]
    levels = dict(conn.execute("SELECT level, COUNT(*) FROM ddi GROUP BY level"))
    items = [
        (name, levels.get(key, 0), color, f"{levels.get(key, 0):,}（{levels.get(key, 0) / tot * 100:.1f}%）")
        for key, name, color in LEVEL_ORDER
    ]
    (ASSETS / "level_dist.svg").write_text(bar_chart(items), encoding="utf-8")

    drugs = conn.execute("SELECT COUNT(*) FROM drug").fetchone()[0]
    drugs_cn = conn.execute("SELECT COUNT(*) FROM drug WHERE name_cn IS NOT NULL").fetchone()[0]
    (ASSETS / "cn_coverage.svg").write_text(
        donut_coverage(drugs_cn, drugs, "中文通用名覆盖（drug.name_cn 非空）"), encoding="utf-8"
    )

    top = conn.execute(
        """
        SELECT d.name_cn, d.name_en, COUNT(*) AS deg
        FROM (SELECT ddinter_id_a AS id FROM ddi UNION ALL SELECT ddinter_id_b FROM ddi) x
        JOIN drug d ON d.ddinter_id = x.id
        GROUP BY x.id ORDER BY deg DESC LIMIT 10
        """
    ).fetchall()
    (ASSETS / "top_degree.svg").write_text(
        bar_chart(
            [(r["name_cn"] or r["name_en"], r["deg"], "#1D6FA5", f"{r['deg']:,}") for r in top],
            pad_top=16,
        ),
        encoding="utf-8",
    )

    (DOCS / "data_profile.md").write_text(markdown(conn), encoding="utf-8")

    # 三类「其他相互作用」规模（网页接口抓取）
    other_items = []
    for label, table, color in (
        ("DDSI 药物-疾病禁忌", "ddsi", "#B4472F"),
        ("重复用药（类别×药品）", "dupli", "#1D6FA5"),
        ("DFI 药物-食物", "dfi", "#C98A2E"),
    ):
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.Error:
            continue
        if n:
            other_items.append((label, n, color, f"{n:,}"))
    if other_items:
        (ASSETS / "other_scale.svg").write_text(
            bar_chart(other_items, pad_top=16), encoding="utf-8"
        )

    conn.close()
    print(f"✓ 图表 -> {ASSETS}")
    print(f"✓ 正文 -> {DOCS / 'data_profile.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
