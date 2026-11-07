# 接口文档（API）

> 基础地址：`http://127.0.0.1:8000`　交互式文档：`/docs`（Swagger UI）、`/redoc`
> 开发模式下前端 Vite 将 `/api` 代理到 `8000`，页面代码无需区分环境。
> 全部接口只读、无账号体系、不落库药单——服务端不保存任何用户输入。

## 0. 通用约定

| 项 | 说明 |
|---|---|
| 编码 | UTF-8，`Content-Type: application/json` |
| 错误 | 4xx/5xx 返回 `{"detail": "..."}`（FastAPI 默认结构） |
| 药名入参 | 支持中文通用名 / 英文名 / 拼音首字母 / DDInter ID 四类写法 |
| 单张药单上限 | 20 种（超过返回 422，由 Pydantic 校验） |
| 基础疾病入参 | `diseases` 传**英文规范病名**（与 `ddsi.disease_en` 一致），上限 20 个；前端选择器限制 8 个 |
| 免责 | 响应仅用于教学与科普，`coverage_note` 会随结果返回覆盖提示 |

## 1. `GET /api/health` — 健康检查与数据规模

前端首页/关于页的规模数字全部来自此接口，避免硬编码官方口径。

```bash
curl -s http://127.0.0.1:8000/api/health
```

```json
{
  "status": "ok",
  "db_path": "F:\\Medical Artificial Intelligence\\saferx\\data\\saferx.sqlite",
  "data_version": "DDInter 2.0 · 1971 种药物 · 234,981 条 DDI · 构建于 2026-11-07 00:49:05",
  "stats": {
    "drugs": 1971,
    "drugs_with_cn": 366,
    "ddi_pairs": 234981,
    "mechanisms": 21,
    "mechanisms_covered_pairs": 21,
    "aliases": 5244,
    "aliases_cn": 367,
    "templates": 4,
    "ddsi_rows": 8009,
    "dfi_rows": 805,
    "dupli_rows": 5663,
    "ddsi_diseases": 459,
    "ddsi_cn_covered": 7111,
    "dfi_foods": 29,
    "dupli_categories": 95,
    "levels": { "Major": 39082, "Moderate": 143748, "Minor": 9736, "Unknown": 42415 },
    "built_at": "2026-11-07 00:49:05",
    "source": "DDInter 2.0 (https://ddinter2.scbdd.com/, CC BY-NC-SA 4.0)"
  }
}
```

`ddsi_*` / `dfi_*` / `dupli_*` 为官方网页接口抓取的三类「其他相互作用」规模（见 `data_dictionary.md` §2.1），
`ddsi_cn_covered` 是已配到中文病名的条目数（7111 / 8009 ≈ 88.8%，其余回退英文病名）。

数据库缺失时返回 `503 {"status": "db_missing", "hint": "请先运行 make data && make initdb"}`。

## 2. `POST /api/check` — 药单检查（核心）

请求：

```json
{
  "medications": ["华法林", "阿司匹林", "二甲双胍"],
  "diseases": ["Kidney Diseases", "Hypertension"]
}
```

`diseases` 可省略（默认 `[]`），省略时跳过「药物-疾病禁忌」这一项，并在 `other_note` 里说明。

响应（节选，真实的 3 药样例）：

```json
{
  "unresolved": [],
  "pairs": [
    {
      "drug_a": { "ddinter_id": "DDInter1951", "name_cn": "华法林", "name_en": "Warfarin", "atc": null, "category": "抗凝药" },
      "drug_b": { "ddinter_id": "DDInter20", "name_cn": "阿司匹林", "name_en": "Acetylsalicylic acid", "atc": null, "category": "抗血小板药" },
      "level": "Major",
      "level_cn": "严重",
      "mechanism_cn": "华法林抑制凝血因子合成，阿司匹林抑制血小板功能，抗凝与抗血小板作用叠加，出血风险显著升高。",
      "mechanism_en": "The risk of bleeding may be increased when warfarin is combined with acetylsalicylic acid.",
      "management": "避免常规联用；如确需抗栓联合治疗，应由医师评估获益与风险，密切监测 INR 及出血征象。",
      "source_id": "DDInter2.0:DDInter1951/DDInter20"
    }
  ],
  "unrecorded_pairs": [],
  "summary": { "Major": 1, "Moderate": 0, "Minor": 0, "Unknown": 0, "overall": "red" },
  "checked_at": "2026-11-06T17:22:41+00:00",
  "data_version": "DDInter 2.0 · 1971 种药物 · 234,981 条 DDI · 构建于 2026-11-07 00:49:05",
  "coverage_note": "当前药单所有组合均有收录记录；「分级未知」条目为官方未标注严重度的记录，同样不代表安全。",

  "diseases_checked": ["Kidney Diseases", "Hypertension"],
  "disease_risks": [
    {
      "drug": { "ddinter_id": "DDInter1951", "name_cn": "华法林", "name_en": "Warfarin", "category": "抗凝药" },
      "disease_en": "Hypertension",
      "disease_cn": "高血压",
      "level": "Major",
      "level_cn": "严重",
      "summary_cn": "患有「高血压」时使用 华法林 属严重风险，需由医师评估后决定是否使用。",
      "description_en": "In general, the use of oral anticoagulants is contraindicated in patients with malignant or severe, uncontrolled hypertension. ...",
      "reference_text": "Hylek EM, Singer DE \"Risk factors for intracranial hemorrhage in outpatients taking warfarin.\" Ann Intern Med 120 (1994): 897-902|..."
    }
  ],
  "food_risks": [
    {
      "drug": { "ddinter_id": "DDInter1164", "name_cn": "二甲双胍", "name_en": "Metformin", "category": "降糖药" },
      "food_en": "alcohol",
      "food_cn": "酒精",
      "level": "Major",
      "level_cn": "严重",
      "mechanism_cn": "其他",
      "summary_cn": "与「酒精」同服可能产生严重风险（机制：其他）。",
      "interaction_en": "Alcohol can potentiate the effect of metformin on lactate metabolism and increase the risk of lactic acidosis. ...",
      "management_en": "Metformin should be taken with meals, and excessive alcohol intake should be avoided during treatment. ...",
      "reference_text": "\"Product Information. Glucophage (metformin).\" Bristol-Myers Squibb (2001):|..."
    }
  ],
  "duplications": [],
  "other_summary": {
    "disease": { "Major": 2, "Moderate": 1, "Minor": 0 },
    "food": { "Major": 1, "Moderate": 3, "Minor": 0 },
    "duplication_groups": 0,
    "overall": "red"
  },
  "other_note": "",
  "overall_all": "red"
}
```

### 2.1 DDI 字段说明

| 字段 | 说明 |
|---|---|
| `pairs[]` | 每个有收录记录的药对一条，按风险等级降序 |
| `level` | `Major` / `Moderate` / `Minor` / `Unknown` |
| `summary.overall` | `red`（含 Major）/ `orange`（含 Moderate）/ `green`（仅 Minor）/ `gray`（无记录或仅 Unknown） |
| `unrecorded_pairs[]` | 库内**无记录**的组合——不代表安全，前端单独展示 |
| `unresolved[]` | 药名无法归一化的输入，附 `candidates` 候选供用户确认 |

### 2.2 「其他相互作用」字段说明

三类数据来源与 DDI 不同（官方网页接口，非 CSV），故单独成块返回，不混入 `pairs`。

| 字段 | 说明 |
|---|---|
| `diseases_checked` | 本次实际参与检查的疾病英文名（回显，便于前端标注） |
| `disease_risks[]` | 药物 × 基础疾病禁忌。`summary_cn` 为模板生成的**中文结论**；`description_en` / `reference_text` 保留官方原文，中文不做二次改写 |
| `food_risks[]` | 药物 × 食物（含烟酒、西柚汁等 29 类）。`mechanism_cn` 为机制标签（吸收/代谢/协同作用/拮抗作用/排泄/分布/其他） |
| `duplications[]` | 治疗重复：同一治疗类别下出现 ≥2 种药即按类别聚合成一组，`drugs[]` 列出组内药品 |
| `other_summary` | 三类各自的分级计数 + `duplication_groups`（重复用药组数）+ 合并后的 `overall` |
| `other_note` | 空则正常；未传 `diseases` 时为「已跳过药物-疾病禁忌检查」，传了但无命中时为「未收录不代表安全」 |
| `overall_all` | DDI 与三类其他相互作用的**合并最高等级**（保守聚合：取更严重者），前端顶部横幅读此字段 |

> 保守聚合原则：任一类判 `red` 即整体 `red`，宁可高报不漏报。这也是"未收录不代表安全"在接口层的体现。

**治疗重复样例**（`{"medications":["阿托伐他汀","瑞舒伐他汀","氨氯地平","硝苯地平"]}`）：

```json
{
  "category_en": "calcium channel blockers",
  "category_cn": "钙通道阻滞剂",
  "drugs": [
    { "ddinter_id": "DDInter79", "name_cn": "氨氯地平", "name_en": "Amlodipine", "category": "钙通道阻滞剂" },
    { "ddinter_id": "DDInter1291", "name_cn": "硝苯地平", "name_en": "Nifedipine", "category": "钙通道阻滞剂" }
  ],
  "summary_cn": "药单中有 2 种药物同属「钙通道阻滞剂」类别（氨氯地平、硝苯地平），构成治疗重复，建议核对是否为重复用药。",
  "warning_en": "The recommended maximum number of medicines in the 'calcium channel blockers' category to be taken concurrently is usually one. ...",
  "note_en": "Note: In certain circumstances, the benefits of taking this combination of drugs may outweigh any risks. ..."
}
```

## 3. `GET /api/drugs/search` — 药名模糊搜索

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `q` | string | `""` | 空值时返回有中文名的常用药 |
| `limit` | int | 10 | 1–50 |

```bash
curl -s "http://127.0.0.1:8000/api/drugs/search?q=比索洛尔&limit=3"
```

```json
[{ "ddinter_id": "DDInter…", "name_cn": "比索洛尔", "name_en": "Bisoprolol", "atc": null, "category": "β受体阻滞剂" }]
```

排序相关度：中文精确 100 > 中文前缀 90 > 英文精确 85 > 英文前缀 75 > 别名精确 70（拼音/同义词）> 包含匹配 50–60。

## 4. `GET /api/drugs/templates` — 慢病示例模板

```bash
curl -s http://127.0.0.1:8000/api/drugs/templates
```

```json
[{
  "id": "tpl-1",
  "name": "高血压 + 房颤",
  "desc": "慢病共病典型组合：抗凝 + 抗心律失常 + 降压 + 利尿",
  "expected": "两条 Major 红卡",
  "drugs": [{ "ddinter_id": "DDInter1951", "name_cn": "华法林", "name_en": "Warfarin" }]
}]
```

## 4.1 `GET /api/drugs/diseases` — 基础疾病候选（DDSI）

供前端疾病选择器使用，按收录条目数取常见病，天然把「糖尿病」「心力衰竭」这类高频共病排在前面。

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `limit` | int | 80 | 10–200，超出返回 422 |

```bash
curl -s "http://127.0.0.1:8000/api/drugs/diseases?limit=3"
```

```json
[
  { "name_en": "Kidney Diseases", "name_cn": "肾脏疾病", "count": 641, "major": 225 },
  { "name_en": "Liver Diseases", "name_cn": "肝脏疾病", "count": 638, "major": 271 },
  { "name_en": "Diabetes Mellitus", "name_cn": "糖尿病", "count": 185, "major": 33 }
]
```

- `count`：该疾病下的禁忌条目总数；`major`：其中严重级条目数（前端用于标注「高警示」）
- `name_en` 即 `POST /api/check` 的 `diseases` 入参
- `name_cn` 未收录时回退为英文名（459 种疾病中 150 种已配中文，覆盖 88.8% 条目）

## 5. `GET /api/graph` — 药单关系子图

| 参数 | 说明 |
|---|---|
| `ids` | 逗号分隔的 DDInter ID 或药名（自动归一化，无法识别的项跳过） |

```bash
curl -s "http://127.0.0.1:8000/api/graph?ids=华法林,胺碘酮,地高辛"
```

```json
{
  "nodes": [{ "id": "DDInter1951", "name": "华法林", "category": "抗凝药", "maxLevel": "Major" }],
  "links": [{ "source": "DDInter1951", "target": "DDInter76", "value": 3, "level": "Major" }]
}
```

`value` 为等级数值（Major=3 / Moderate=2 / Minor=1 / Unknown=0），可直接映射 ECharts 线宽与颜色。

## 6. `POST /api/report` — 汇总报告数据

与 `/api/check` 同构（供报告页/导出使用），另支持 `GET /api/report?ids=a,b,c`。
导出的 HTML 报告由前端 `CheckResultView` 在浏览器内生成（匿名、可打印），服务端不留存。

## 7. `POST /api/lab/extract` — 文献 DDI 抽取

```bash
curl -s -X POST http://127.0.0.1:8000/api/lab/extract \
  -H "Content-Type: application/json" \
  -d '{"text":"患者长期口服华法林抗凝，近期因房颤加用胺碘酮。"}'
```

```json
{
  "engine": "dict",
  "entities": [
    { "text": "华法林", "start": 5, "end": 8, "source": "dict",
      "drug": { "name_cn": "华法林", "name_en": "Warfarin" } },
    { "text": "胺碘酮", "start": 17, "end": 20, "source": "dict",
      "drug": { "name_cn": "胺碘酮", "name_en": "Amiodarone" } }
  ],
  "unknown_entities": [],
  "triples": [{ "drug_a": {}, "drug_b": {}, "status": "known", "level": "Major", "confidence": 0.92 }]
}
```

| 字段 | 说明 |
|---|---|
| `engine` | `dict`（词典基线）或 `biobert`（序列标注），前端据此显示当前识别引擎 |
| `entities[].source` | `dict` / `model`，标明该实体由哪一档识别出来 |
| `entities[].drug` | 归一化到库内的药物；**可能为 `null`**（模型识别出库外商品名） |
| `unknown_entities[]` | 模型识别为药物但库内无对应药名的实体，不计入三元组，作人工评审候选 |
| `triples[].status` | `known`（主库已收录，附分级）/ `new`（主库无记录，需人工核实后评审入库） |

**两档实现，请求可用 `use_model` 切换**（`null` = 跟随服务端 `SAFERX_ML` 开关）：

| 引擎 | 触发条件 | 实体 F1 | 单次耗时 |
|---|---|---|---|
| 词典基线 | 默认 | 0.656 | ~20 ms |
| BioBERT | `SAFERX_ML=1` 且 `ml/artifacts/biobert-ner` 存在，或请求 `use_model: true` | **0.877** | 首次加载 ~15 s，之后 ~0.2 s |

两档产物结构完全一致，上层前端无需改动。模型不可用时**静默降级**到词典基线，不会 500。
模型权重 411MB，不进容器镜像、不进发布包，需单独 `python ml/train_ner.py --epochs 3` 生成。

`text` 为纯空白时返回 422（`field_validator` 拦截），避免白跑一次全表扫描。

## 8. 错误与边界

| 场景 | 状态码 | 表现 |
|---|---|---|
| 药单为空数组 | 422 | Pydantic 校验失败 |
| 药单仅 1 种药 | 200 | `pairs` 为空，`summary` 全 0，前端提示「至少添加 2 种药物」 |
| 药单超过 20 种 | 422 | `medications` 长度校验 |
| 药名不存在 | 200 | `unresolved[]` 带候选，不报错（避免用户被 4xx 打断） |
| `diseases` 超过 20 个 | 422 | 长度校验 |
| `GET /api/drugs/diseases?limit=5` | 422 | `limit` 下界为 10（防空列表把选择题做成填空题） |
| 数据库未建 | 503 | `/api/health` 返回 `db_missing` 与修复提示 |

## 9. 离线降级（前端行为）

`frontend/src/api/client.js` 先请求 `/api`，超时（默认 2s）或失败即切到 `api/mock.js` 的离线子集
（28 种药 / 21 条关系 / 6 种基础疾病占位）。降级后页面顶部显示「演示数据」状态，
`other_note` 会说明离线包不含 DDSI/DFI/重复用药数据，避免把「空结果」误读成「无风险」。

## 10. 性能实测

含 DDI + DDSI + DFI + 重复用药四类检查（每次附带 3 个基础疾病），本机 Python 3.13 / SQLite / 20 次均值：

| 药单规模 | DDI 组合数 | 平均耗时 | P95 | 命中（DDI / 病 / 食 / 重复组） |
|---|---|---|---|---|
| 5 药 | 10 | 0.89 ms | 1.29 ms | 10 / 6 / 6 / 1 |
| 10 药 | 45 | 2.50 ms | 2.73 ms | 45 / 11 / 13 / 1 |
| 19 药 | 171 | 7.87 ms | 8.46 ms | 159 / 28 / 21 / 3 |

`GET /api/drugs/diseases` 为 1.29 ms。

索引与查询计划上有两处实测结论（见 `pipelines/init_db.py` 注释）：

- `ddsi` 建**复合索引** `(ddinter_id, disease_en)`，并在 SQL 里用 `INDEXED BY` 固定它。
  不加提示时 SQLite 在 `IN` 列表变长后会改走「疾病优先」计划——先取出某病名下的 600+ 条
  带长描述的行再按药过滤，10 药场景从 0.09 ms 劣化到 6.7 ms（22 倍）。单列 `disease_en`
  索引同样会诱发这个计划，故不建。
- 疾病选择器要按疾病聚合计数，加了覆盖索引 `(disease_en, disease_cn, level)`，
  避免回表读大文本：17.4 ms → 1.3 ms。

瓶颈为首次磁盘页命中；重复调用稳定在毫秒级。测试方法见 `backend/tests/test_checker.py`
与 `docs/data_profile.md`。
