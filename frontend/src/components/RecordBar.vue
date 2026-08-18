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
      class="record-bar pointer-events-auto fixed inset-x-0 bottom-0 z-[75] border-t border-brand-200/70 bg-white/95 px-2 py-1.5 pb-[max(0.4rem,env(safe-area-inset-bottom))] shadow-[0_-6px_20px_rgba(15,23,42,0.08)] backdrop-blur-sm"
    >
      <div class="mx-auto flex max-w-[1400px] flex-wrap items-center gap-2">
        <span class="chip shrink-0 bg-brand-100 text-brand-700">第 {{ segIndex + 1 }} / {{ segCount }} 段</span>
        <p class="hidden min-w-0 flex-1 truncate text-xs font-bold text-brand-600 sm:block">
          书上黄框就是要读的 · 每词最多 3 秒 · 读完可点停
        </p>
        <button
          class="chip shrink-0 bg-brand-100 text-brand-700 disabled:opacity-50"
          type="button"
          :disabled="cameraStarting"
          @click="emit('toggleCamera')"
        >
          {{ cameraEnabled ? '📷 关摄像头' : '📷 开摄像头' }}
        </button>
        <p v-if="cameraError && !cameraEnabled" class="hidden text-[11px] font-bold text-candy lg:block">
          {{ cameraError }}
        </p>

        <div v-if="recording" class="flex min-w-0 flex-1 items-center gap-2">
          <span
            class="w-8 shrink-0 text-center text-lg font-black tabular-nums"
            :class="recordLeft <= 3 ? 'text-candy' : 'text-brand-700'"
          >
            {{ Math.ceil(recordLeft) }}
          </span>
          <div class="h-1.5 min-w-[4rem] flex-1 overflow-hidden rounded-full bg-brand-100">
            <div
              class="h-full rounded-full"
              :class="recordLeft <= 3 ? 'bg-candy' : 'bg-sunny'"
              :style="{ width: recordTotal ? `${(recordLeft / recordTotal) * 100}%` : '0%' }"
            />
          </div>
          <span class="hidden shrink-0 text-[11px] font-bold text-brand-600/70 sm:inline">
            {{ recordWords }} 词 × 3 秒
          </span>
        </div>

        <p v-else-if="busy" class="min-w-0 flex-1 truncate text-xs font-bold text-brand-600/70">正在评分…</p>
        <p v-else-if="scoreError" class="min-w-0 flex-1 truncate text-xs font-bold text-candy">{{ scoreError }}</p>
        <p v-else-if="uploadHint" class="min-w-0 flex-1 truncate text-xs font-bold text-brand-600">{{ uploadHint }}</p>
        <p v-else-if="lastScore != null" class="min-w-0 flex-1 truncate text-xs font-extrabold" :class="passed ? 'text-mint' : 'text-candy'">
          {{ lastScore }} 分 · {{ passText }}
          <span v-if="lastHeard" class="font-bold text-brand-600/50"> · 听到：{{ lastHeard }}</span>
        </p>

        <div data-camera-pip-anchor class="ml-auto flex shrink-0 items-center gap-1.5">
          <button
            v-if="!recording && !busy"
            class="btn-candy px-3 py-1.5 text-xs sm:text-sm"
            type="button"
            @click="emit('start')"
          >
            {{ lastScore != null && !passed ? '再读一次' : '开始录音' }}
          </button>
          <button
            v-else-if="recording"
            class="btn-ghost px-3 py-1.5 text-xs sm:text-sm"
            type="button"
            @click="emit('stop')"
          >
            停
          </button>
          <button
            v-if="!recording && !busy && !passed"
            class="px-2 py-1 text-xs font-extrabold text-brand-600/70"
            type="button"
            @click="emit('skip')"
          >
            跳过这句
          </button>
          <button
            class="grid h-7 w-7 place-items-center rounded-full text-sm font-black text-brand-500 hover:bg-brand-50"
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
