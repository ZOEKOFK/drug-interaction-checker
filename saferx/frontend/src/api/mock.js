/**
 * 演示兜底数据服务（离线 mock）
 * ------------------------------------------------------------------
 * 后端 /api 未启动时，前端自动降级到本模块，保证任意环境可完整演示。
 * 算法与方案 §3.3 一致：归一化 -> 两两组合 -> 查表 -> 聚合取最高级 -> 总体分级。
 * 数据为教学演示用的精编子集（真实数据由后端 + DDInter 2.0 提供）。
 */
import drugsRaw from '../assets/sample_meds/drugs.json'
import ddiRaw from '../assets/sample_meds/ddi.json'
import templatesRaw from '../assets/sample_meds/templates.json'

const drugs = drugsRaw
const ddiList = ddiRaw
const templates = templatesRaw

const LEVEL_ORDER = { Major: 3, Moderate: 2, Minor: 1 }
const LEVEL_CN = { Major: '严重', Moderate: '中度', Minor: '轻微' }

const drugById = new Map(drugs.map((d) => [d.ddinter_id, d]))

/** 无序对规范化：id 较小者在前，与后端 idx_pair 唯一索引约定一致 */
function pairKey(a, b) {
  return a < b ? `${a}|${b}` : `${b}|${a}`
}

const ddiIndex = new Map()
for (const rec of ddiList) {
  const key = pairKey(rec.a, rec.b)
  if (!ddiIndex.has(key)) ddiIndex.set(key, [])
  ddiIndex.get(key).push(rec)
}

/* ---------------- 药名搜索（中文 / 英文 / 拼音首字母） ---------------- */
export function searchDrugs(q, limit = 10) {
  const query = String(q || '').trim().toLowerCase()
  if (!query) return drugs.slice(0, limit)

  const scored = []
  for (const d of drugs) {
    const cn = d.name_cn
    const en = d.name_en.toLowerCase()
    let score = 0
    if (cn === query) score = 100
    else if (cn.startsWith(query)) score = 90
    else if (cn.includes(query)) score = 70
    else if (en === query) score = 85
    else if (en.startsWith(query)) score = 75
    else if (en.includes(query)) score = 55
    else if (d.pinyin.startsWith(query)) score = 60
    if (score > 0) scored.push({ d, score })
  }
  scored.sort((x, y) => y.score - x.score)
  return scored.slice(0, limit).map((s) => s.d)
}

/* ---------------- 两两 DDI 检查（核心 checker） ---------------- */
export function check(medIds) {
  const ids = [...new Set(medIds)].filter((id) => drugById.has(id))
  const pairs = []
  const unrecorded = []

  for (let i = 0; i < ids.length; i++) {
    for (let j = i + 1; j < ids.length; j++) {
      const recs = ddiIndex.get(pairKey(ids[i], ids[j])) || []
      if (recs.length === 0) {
        unrecorded.push([drugById.get(ids[i]), drugById.get(ids[j])])
        continue
      }
      // 保守策略：同一组合取最高风险等级
      const best = recs.reduce((m, r) =>
        LEVEL_ORDER[r.level] > LEVEL_ORDER[m.level] ? r : m
      )
      pairs.push({
        drug_a: drugById.get(best.a),
        drug_b: drugById.get(best.b),
        level: best.level,
        level_cn: LEVEL_CN[best.level],
        mechanism_cn: best.mechanism_cn,
        mechanism_en: best.mechanism_en,
        management: best.management,
        source_id: best.source_id
      })
    }
  }

  const order = { Major: 0, Moderate: 1, Minor: 2 }
  pairs.sort(
    (x, y) => order[x.level] - order[y.level] || x.drug_a.name_cn.localeCompare(y.drug_a.name_cn)
  )

  const summary = {
    Major: pairs.filter((p) => p.level === 'Major').length,
    Moderate: pairs.filter((p) => p.level === 'Moderate').length,
    Minor: pairs.filter((p) => p.level === 'Minor').length,
    Unknown: 0,
    overall:
      pairs.some((p) => p.level === 'Major')
        ? 'red'
        : pairs.some((p) => p.level === 'Moderate')
          ? 'orange'
          : pairs.length > 0
            ? 'green'
            : 'gray'
  }

  return {
    unresolved: [],
    pairs,
    unrecorded_pairs: unrecorded.map(([a, b]) => ({ drug_a: a, drug_b: b })),
    summary,
    checked_at: new Date().toISOString(),
    data_version: 'DDInter 2.0 (2025, NAR) · 演示子集',
    coverage_note:
      unrecorded.length > 0
        ? `以下 ${unrecorded.length} 个药物组合在数据库中无收录记录，不代表无相互作用。`
        : '当前药单所有组合均有收录记录。'
  }
}

/* ---------------- 图谱子图构建 ---------------- */
const LEVEL_COLOR = { Major: '#A32D2D', Moderate: '#854F0B', Minor: '#3B6D11' }

export function buildGraph(medIds) {
  const result = check(medIds)
  const nodes = medIds
    .map((id) => {
      const d = drugById.get(id)
      return { id: d.ddinter_id, name: d.name_cn, name_en: d.name_en, category: d.category, degree: 0 }
    })
    .filter(Boolean)

  const links = result.pairs.map((p) => {
    const s = nodes.find((n) => n.id === p.drug_a.ddinter_id)
    const t = nodes.find((n) => n.id === p.drug_b.ddinter_id)
    s.degree++
    t.degree++
    return {
      source: p.drug_a.ddinter_id,
      target: p.drug_b.ddinter_id,
      value: p.level,
      lineStyle: { color: LEVEL_COLOR[p.level], width: p.level === 'Major' ? 3.5 : 2 },
      label: { show: false }
    }
  })

  // 节点最大关联风险着色描边
  const levelNum = { Major: 3, Moderate: 2, Minor: 1 }
  for (const n of nodes) n.maxLevel = 0
  for (const p of result.pairs) {
    for (const d of [p.drug_a, p.drug_b]) {
      const n = nodes.find((x) => x.id === d.ddinter_id)
      if (n && levelNum[p.level] > n.maxLevel) n.maxLevel = levelNum[p.level]
    }
  }
  return {
    nodes: nodes.map((n) => ({
      ...n,
      symbolSize: 16 + Math.min(n.degree, 5) * 6,
      borderColor: ['#DCE9E4', '#3B6D11', '#854F0B', '#A32D2D'][n.maxLevel],
      borderWidth: n.maxLevel > 0 ? 4 : 2
    })),
    links
  }
}

export function getTemplates() {
  return templates
}

export function getDrug(id) {
  return drugById.get(id) || null
}

export function getAllDrugs() {
  return drugs
}

/* ---------------- NLP 抽取演示（离线规则模拟） ---------------- */
export function extractEntities(text) {
  const entities = []
  for (const d of drugs) {
    const patterns = [d.name_cn, d.name_en]
    for (const pat of patterns) {
      let idx = text.indexOf(pat)
      while (idx !== -1) {
        entities.push({ start: idx, end: idx + pat.length, text: pat, drug: d })
        idx = text.indexOf(pat, idx + pat.length)
      }
    }
  }
  // 按位置排序，重叠时保留更长者
  entities.sort((a, b) => a.start - b.start || b.end - a.end)
  const merged = []
  for (const e of entities) {
    const last = merged[merged.length - 1]
    if (last && e.start < last.end) continue
    merged.push(e)
  }
  return merged
}

export function extractTriples(text) {
  const entities = extractEntities(text)
  const seen = new Set()
  const triples = []
  for (let i = 0; i < entities.length; i++) {
    for (let j = i + 1; j < entities.length; j++) {
      const a = entities[i].drug
      const b = entities[j].drug
      if (a.ddinter_id === b.ddinter_id) continue
      const key = pairKey(a.ddinter_id, b.ddinter_id)
      if (seen.has(key)) continue
      seen.add(key)
      const recs = ddiIndex.get(key) || []
      const known = recs.length > 0 ? recs.reduce((m, r) => (LEVEL_ORDER[r.level] > LEVEL_ORDER[m.level] ? r : m)) : null
      triples.push({
        drug_a: a,
        drug_b: b,
        status: known ? 'known' : 'new',
        level: known ? known.level : null,
        level_cn: known ? LEVEL_CN[known.level] : null,
        mechanism_cn: known ? known.mechanism_cn : '主库未收录，建议人工核实原文后评审入库',
        confidence: known ? 0.92 : 0.78
      })
    }
  }
  return { entities, triples }
}

/** 离线演示子集的规模信息（与 /api/health 的 stats 结构保持一致） */
export function getStats() {
  const levels = { Major: 0, Moderate: 0, Minor: 0, Unknown: 0 }
  for (const r of ddiList) levels[r.level] = (levels[r.level] || 0) + 1
  return {
    offline: true,
    drugs: drugs.length,
    drugs_with_cn: drugs.filter((d) => d.name_cn && d.name_cn !== d.name_en).length,
    ddi_pairs: ddiList.length,
    mechanisms: ddiList.filter((r) => r.mechanism_cn).length,
    mechanisms_covered_pairs: ddiList.filter((r) => r.mechanism_cn).length,
    aliases: 0,
    aliases_cn: 0,
    templates: templates.length,
    levels,
    built_at: '',
    source: 'DDInter 2.0（离线演示子集）'
  }
}
