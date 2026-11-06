<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMedStore, MAX_DRUGS } from '../stores/medications.js'
import { useResultStore } from '../stores/results.js'
import { searchDrugs, check as apiCheck, getTemplates, getDiseases } from '../api/client.js'
import DrugSearchBox from '../components/DrugSearchBox.vue'
import PillChip from '../components/PillChip.vue'
import RiskDonut from '../components/RiskDonut.vue'

const router = useRouter()
const medStore = useMedStore()
const resultStore = useResultStore()

const templates = ref([])
const diseases = ref([])
const showAllDiseases = ref(false)
onMounted(async () => {
  templates.value = await getTemplates()
  diseases.value = await getDiseases(60)
})

const visibleDiseases = computed(() =>
  showAllDiseases.value ? diseases.value : diseases.value.slice(0, 12)
)
const selectedDiseaseKeys = computed(() => new Set(medStore.diseaseIds))
function toggleDisease(d) {
  medStore.toggleDisease(d)
}

/* 实时风险摘要（增删药品 / 改基础疾病即时刷新） */
watch(
  () => [medStore.ids, medStore.diseaseIds],
  async ([ids]) => {
    if (ids.length < 2) {
      resultStore.clearPreview()
      return
    }
    const result = await apiCheck(ids, medStore.diseaseIds)
    resultStore.setPreview(result)
  },
  { deep: true, immediate: true }
)

const preview = computed(() => resultStore.preview)
const previewSummary = computed(
  () => preview.value?.summary ?? { Major: 0, Moderate: 0, Minor: 0, Unknown: 0, overall: 'gray' }
)

const OVERALL_META = {
  red: { label: '发现严重风险', cls: 'bg-risk-major text-white', icon: 'M12 9v4M12 17h.01' },
  orange: { label: '发现中度风险', cls: 'bg-risk-moderate text-white', icon: 'M12 9v4M12 17h.01' },
  green: { label: '仅轻微风险', cls: 'bg-risk-minor text-white', icon: 'm5 13 4 4L19 7' },
  gray: { label: '未发现已知分级风险', cls: 'bg-primary text-white', icon: 'm5 13 4 4L19 7' }
}
const overall = computed(() => OVERALL_META[previewSummary.value.overall] || OVERALL_META.gray)

/* 其他相互作用摘要（疾病禁忌 / 食物 / 重复用药） */
const previewOther = computed(
  () =>
    preview.value?.other_summary ?? {
      disease: { Major: 0, Moderate: 0, Minor: 0 },
      food: { Major: 0, Moderate: 0, Minor: 0 },
      duplication_groups: 0,
      overall: 'gray'
    }
)
const previewOtherCount = computed(
  () =>
    (preview.value?.disease_risks?.length ?? 0) +
    (preview.value?.food_risks?.length ?? 0) +
    (preview.value?.duplications?.length ?? 0)
)
const diseaseCount = computed(() => {
  const d = previewOther.value.disease
  return d.Major + d.Moderate + d.Minor
})
const foodCount = computed(() => {
  const f = previewOther.value.food
  return f.Major + f.Moderate + f.Minor
})

/* 药品推荐（常用慢病药，排除已添加） */
const suggestions = ref([])
onMounted(async () => {
  suggestions.value = await searchDrugs('', 40)
})
const recommend = computed(() => {
  const inList = new Set(medStore.ids)
  return suggestions.value.filter((d) => !inList.has(d.ddinter_id)).slice(0, 6)
})

function onSelect(drug) {
  medStore.add(drug)
}

async function loadTemplate(tpl) {
  medStore.loadTemplate(tpl.drugs)
}

async function startCheck() {
  if (medStore.count < 2) return
  await resultStore.runCheck(medStore.ids, medStore.diseaseIds)
  router.push('/results')
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-2xl font-extrabold tracking-tight">我的药单</h1>
        <p class="mt-1 text-sm text-ink-soft">把正在服用的药物加入药盒，右侧实时预览风险摘要</p>
      </div>
      <span class="badge badge-clear badge-dot">{{ medStore.count }} / {{ MAX_DRUGS }} 种 · 待检组合 {{ medStore.pairCount }} 对</span>
    </div>

    <div class="mt-6 grid lg:grid-cols-[1fr_340px] gap-6 items-start">
      <!-- ============ 左：药盒 ============ -->
      <div class="space-y-6">
        <div class="card p-5">
          <div class="flex items-center gap-2 mb-4">
            <svg class="w-5 h-5 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="8" width="18" height="5" rx="2" /><path d="M12 8v5M7 8c0-1.7 1-3 2.5-3S12 6.3 12 8c0-1.7 1-3 2.5-3S17 6.3 17 8" /><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" />
            </svg>
            <h2 class="font-bold">我的药盒</h2>
            <span v-if="medStore.count === 0" class="text-xs text-ink-faint">（空）</span>
          </div>

          <DrugSearchBox @select="onSelect" />

          <!-- 药品胶囊 -->
          <div v-if="medStore.count" class="mt-4 flex flex-wrap gap-2.5">
            <PillChip v-for="d in medStore.drugs" :key="d.ddinter_id" :drug="d" @remove="medStore.remove" />
          </div>
          <div v-else class="mt-4 border-2 border-dashed border-line rounded-xl p-8 text-center">
            <p class="text-ink-soft text-sm font-medium">药盒还是空的</p>
            <p class="text-ink-faint text-xs mt-1">在上方搜索药品加入，或从下面的模板一键载入</p>
          </div>

          <div class="mt-4 flex items-center justify-between text-xs text-ink-faint">
            <span>上限 {{ MAX_DRUGS }} 种 · 匿名处理，离开页面即清除</span>
            <button v-if="medStore.count" class="text-risk-major hover:underline font-semibold" @click="medStore.clear()">
              清空药单
            </button>
          </div>
        </div>

        <!-- 基础疾病（启用药物-疾病禁忌检查） -->
        <div class="card p-5">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h2 class="font-bold text-sm flex items-center gap-2">
                基础疾病
                <span class="badge badge-clear text-[10px] font-semibold">可选</span>
              </h2>
              <p class="text-xs text-ink-faint mt-1">选择患者的基础疾病后，将额外执行「药物-疾病禁忌（DDSI）」检查</p>
            </div>
            <button
              v-if="medStore.hasDisease"
              class="text-xs text-risk-major hover:underline font-semibold shrink-0"
              @click="medStore.clearDiseases()"
            >
              清空
            </button>
          </div>

          <div class="mt-3 flex flex-wrap gap-2">
            <button
              v-for="d in visibleDiseases"
              :key="d.name_en"
              class="px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors"
              :class="selectedDiseaseKeys.has(d.name_en)
                ? 'bg-primary text-white border-primary'
                : 'bg-white text-ink-soft border-line hover:border-primary-bright hover:text-primary'"
              @click="toggleDisease(d)"
            >
              {{ d.name_cn }}
              <span v-if="d.count" class="ml-1 tabular-nums opacity-60">{{ d.count }}</span>
            </button>
          </div>

          <button
            v-if="diseases.length > 12"
            class="mt-2.5 text-xs font-semibold text-primary hover:underline"
            @click="showAllDiseases = !showAllDiseases"
          >
            {{ showAllDiseases ? '收起' : `展开更多疾病（共 ${diseases.length} 项）` }}
          </button>

          <p v-if="!medStore.hasDisease" class="mt-2.5 text-[11px] text-ink-faint">
            未选择时跳过该项检查——未检查不代表没有禁忌。
          </p>
          <p v-else class="mt-2.5 text-[11px] text-primary/80">
            已选 {{ medStore.diseases.length }} 项：{{ medStore.diseases.map((d) => d.name_cn).join('、') }}
          </p>
        </div>

        <!-- 模板快捷载入 -->
        <div class="card p-5">
          <h2 class="font-bold text-sm mb-3">示例模板一键载入</h2>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="tpl in templates"
              :key="tpl.id"
              class="btn-ghost text-xs"
              :title="tpl.expected"
              @click="loadTemplate(tpl)"
            >
              {{ tpl.name }}（{{ tpl.drugs.length }} 药）
            </button>
          </div>
        </div>

        <!-- 推荐补充 -->
        <div v-if="recommend.length" class="card p-5">
          <h2 class="font-bold text-sm mb-3">常用药品快捷添加</h2>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="d in recommend"
              :key="d.ddinter_id"
              class="px-3 py-1.5 rounded-full border border-line bg-white text-xs font-semibold text-ink-soft hover:border-primary-bright hover:text-primary transition-colors"
              @click="medStore.add(d)"
            >
              + {{ d.name_cn }}
            </button>
          </div>
          <p class="mt-2.5 text-[11px] text-ink-faint">推荐仅用于演示，不构成用药建议</p>
        </div>
      </div>

      <!-- ============ 右：实时风险摘要 ============ -->
      <div class="lg:sticky lg:top-20 card p-5">
        <h2 class="font-bold mb-2">实时风险摘要</h2>

        <template v-if="medStore.count >= 2">
          <RiskDonut :major="previewSummary.Major" :moderate="previewSummary.Moderate" :minor="previewSummary.Minor" :size="170" />

          <div class="mt-3 space-y-1.5 text-sm">
            <div class="flex items-center justify-between px-1">
              <span class="flex items-center gap-2"><i class="w-2.5 h-2.5 rounded-full bg-risk-major inline-block" />严重 Major</span>
              <b :class="previewSummary.Major ? 'text-risk-major' : 'text-ink-faint'">{{ previewSummary.Major }}</b>
            </div>
            <div class="flex items-center justify-between px-1">
              <span class="flex items-center gap-2"><i class="w-2.5 h-2.5 rounded-full bg-risk-moderate inline-block" />中度 Moderate</span>
              <b :class="previewSummary.Moderate ? 'text-risk-moderate' : 'text-ink-faint'">{{ previewSummary.Moderate }}</b>
            </div>
            <div class="flex items-center justify-between px-1">
              <span class="flex items-center gap-2"><i class="w-2.5 h-2.5 rounded-full bg-risk-minor inline-block" />轻微 Minor</span>
              <b :class="previewSummary.Minor ? 'text-risk-minor' : 'text-ink-faint'">{{ previewSummary.Minor }}</b>
            </div>
            <div v-if="previewSummary.Unknown" class="flex items-center justify-between px-1">
              <span class="flex items-center gap-2"><i class="w-2.5 h-2.5 rounded-full bg-ink-faint inline-block" />分级未知 Unknown</span>
              <b class="text-ink-soft">{{ previewSummary.Unknown }}</b>
            </div>
          </div>

          <!-- 其他相互作用（疾病禁忌 / 食物 / 重复用药） -->
          <div v-if="previewOtherCount" class="mt-3 border-t border-line pt-3 space-y-1.5 text-sm">
            <p class="text-[11px] font-bold text-ink-faint tracking-wide">其他相互作用</p>
            <div v-if="diseaseCount" class="flex items-center justify-between px-1">
              <span class="flex items-center gap-2"><i class="w-2.5 h-2.5 rounded-full bg-primary inline-block" />疾病禁忌</span>
              <b class="tabular-nums" :class="previewOther.disease.Major ? 'text-risk-major' : 'text-ink-soft'">{{ diseaseCount }}</b>
            </div>
            <div v-if="foodCount" class="flex items-center justify-between px-1">
              <span class="flex items-center gap-2"><i class="w-2.5 h-2.5 rounded-full bg-risk-moderate inline-block" />食物/烟酒</span>
              <b class="tabular-nums" :class="previewOther.food.Major ? 'text-risk-major' : 'text-ink-soft'">{{ foodCount }}</b>
            </div>
            <div v-if="previewOther.duplication_groups" class="flex items-center justify-between px-1">
              <span class="flex items-center gap-2"><i class="w-2.5 h-2.5 rounded-full bg-risk-minor inline-block" />治疗重复</span>
              <b class="text-ink-soft tabular-nums">{{ previewOther.duplication_groups }}</b>
            </div>
          </div>

          <div class="mt-4 rounded-xl p-3 text-center text-sm font-bold" :class="overall.cls">
            <svg class="w-4 h-4 inline mr-1 -mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
              <path :d="overall.icon" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            {{ overall.label }}
          </div>

          <button class="btn-primary w-full mt-4" :disabled="resultStore.checking" @click="startCheck">
            <svg v-if="!resultStore.checking" class="w-[18px] h-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="m22 2-7 20-4-9-9-4Z" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg v-else class="w-[18px] h-[18px] animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M21 12a9 9 0 1 1-6.2-8.6" stroke-linecap="round" />
            </svg>
            {{ resultStore.checking ? '正在检查 ' + medStore.pairCount + ' 个组合…' : '开始完整检查' }}
          </button>
        </template>

        <div v-else class="py-10 text-center">
          <p class="text-ink-soft text-sm font-medium">至少添加 2 种药物</p>
          <p class="text-ink-faint text-xs mt-1">即可进行两两相互作用检查</p>
        </div>

        <p class="mt-4 text-[11px] text-ink-faint leading-relaxed border-t border-line pt-3">
          摘要为实时预览；完整检查将输出可展开的风险卡片与交互图谱。未收录 ≠ 无相互作用。
        </p>
      </div>
    </div>
  </div>
</template>
