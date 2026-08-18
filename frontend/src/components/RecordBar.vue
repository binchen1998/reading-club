<script setup lang="ts">
defineProps<{
  open: boolean
  recording: boolean
  busy: boolean
  passed: boolean
  lastScore: number | null
  lastHeard: string
  scoreError: string
  uploadHint: string
  recordLeft: number
  recordTotal: number
  recordWords: number
  segIndex: number
  segCount: number
  cameraEnabled: boolean
  cameraStarting: boolean
  cameraError: string
  passText: string
}>()

const emit = defineEmits<{
  start: []
  stop: []
  skip: []
  close: []
  toggleCamera: []
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="record-bar pointer-events-none fixed inset-x-0 bottom-0 z-[75] px-2 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 sm:px-4"
    >
      <div
        class="pointer-events-auto mx-auto flex min-h-[4.5rem] max-w-[1400px] flex-wrap items-center gap-3 rounded-3xl border border-white/50 bg-white/55 px-3 py-3 shadow-[0_10px_32px_rgba(15,23,42,0.16)] backdrop-blur-md sm:min-h-[5.25rem] sm:gap-4 sm:px-5 sm:py-4"
      >
        <span class="chip shrink-0 bg-brand-100/90 px-3 py-1.5 text-sm text-brand-700 sm:text-base">
          第 {{ segIndex + 1 }} / {{ segCount }} 段
        </span>
        <p class="hidden min-w-0 flex-1 text-sm font-bold leading-6 text-brand-700 sm:block sm:text-base">
          书上黄框就是要读的 · 每词最多 3 秒 · 读完可点停
        </p>
        <div v-if="recording" class="flex min-w-0 flex-1 items-center gap-3">
          <span
            class="w-10 shrink-0 text-center text-2xl font-black tabular-nums sm:text-3xl"
            :class="recordLeft <= 3 ? 'text-candy' : 'text-brand-700'"
          >
            {{ Math.ceil(recordLeft) }}
          </span>
          <div class="h-2.5 min-w-[5rem] flex-1 overflow-hidden rounded-full bg-brand-100/80">
            <div
              class="h-full rounded-full"
              :class="recordLeft <= 3 ? 'bg-candy' : 'bg-sunny'"
              :style="{ width: recordTotal ? `${(recordLeft / recordTotal) * 100}%` : '0%' }"
            />
          </div>
          <span class="hidden shrink-0 text-sm font-bold text-brand-700/70 sm:inline">
            {{ recordWords }} 词 × 3 秒
          </span>
        </div>

        <p v-else-if="busy" class="min-w-0 flex-1 text-base font-extrabold text-brand-700/80">正在评分…</p>
        <p v-else-if="scoreError" class="min-w-0 flex-1 text-base font-extrabold text-candy">{{ scoreError }}</p>
        <p v-else-if="uploadHint" class="min-w-0 flex-1 text-base font-extrabold text-brand-700">{{ uploadHint }}</p>
        <p
          v-else-if="lastScore != null"
          class="min-w-0 flex-1 text-base font-extrabold"
          :class="passed ? 'text-mint' : 'text-candy'"
        >
          {{ lastScore }} 分 · {{ passText }}
          <span v-if="lastHeard" class="font-bold text-brand-700/50"> · 听到：{{ lastHeard }}</span>
        </p>

        <div data-camera-pip-anchor class="relative z-20 ml-auto flex shrink-0 items-center gap-2">
          <button
            class="chip shrink-0 bg-white/80 px-3 py-1.5 text-sm text-brand-700 disabled:opacity-50 sm:text-base"
            type="button"
            :disabled="cameraStarting"
            @click="emit('toggleCamera')"
          >
            {{ cameraEnabled ? '📷 关摄像头' : '📷 开摄像头' }}
          </button>
          <button
            v-if="!recording && !busy"
            class="btn-candy px-4 py-2 text-sm sm:px-5 sm:py-2.5 sm:text-base"
            type="button"
            @click="emit('start')"
          >
            {{ lastScore != null && !passed ? '再读一次' : '开始录音' }}
          </button>
          <button
            v-else-if="recording"
            class="btn-ghost px-4 py-2 text-sm sm:px-5 sm:py-2.5 sm:text-base"
            type="button"
            @click="emit('stop')"
          >
            停
          </button>
          <button
            v-if="!recording && !busy && !passed"
            class="px-3 py-2 text-sm font-extrabold text-brand-700/80 sm:text-base"
            type="button"
            @click="emit('skip')"
          >
            跳过这句
          </button>
          <button
            class="grid h-9 w-9 place-items-center rounded-full bg-white/70 text-lg font-black text-brand-500 hover:bg-white sm:h-10 sm:w-10"
            type="button"
            aria-label="关闭"
            @click="emit('close')"
          >
            ×
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
