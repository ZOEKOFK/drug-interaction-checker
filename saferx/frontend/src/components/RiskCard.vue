<script setup>
/**
 * 风险卡片：色条 + 药物对 + 一句话结论，展开显示机制 / 处置 / 证据来源
 */
import { ref, computed } from 'vue'

const props = defineProps({
  pair: { type: Object, required: true }
})
const emit = defineEmits(['toggle'])

const expanded = ref(false)

const LEVEL_STYLE = {
  Major: { cls: 'major', bar: 'bg-risk-major', badge: 'badge-major', label: '严重 Major' },
  Moderate: { cls: 'moderate', bar: 'bg-risk-moderate', badge: 'badge-moderate', label: '中度 Moderate' },
  Minor: { cls: 'minor', bar: 'bg-risk-minor', badge: 'badge-minor', label: '轻微 Minor' },
  Unknown: { cls: 'unknown', bar: 'bg-ink-faint', badge: 'badge-unknown', label: '分级未知 Unknown' }
}
const style = computed(() => LEVEL_STYLE[props.pair.level] || LEVEL_STYLE.Minor)

function toggle() {
  expanded.value = !expanded.value
  emit('toggle', props.pair)
}
</script>

<template>
  <article class="card overflow-hidden relative" :class="style.cls">
    <!-- 左侧风险色条 -->
    <span class="absolute left-0 top-0 bottom-0 w-1.5" :class="style.bar" />

    <button class="w-full text-left pl-5 pr-4 py-4 flex items-start gap-3 group" @click="toggle">
      <div class="flex-1 min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h3 class="font-bold text-ink text-[15px]">
            {{ pair.drug_a.name_cn }}
            <span v-if="pair.drug_a.name_en !== pair.drug_a.name_cn" class="text-ink-faint font-normal text-xs ml-0.5 mr-0.5">{{ pair.drug_a.name_en }}</span>
            <span class="mx-1 text-ink-faint" aria-hidden="true">×</span>
            {{ pair.drug_b.name_cn }}
            <span v-if="pair.drug_b.name_en !== pair.drug_b.name_cn" class="text-ink-faint font-normal text-xs ml-0.5">{{ pair.drug_b.name_en }}</span>
          </h3>
          <span class="badge badge-dot" :class="style.badge">{{ style.label }}</span>
        </div>
        <p class="mt-1.5 text-sm text-ink-soft leading-relaxed line-clamp-1">
          {{ pair.mechanism_cn }}
        </p>
      </div>
      <svg
        class="w-5 h-5 mt-1 text-ink-faint shrink-0 transition-transform duration-300 group-hover:text-primary"
        :class="expanded ? 'rotate-180' : ''"
        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      >
        <path d="m6 9 6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <div class="expandable" :class="{ open: expanded }">
      <div>
        <div class="pl-5 pr-4 pb-4 -mt-1 space-y-3 text-sm">
          <div class="rounded-lg bg-paper p-3.5 space-y-3">
            <div v-if="pair.mechanism_cn">
              <p class="text-xs font-bold text-ink-faint tracking-wide mb-1">作用机制（中文摘要）</p>
              <p class="text-ink leading-relaxed">{{ pair.mechanism_cn }}</p>
            </div>
            <div>
              <p class="text-xs font-bold text-ink-faint tracking-wide mb-1">处置建议</p>
              <p class="text-ink leading-relaxed">{{ pair.management }}</p>
            </div>
            <details v-if="pair.mechanism_en">
              <summary class="text-xs text-primary cursor-pointer select-none font-semibold">展开英文原文（DDInter）</summary>
              <p class="mt-1.5 text-ink-soft italic leading-relaxed">{{ pair.mechanism_en }}</p>
            </details>
            <p class="text-xs text-ink-faint pt-1 border-t border-line">
              证据来源：DDInter 2.0 · 记录 {{ pair.source_id }} · 实际用药请咨询医师或药师
            </p>
          </div>
        </div>
      </div>
    </div>
  </article>
</template>
