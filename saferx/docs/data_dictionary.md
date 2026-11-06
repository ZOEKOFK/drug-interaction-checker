# 数据字典（Data Dictionary）

> 适用范围：`data/saferx.sqlite`（由 `pipelines/` 下的四个脚本从 DDInter 2.0 官方 CSV 重建）。
> 数据许可：DDInter 2.0 采用 **CC BY-NC-SA 4.0**，本项目为课程作业（非商用），页脚与「关于」页已署名。

## 1. 数据来源

| 项目 | 内容 |
|---|---|
| 原始数据 | DDInter 2.0（<https://ddinter2.scbdd.com/>，Nucleic Acids Research 2025） |
| 下载方式 | `pipelines/download_ddinter.py`，按药名首字母分文件，共 **14 个 CSV**（A/B/C/D/G/H/J/L/M/N/P/R/S/V） |
| 原始规模 | 507,655 行（跨文件重复计入） |
| 清洗后 | **1,971 种药物、234,981 个唯一药对** |
| 官方对照 | 官方宣称 2,310 种药物 / 302,516 条 DDI；差异来自跨分类重复、无效记录与未映射药物 |

> 注意：官方下载页只列出 8 个链接（A/B/D/H/L/P/R/V），其余 6 个（C/G/J/M/N/S）需按 URL 规则探测，
> 遗漏会少约 35% 数据——`download_ddinter.py` 已内置完整 14 个文件名。

## 2. 管道四步

| 步骤 | 脚本 | 输入 → 输出 | 关键处理 |
|---|---|---|---|
| ① 下载 | `download_ddinter.py` | 官网 CSV → `data/raw/` | 断点重试、行数与文件大小校验 |
| ② 清洗 | `clean_ddinter.py` | `raw/*.csv` → `data/processed/drugs.csv`、`ddi.csv` | 无序对规范化、去重、分级保守聚合、列白名单 |
| ③ 别名 | `build_alias_table.py` | `drugs.csv` + `external/alias_curated.json` → `alias.csv` | 英文名自动全量 + 中文/拼音/同义词人工审编 |
| ④ 建库 | `init_db.py` | processed CSV + `external/*.json` → `saferx.sqlite` | 建表建索引、灌数据、写 `meta` 版本信息 |

## 3. 表结构总览

| 表 | 行数 | 作用 |
|---|---|---|
| `drug` | 1,971 | 药品主表 |
| `ddi` | 234,981 | 药对关系表（无序对唯一） |
| `mechanism` | 21 | 人工审编机制 / 处置文本 |
| `alias` | 5,244 | 别名映射（中文 / 英文 / 拼音 / 同义词） |
| `template` | 4 | 慢病演示模板药单 |
| `meta` | 6 | 数据版本与规模元信息 |

## 4. 字段字典

### 4.1 `drug` 药品主表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `ddinter_id` | TEXT | PK | DDInter 原始 ID，如 `DDInter1951` |
| `name_en` | TEXT | NOT NULL，有索引 | 官方英文名（含限定词时会带括号，如 `Acyclovir (topical)`） |
| `name_cn` | TEXT | 可空 | 中文通用名，仅人工审编的 366 种有值 |
| `atc_code` / `atc_name` | TEXT | 可空 | **当前恒为 NULL**：官方 CSV 不含 ATC，早期按文件首字母推断的分类已废弃以免误导 |
| `category` | TEXT | 可空 | 治疗类别（如「抗凝药」），来自别名表人工标注 |

### 4.2 `ddi` 药对关系表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | INTEGER | PK | 自增 |
| `ddinter_id_a` | TEXT | NOT NULL，外键 | 较小 ID |
| `ddinter_id_b` | TEXT | NOT NULL，外键 | 较大 ID |
| `level` | TEXT | CHECK IN (`Major`,`Moderate`,`Minor`,`Unknown`) | 风险分级；**`Unknown` 为官方未标注严重度** |
| `mechanism_id` | INTEGER | 外键，可空 | 命中人工审编机制时非空（当前仅 21 行） |
| `source_id` | TEXT | NOT NULL | 溯源标识，格式 `DDInter2.0:{id_a}/{id_b}` |

唯一索引 `idx_pair(ddinter_id_a, ddinter_id_b)` 是「n=10 共 45 组合 < 5ms」的前提。

### 4.3 `mechanism` 机制文本表

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER PK | — |
| `text_en` | TEXT | 英文机制原文（来自 DDInter 网页说明的审编摘要） |
| `text_cn` | TEXT | 中文机制摘要（人工审编） |
| `management_cn` | TEXT | 中文处置建议（避免联用 / 监测指标 / 替代方案） |

> 官方 CSV **不含**机制文本，这 21 条来自 `data/external/mechanism_curated.json` 人工审编，
> 覆盖方案 §9 的 7 个经典案例及其相邻组合。其余药对诚实回退为「暂无中文机制」。

### 4.4 `alias` 别名表

| 字段 | 类型 | 说明 |
|---|---|---|
| `alias` | TEXT PK | 别名原文（中文名保留原样，英文/拼音统一小写） |
| `kind` | TEXT | `cn` 中文通用名 / `en` 英文名 / `pinyin` 拼音首字母 / `synonym` 同义词或商品名 |
| `ddinter_id` | TEXT | 指向 `drug` |

**冲突处理**：同一别名指向两种药时**不写入**（避免把 A 药的风险算到 B 药头上），
构建脚本会打印冲突清单。当前 5 组拼音天然冲突：`klms`（克拉霉素/克林霉素）、`lglt`、`lst`（氯沙坦/利塞膦酸）、
`pftt`（普伐他汀/匹伐他汀）、`ys`。

### 4.5 `template` 演示模板

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | `tpl-1` … `tpl-4` |
| `name` | TEXT | 模板名（如「高血压 + 房颤」） |
| `desc_text` | TEXT | 场景说明 |
| `expected` | TEXT | 预期演示效果（答辩时可对照） |
| `drugs_json` | TEXT | DDInter ID 数组的 JSON 字符串 |

### 4.6 `meta` 元信息

| key | 示例值 |
|---|---|
| `source` | `DDInter 2.0 (https://ddinter2.scbdd.com/, CC BY-NC-SA 4.0)` |
| `built_at` | `2026-11-06 23:55:56` |
| `drugs` / `ddi_pairs` / `mechanisms` / `aliases` | 规模快照 |

## 5. 清洗规则（可复现）

| 规则 | 实现 |
|---|---|
| 无序对规范化 | `(min(id_a,id_b), max(id_a,id_b))`，保证一次查询命中唯一索引 |
| 跨文件去重 | 同一规范化药对只保留一行 |
| 分级冲突聚合 | 取最高等级：Major > Moderate > Minor > Unknown（宁可高报不漏报） |
| 非法分级 | 丢弃并计入清洗日志 |
| 文件首字母≠ATC | 早期按文件字母推断的「ATC 分类」已移除，避免把 A 文件当成「消化系统用药」的误导 |

## 6. 别名维护流程（新增一种中文药名）

1. 在 `data/external/alias_curated.json` 追加一条：

   ```json
   { "name_en": "Bisoprolol", "name_cn": "比索洛尔", "category": "β受体阻滞剂", "synonyms": [] }
   ```

   - `name_en` 必须与库内 `drug.name_en` **完全一致**（大小写不敏感）；不确定时先查：
     `sqlite3 data/saferx.sqlite "select name_en from drug where name_en like '%soprolol%'"`
   - `pinyin` 字段可省略，构建时用 `pypinyin` 自动生成首字母。

2. 重建并验证：

   ```bash
   make alias && make initdb    # 重建 alias 表与整库
   make test                    # 31 个用例需保持全绿
   ```

3. 验证检索：`curl "http://127.0.0.1:8000/api/drugs/search?q=比索洛尔"`

**写入口径**：中文名采用《中国药品通用名称》通用名，不收录商品名；商品名/别名放 `synonyms`。
同一中文名不得指向两种药（构建脚本会跳过冲突项）。

## 7. 覆盖边界（诚实清单）

| 边界 | 现状 | 影响 |
|---|---|---|
| 中文名 | 366 / 1,971（18.6%） | 其余药需英文检索 |
| 机制文本 | 21 / 234,981 | 绝大多数药对无中文机制 |
| 分级未知 | 42,415 对（18.05%） | 独立展示，不并入「安全」 |
| 未收录药 | DDInter 未收录的国产药（如格列齐特、多潘立酮） | 检索不到，界面提示「查无此药」 |
| DFI / DDSI / 重复用药 | 未入库 | 官网未开放 CSV 下载，需另选数据源（规划项） |
