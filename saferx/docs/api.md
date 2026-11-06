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
  "data_version": "DDInter 2.0 · 1971 种药物 · 234,981 条 DDI · 构建于 2026-11-06 23:55:56",
  "stats": {
    "drugs": 1971,
    "drugs_with_cn": 366,
    "ddi_pairs": 234981,
    "mechanisms": 21,
    "mechanisms_covered_pairs": 21,
    "aliases": 5244,
    "aliases_cn": 367,
    "templates": 4,
    "levels": { "Major": 39082, "Moderate": 143748, "Minor": 9736, "Unknown": 42415 },
    "built_at": "2026-11-06 23:55:56",
    "source": "DDInter 2.0 (https://ddinter2.scbdd.com/, CC BY-NC-SA 4.0)"
  }
}
```

数据库缺失时返回 `503 {"status": "db_missing", "hint": "请先运行 make data && make initdb"}`。

## 2. `POST /api/check` — 药单两两检查（核心）

请求：

```json
{ "medications": ["华法林", "阿司匹林", "二甲双胍"] }
```

响应（节选，真实的 2 药样例）：

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
  "checked_at": "2026-11-06T16:04:55+00:00",
  "data_version": "DDInter 2.0 · 1971 种药物 · 234,981 条 DDI · 构建于 2026-11-06 23:55:56",
  "coverage_note": "当前药单所有组合均有收录记录；「分级未知」条目为官方未标注严重度的记录，同样不代表安全。"
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `pairs[]` | 每个有收录记录的药对一条，按风险等级降序 |
| `level` | `Major` / `Moderate` / `Minor` / `Unknown` |
| `summary.overall` | `red`（含 Major）/ `orange`（含 Moderate）/ `green`（仅 Minor）/ `gray`（无记录或仅 Unknown） |
| `unrecorded_pairs[]` | 库内**无记录**的组合——不代表安全，前端单独展示 |
| `unresolved[]` | 药名无法归一化的输入，附 `candidates` 候选供用户确认 |

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

## 7. `POST /api/lab/extract` — 文献 DDI 抽取（演示）

```bash
curl -s -X POST http://127.0.0.1:8000/api/lab/extract \
  -H "Content-Type: application/json" \
  -d '{"text":"患者长期口服华法林抗凝，近期因房颤加用胺碘酮。"}'
```

```json
{
  "entities": [{ "text": "华法林", "drug": { "name_cn": "华法林", "name_en": "Warfarin" }, "start": 5, "end": 8 }],
  "triples": [{ "drug_a": {}, "drug_b": {}, "status": "known", "level": "Major", "confidence": 0.92 }]
}
```

`status`：`known`（主库已收录，附分级）/ `new`（主库无记录，作为候选取样，需人工核实后评审入库）。
**当前实现为词典共现规则基线**，`ml/artifacts` 就绪后替换为 UIE/BioBERT 推理，接口结构不变。

## 8. 错误与边界

| 场景 | 状态码 | 表现 |
|---|---|---|
| 药单为空数组 | 422 | Pydantic 校验失败 |
| 药单仅 1 种药 | 200 | `pairs` 为空，`summary` 全 0，前端提示「至少添加 2 种药物」 |
| 药单超过 20 种 | 422 | `medications` 长度校验 |
| 药名不存在 | 200 | `unresolved[]` 带候选，不报错（避免用户被 4xx 打断） |
| 数据库未建 | 503 | `/api/health` 返回 `db_missing` 与修复提示 |

## 9. 离线降级（前端行为）

`frontend/src/api/client.js` 先请求 `/api`，超时（默认 2s）或失败即切到 `api/mock.js` 的离线子集
（28 种药 / 21 条关系），保证断网答辩仍可完整演示。降级后页面顶部会显示「演示数据」状态。

## 10. 性能实测

| 药单规模 | 组合数 | 平均耗时（20 次均值，本机 Python 3.13 / SQLite） |
|---|---|---|
| 5 药 | 10 | 0.70 ms |
| 10 药 | 45 | 2.47 ms |
| 20 药 | 190 | 8.97 ms |

测试方法见 `backend/tests/test_checker.py` 与 `docs/data_profile.md`；瓶颈为磁盘页缓存首次命中，重复调用稳定在毫秒级。
