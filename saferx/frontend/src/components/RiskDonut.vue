<script setup>
/**
 * 风险分布环形图（ECharts 封装）
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  major: { type: Number, default: 0 },
  moderate: { type: Number, default: 0 },
  minor: { type: Number, default: 0 },
  unknown: { type: Number, default: 0 },
  size: { type: Number, default: 190 }
})

const el = ref(null)
let chart = null

const total = () => props.major + props.moderate + props.minor + props.unknown

function render() {
  if (!chart) return
  const data = [
    { value: props.major, name: '严重 Major', itemStyle: { color: '#A32D2D' } },
    { value: props.moderate, name: '中度 Moderate', itemStyle: { color: '#854F0B' } },
    { value: props.minor, name: '轻微 Minor', itemStyle: { color: '#3B6D11' } },
    { value: props.unknown, name: '分级未知 Unknown', itemStyle: { color: '#8CA096' } }
  ].filter((d) => d.value > 0)

  const empty = data.length === 0
  const overall =
    props.major > 0
      ? '发现严重风险'
      : props.moderate > 0
        ? '发现中度风险'
        : props.minor > 0
          ? '发现轻微风险'
          : props.unknown > 0
            ? '仅分级未知记录'
            : '未发现收录风险'

  chart.setOption({
    animationDuration: 600,
    series: [
      empty
        ? {
            type: 'pie',
            radius: ['68%', '84%'],
            label: { show: false },
            data: [{ value: 1, itemStyle: { color: '#DCE9E4' } }],
            silent: true
          }
        : {
            type: 'pie',
            radius: ['62%', '84%'],
            avoidLabelOverlap: true,
            itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
            label: { show: false },
            emphasis: { scaleSize: 5 },
            data
          }
    ],
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '42%',
        style: {
          text: String(total()),
          fontSize: 34,
          fontWeight: 700,
          fill: empty ? '#8CA096' : '#1F2A26',
          fontFamily: 'inherit'
        }
      },
      {
        type: 'text',
        left: 'center',
        top: '56%',
        style: {
          text: overall,
          fontSize: 13,
          fill: empty ? '#8CA096' : '#55655E',
          fontFamily: 'inherit'
        }
      }
    ]
  })
}

onMounted(() => {
  chart = echarts.init(el.value)
  render()
  const ro = new ResizeObserver(() => chart && chart.resize())
  ro.observe(el.value)
  onBeforeUnmount(() => ro.disconnect())
})
watch(() => [props.major, props.moderate, props.minor, props.unknown], render)
onBeforeUnmount(() => {
  if (chart) chart.dispose()
})
</script>

<template>
  <div ref="el" :style="{ width: size + 'px', height: size + 'px' }" class="mx-auto" />
</template>
