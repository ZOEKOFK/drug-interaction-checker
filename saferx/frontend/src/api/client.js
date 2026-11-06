/**
 * API 客户端：优先请求 FastAPI 后端（/api），失败自动降级到离线 mock。
 * 后端就绪后无需改动任何页面代码。
 */
import * as mock from './mock.js'

let backendOnline = null // null=未知 true=在线 false=离线（降级）

async function jfetch(url, options = {}, timeout = 2000) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeout)
  try {
    const res = await fetch(url, { ...options, signal: ctrl.signal })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } finally {
    clearTimeout(timer)
  }
}

/** 药名模糊搜索 -> [{ddinter_id,name_cn,name_en,category,...}] */
export async function searchDrugs(q, limit = 10) {
  if (backendOnline !== false) {
    try {
      const data = await jfetch(`/api/drugs/search?q=${encodeURIComponent(q)}&limit=${limit}`)
      backendOnline = true
      return data.results ?? data
    } catch {
      backendOnline = false
    }
  }
  return mock.searchDrugs(q, limit)
}

/** 两两 DDI 检查（核心接口） */
export async function check(medIds) {
  if (backendOnline !== false) {
    try {
      const data = await jfetch('/api/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ medications: medIds })
      })
      backendOnline = true
      return data
    } catch {
      backendOnline = false
    }
  }
  return mock.check(medIds)
}

/** 当前药单的关系子图 -> {nodes, links}（ECharts 直接可用） */
export async function getGraph(medIds) {
  if (backendOnline !== false) {
    try {
      const data = await jfetch(`/api/graph?ids=${medIds.join(',')}`)
      backendOnline = true
      return data
    } catch {
      backendOnline = false
    }
  }
  return mock.buildGraph(medIds)
}

/** 慢病示例模板药单 -> [{id,name,desc,expected,drugs:[drug]}] */
export async function getTemplates() {
  if (backendOnline !== false) {
    try {
      const data = await jfetch('/api/drugs/templates')
      backendOnline = true
      return data
    } catch {
      backendOnline = false
    }
  }
  return mock.getTemplates().map((t) => ({
    ...t,
    drugs: t.drugs.map((id) => mock.getDrug(id)).filter(Boolean)
  }))
}

/** NLP 文献抽取演示 -> {entities, triples} */
export async function extract(text) {
  if (backendOnline !== false) {
    try {
      const data = await jfetch('/api/lab/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      })
      backendOnline = true
      return data
    } catch {
      backendOnline = false
    }
  }
  return mock.extractTriples(text)
}

export function isBackendOnline() {
  return backendOnline === true
}

export { mock }
