import { ref, watch, onUnmounted } from 'vue'

/**
 * 数字滚动动画（首页数据规模展示用）。
 * 支持传入数字或 getter：数据异步到达后可重新滚动到新目标值。
 */
export function useCountUp(source, duration = 1400) {
  const value = ref(0)
  const getTarget = () => {
    const v = typeof source === 'function' ? source() : source
    return typeof v === 'number' && Number.isFinite(v) ? v : 0
  }

  let raf = null
  watch(
    getTarget,
    (target) => {
      if (raf) cancelAnimationFrame(raf)
      if (!target) {
        value.value = 0
        return
      }
      const from = value.value
      const t0 = performance.now()
      const tick = (t) => {
        const p = Math.min(1, (t - t0) / duration)
        value.value = Math.round(from + (target - from) * (1 - Math.pow(1 - p, 3)))
        if (p < 1) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    },
    { immediate: true }
  )

  onUnmounted(() => {
    if (raf) cancelAnimationFrame(raf)
  })

  return value
}
