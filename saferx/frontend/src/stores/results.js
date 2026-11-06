import { defineStore } from 'pinia'
import { check as apiCheck, getGraph as apiGetGraph } from '../api/client.js'

/**
 * 检查结果 store：preview（药单页实时摘要）与 report（完整检查结果）
 */
export const useResultStore = defineStore('results', {
  state: () => ({
    preview: null, // 药单页实时风险摘要
    report: null, // 完整检查结果（进入结果页/图谱页的数据源）
    filter: 'all', // all | Major | Moderate | Minor | unrecorded
    checking: false
  }),

  getters: {
    summary: (s) => s.report?.summary ?? { Major: 0, Moderate: 0, Minor: 0, Unknown: 0, overall: 'gray' },
    pairs: (s) => s.report?.pairs ?? [],
    unrecorded: (s) => s.report?.unrecorded_pairs ?? [],
    /** 其他相互作用三段（疾病 / 食物 / 重复用药） */
    diseaseRisks: (s) => s.report?.disease_risks ?? [],
    foodRisks: (s) => s.report?.food_risks ?? [],
    duplications: (s) => s.report?.duplications ?? [],
    otherSummary: (s) =>
      s.report?.other_summary ?? {
        disease: { Major: 0, Moderate: 0, Minor: 0 },
        food: { Major: 0, Moderate: 0, Minor: 0 },
        duplication_groups: 0,
        overall: 'gray'
      },
    otherCount: (s) =>
      (s.report?.disease_risks?.length ?? 0) +
      (s.report?.food_risks?.length ?? 0) +
      (s.report?.duplications?.length ?? 0),
    filteredPairs(s) {
      if (s.filter === 'all') return s.pairs
      if (s.filter === 'unrecorded') return []
      return s.pairs.filter((p) => p.level === s.filter)
    }
  },

  actions: {
    setPreview(result) {
      this.preview = result
    },
    clearPreview() {
      this.preview = null
    },
    async runCheck(medIds, diseases = []) {
      this.checking = true
      try {
        this.report = await apiCheck(medIds, diseases)
        this.preview = this.report
        return this.report
      } finally {
        this.checking = false
      }
    },
    async loadGraph(medIds) {
      return apiGetGraph(medIds)
    },
    reset() {
      this.preview = null
      this.report = null
      this.filter = 'all'
    }
  }
})
