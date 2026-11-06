<script setup>
/**
 * 药物 × 疾病 / 药物 × 食物 的通用风险卡。
 * 中文只给「等级 + 对象 + 机制标签」，英文原文与参考文献折叠保留，避免二次转译失真。
 */
const props = defineProps({
  item: { type: Object, required: true },
  kind: { type: String, default: 'disease' } // disease | food
})

const LEVEL_CLS = {
  Major: { badge: 'badge-major', bar: 'bg-risk-major', text: 'text-risk-major' },
  Moderate: { badge: 'badge-moderate', bar: 'bg-risk-moderate', text: 'text-risk-moderate' },
  Minor: { badge: 'badge-minor', bar: 'bg-risk-minor', text: 'text-risk-minor' }
}
const style = LEVEL_CLS[props.item.level] || LEVEL_CLS.Minor

const targetCn = props.kind === 'disease' ? props.item.disease_cn : props.item.food_cn
const targetEn = props.kind === 'disease' ? props.item.disease_en : props.item.food_en
const detail = props.kind === 'disease' ? props.item.description_en : props.item.interaction_en
const management = props.item.management_en
</script>

<template>
  <div class="relative card p-4 pl-5 overflow-hidden">
    <span class="absolute left-0 top-0 bottom-0 w-1" :class="style.bar" />

    <div class="flex flex-wrap items-center gap-2">
      <h4 class="font-bold text-ink text-[14px]">
        {{ item.drug.name_cn }}
        <span class="text-ink-faint font-normal text-[11px] ml-0.5">{{ item.drug.name_en }}</span>
        <span class="mx-1.5 text-ink-faint font-normal" aria-hidden="true">×</span>
        {{ targetCn }}
        <span v-if="targetEn && targetEn !== targetCn" class="text-ink-faint font-normal text-[11px] ml-0.5">{{ targetEn }}</span>
      </h4>
      <span class="badge badge-dot" :class="style.badge">{{ item.level_cn }} {{ item.level }}</span>
      <span v-if="kind === 'food' && item.mechanism_cn" class="badge badge-clear">{{ item.mechanism_cn }}</span>
    </div>

    <p class="mt-2 text-[13px] text-ink leading-relaxed">{{ item.summary_cn }}</p>

    <details v-if="detail || management" class="mt-2">
      <summary class="text-[11px] text-primary cursor-pointer select-none font-semibold">
        展开原始说明（DDInter 英文原文）
      </summary>
      <div class="mt-1.5 space-y-1.5">
        <p v-if="detail" class="text-[12px] text-ink-soft leading-relaxed">{{ detail }}</p>
        <p v-if="management" class="text-[12px] text-ink-soft leading-relaxed">
          <b class="text-ink-faint">处置建议：</b>{{ management }}
        </p>
      </div>
    </details>
  </div>
</template>
