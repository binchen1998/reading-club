<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useAssistantPipRect } from '../composables/useAssistantPipFrame'

const props = defineProps<{
  visible: boolean
  listening: boolean
  stream: MediaStream | null
  disabled?: boolean
  /** 本节课提问进度，如 1/30 */
  askQuotaLabel?: string
}>()

const emit = defineEmits<{
  ask: []
  finish: []
}>()

const BAR_COUNT = 12
const levels = ref<number[]>(Array.from({ length: BAR_COUNT }, () => 0.12))

let ctx: AudioContext | null = null
let source: MediaStreamAudioSourceNode | null = null
let analyser: AnalyserNode | null = null
let raf = 0

const { left, top, pipW, pipH } = useAssistantPipRect()
const label = computed(() => (props.listening ? '我讲完了' : '我要提问'))
const fabStyle = computed(() => ({
  left: `${left.value + pipW.value / 2}px`,
  top: `${top.value + pipH.value + 6}px`,
  transform: 'translateX(-50%)',
}))

function stopMeter() {
  if (raf) {
    cancelAnimationFrame(raf)
    raf = 0
  }
  try {
    source?.disconnect()
  } catch {
    /* ignore */
  }
  try {
    analyser?.disconnect()
  } catch {
    /* ignore */
  }
  source = null
  analyser = null
  if (ctx) {
    void ctx.close().catch(() => undefined)
    ctx = null
  }
  levels.value = Array.from({ length: BAR_COUNT }, () => 0.12)
}

async function startMeter(stream: MediaStream) {
  stopMeter()
  const Ctx = window.AudioContext || (window as any).webkitAudioContext
  ctx = new Ctx()
  if (ctx.state === 'suspended') {
    try {
      await ctx.resume()
    } catch {
      /* ignore */
    }
  }
  source = ctx.createMediaStreamSource(stream)
  analyser = ctx.createAnalyser()
  analyser.fftSize = 256
  analyser.smoothingTimeConstant = 0.72
  source.connect(analyser)
  const data = new Uint8Array(analyser.frequencyBinCount)

  const tick = () => {
    raf = requestAnimationFrame(tick)
    if (!analyser) return
    analyser.getByteFrequencyData(data)
    const step = Math.max(1, Math.floor(data.length / BAR_COUNT))
    const next: number[] = []
    for (let i = 0; i < BAR_COUNT; i += 1) {
      let v = 0
      for (let j = 0; j < step; j += 1) v += data[i * step + j] || 0
      const n = Math.min(1, (v / step / 255) * 1.6)
      next.push(0.12 + n * 0.88)
    }
    levels.value = next
  }
  tick()
}

watch(
  () => [props.listening, props.stream] as const,
  ([listening, stream]) => {
    if (listening && stream) void startMeter(stream)
    else stopMeter()
  },
  { immediate: true },
)

onBeforeUnmount(stopMeter)

function onClick() {
  if (props.disabled) return
  if (props.listening) emit('finish')
  else emit('ask')
}
</script>

<template>
  <div
    v-if="visible"
    class="ai-ask-fab pointer-events-none fixed z-[92] flex flex-col items-center gap-1"
    :style="fabStyle"
  >
    <div class="pointer-events-auto flex items-center gap-1">
      <button
        type="button"
        class="rounded-full px-2.5 py-1 text-[11px] font-extrabold shadow-pop transition active:scale-[0.98]"
        :class="
          listening
            ? 'bg-brand-600 text-white ring-2 ring-brand-300/70'
            : 'btn-candy'
        "
        :disabled="disabled"
        @click="onClick"
      >
        {{ label }}
      </button>
      <span
        v-if="askQuotaLabel && !listening"
        class="rounded-full bg-white/95 px-1.5 py-0.5 text-[10px] font-extrabold text-brand-700 shadow-sm"
        :title="`本节课提问次数 ${askQuotaLabel}`"
      >
        {{ askQuotaLabel }}
      </span>
    </div>

    <div
      v-if="listening"
      class="pointer-events-none relative flex h-6 w-16 items-end justify-center gap-px"
      aria-hidden="true"
    >
      <span
        v-for="(lv, idx) in levels"
        :key="`bar-${idx}`"
        class="ai-ask-bar w-px rounded-full bg-gradient-to-t from-brand-500 to-candy"
        :style="{ height: `${Math.round(lv * 100)}%` }"
      />
    </div>
  </div>
</template>

<style scoped>
.ai-ask-bar {
  transition: height 60ms linear;
  min-height: 18%;
}
</style>
