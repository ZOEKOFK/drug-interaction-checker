import { defineStore } from 'pinia'

export const MAX_DRUGS = 20

/**
 * 药单 store：首页 / 药单页 / 结果页 / 图谱页共享
 */
export const useMedStore = defineStore('medications', {
  state: () => ({
    drugs: [], // [{ddinter_id,name_cn,name_en,pinyin,atc,category}]
    diseases: [] // [{name_en,name_cn}] 患者基础疾病（用于药物-疾病禁忌检查）
  }),

  getters: {
    count: (s) => s.drugs.length,
    ids: (s) => s.drugs.map((d) => d.ddinter_id),
    canAdd: (s) => s.drugs.length < MAX_DRUGS,
    /** 两两组合数 C(n,2) */
    pairCount: (s) => (s.drugs.length * (s.drugs.length - 1)) / 2,
    diseaseIds: (s) => s.diseases.map((d) => d.name_en),
    hasDisease: (s) => s.diseases.length > 0
  },

  actions: {
    add(drug) {
      if (!drug || !drug.ddinter_id) return false
      if (this.drugs.some((d) => d.ddinter_id === drug.ddinter_id)) return false
      if (this.drugs.length >= MAX_DRUGS) return false
      this.drugs.push(drug)
      return true
    },
    remove(id) {
      this.drugs = this.drugs.filter((d) => d.ddinter_id !== id)
    },
    clear() {
      this.drugs = []
    },
    /** 切换患者基础疾病（影响 DDSI 检查） */
    toggleDisease(disease) {
      if (!disease || !disease.name_en) return
      const i = this.diseases.findIndex((d) => d.name_en === disease.name_en)
      if (i >= 0) this.diseases.splice(i, 1)
      else if (this.diseases.length < 8) this.diseases.push({ ...disease })
    },
    clearDiseases() {
      this.diseases = []
    },
    loadTemplate(drugs) {
      this.drugs = drugs.slice(0, MAX_DRUGS)
    }
  }
})
