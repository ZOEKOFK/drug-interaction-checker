<script setup>
/**
 * 药盒 chip：胶囊造型（左帽按药品类别着色 + 接缝线）
 */
const props = defineProps({
  drug: { type: Object, required: true },
  removable: { type: Boolean, default: true },
  compact: { type: Boolean, default: false }
})
const emit = defineEmits(['remove'])

const CATEGORY_PALETTE = [
  '#0F6E56', '#1D6FA5', '#5B4FB0', '#8A5A44', '#376D89', '#556B2F', '#6B21A8', '#9A3412'
]
function capColor(category) {
  let h = 0
  for (const ch of String(category || '')) h = (h * 31 + ch.codePointAt(0)) >>> 0
  return CATEGORY_PALETTE[h % CATEGORY_PALETTE.length]
}
</script>

<template>
  <span class="pill" :class="compact ? 'text-xs' : 'text-sm'" :style="{ '--pill-cap': capColor(drug.category) }">
    <span class="relative z-10 flex items-center" :class="compact ? 'pl-3 pr-2 py-1' : 'pl-6 pr-2.5 py-1.5'">
      <span class="font-semibold whitespace-nowrap">{{ drug.name_cn }}</span>
      <span v-if="drug.name_en !== drug.name_cn" class="ml-1.5 text-ink-faint hidden sm:inline whitespace-nowrap">{{ drug.name_en }}</span>
    </span>
    <button
      v-if="removable"
      class="relative z-10 mr-1.5 ml-0.5 w-5 h-5 shrink-0 rounded-full text-ink-faint hover:text-risk-major hover:bg-risk-major-bg flex items-center justify-center transition-colors"
      title="移除该药品"
      @click.stop="emit('remove', drug.ddinter_id)"
    >
      <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
        <path d="M6 6l12 12M18 6 6 18" stroke-linecap="round" />
      </svg>
    </button>
  </span>
</template>
