<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

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
const pulse = ref(0.35)

let ctx: AudioContext | null = null
let source: MediaStreamAudioSourceNode | null = null
let analyser: AnalyserNode | null = null
let raf = 0

const label = computed(() => (props.listening ? '我讲完了' : '我要提问'))

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
  pulse.value = 0.35
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
    let sum = 0
    for (let i = 0; i < BAR_COUNT; i += 1) {
      let v = 0
      for (let j = 0; j < step; j += 1) v += data[i * step + j] || 0
      const n = Math.min(1, (v / step / 255) * 1.6)
      next.push(0.12 + n * 0.88)
      sum += n
    }
    levels.value = next
    pulse.value = 0.28 + Math.min(0.72, (sum / BAR_COUNT) * 1.2)
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
    class="ai-ask-fab pointer-events-none fixed bottom-[max(1.25rem,env(safe-area-inset-bottom))] right-[max(1rem,env(safe-area-inset-right))] z-[92] flex flex-col items-center gap-3"
  >
    <!-- Siri 风格水波纹 + 频谱条 -->
    <div
      v-if="listening"
      class="pointer-events-none relative flex h-28 w-40 items-center justify-center sm:h-32 sm:w-48"
      aria-hidden="true"
    >
      <span
        v-for="i in 3"
        :key="`ring-${i}`"
        class="ai-ask-ring absolute rounded-full border-2 border-brand-400/50"
        :style="{
          width: `${48 + i * 28 + pulse * 36}px`,
          height: `${48 + i * 28 + pulse * 36}px`,
          opacity: Math.max(0.15, 0.55 - i * 0.12) * pulse,
          animationDelay: `${(i - 1) * 0.18}s`,
        }"
      />
      <div class="relative z-10 flex h-14 items-end gap-[3px] sm:h-16 sm:gap-1">
        <span
          v-for="(lv, idx) in levels"
          :key="`bar-${idx}`"
          class="ai-ask-bar w-[3px] rounded-full bg-gradient-to-t from-brand-500 to-candy sm:w-1"
          :style="{ height: `${Math.round(lv * 100)}%` }"
        />
      </div>
    </div>

    <p
      v-if="listening"
      class="pointer-events-none rounded-full bg-slate-900/85 px-3 py-1 text-xs font-extrabold text-white shadow-pop"
    >
      老师正在听你说…
    </p>

    <div class="pointer-events-auto flex items-center gap-2">
      <button
        type="button"
        class="min-w-[8.5rem] rounded-full px-6 py-3.5 text-base font-black shadow-pop transition active:scale-[0.98] sm:min-w-[9.5rem] sm:px-7 sm:py-4 sm:text-lg"
        :class="
          listening
            ? 'bg-brand-600 text-white ring-4 ring-brand-300/60'
            : 'btn-candy'
        "
        :disabled="disabled"
        @click="onClick"
      >
        {{ label }}
      </button>
      <span
        v-if="askQuotaLabel && !listening"
        class="rounded-full bg-white/95 px-2.5 py-1 text-xs font-extrabold text-brand-700 shadow-sm sm:text-sm"
        :title="`本节课提问次数 ${askQuotaLabel}`"
      >
        {{ askQuotaLabel }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.ai-ask-ring {
  animation: ai-ask-pulse 1.6s ease-out infinite;
}
.ai-ask-bar {
  transition: height 60ms linear;
  min-height: 18%;
}
@keyframes ai-ask-pulse {
  0% {
    transform: scale(0.92);
  }
  70% {
    transform: scale(1.06);
  }
  100% {
    transform: scale(0.92);
  }
}
</style>
