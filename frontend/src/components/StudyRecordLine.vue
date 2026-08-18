<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { clubLink } from '../utils/username'
import {
  quizReportIcon,
  quizReportLabel,
  recordReportIcon,
  recordReportLabel,
} from '../utils/reportText'

const props = defineProps<{
  item: {
    bookTitle?: string
    bookSlug?: string
    page: number
    vocabDone?: boolean
    vocabRetries?: number
    phraseDone?: boolean
    phraseRetries?: number
    recordDone?: boolean
    recordScore?: number
    videoUrl?: string
    recordingId?: number
  }
}>()

const router = useRouter()
const openTip = ref('')

const title = computed(() => `${props.item.bookTitle || props.item.bookSlug} · 第 ${props.item.page} 页`)
const vocabTip = computed(() => quizReportLabel('单词', !!props.item.vocabDone, props.item.vocabRetries))
const phraseTip = computed(() => quizReportLabel('短语', !!props.item.phraseDone, props.item.phraseRetries))
const recordTip = computed(() => recordReportLabel(!!props.item.recordDone, props.item.recordScore))

function toggleTip(key: string) {
  openTip.value = openTip.value === key ? '' : key
}

function closeTip() {
  openTip.value = ''
}

function openReading() {
  if (!props.item.recordingId) return
  router.push(clubLink(`/square/${props.item.recordingId}`))
}

onMounted(() => document.addEventListener('click', closeTip))
onUnmounted(() => document.removeEventListener('click', closeTip))
</script>

<template>
  <div class="flex items-center gap-1.5 rounded-2xl bg-brand-50 px-2 py-1.5 lg:gap-2 lg:px-3 lg:py-2">
    <p class="min-w-0 flex-1 truncate text-xs font-extrabold text-brand-700 lg:text-base" :title="title">{{ title }}</p>
    <div class="flex shrink-0 items-center gap-1">
      <button
        type="button"
        class="relative grid h-8 min-w-8 place-items-center rounded-xl bg-white px-1.5 text-sm font-black text-brand-700"
        :title="vocabTip"
        :aria-label="vocabTip"
        @click.stop="toggleTip('vocab')"
      >
        <span aria-hidden="true">🔤{{ quizReportIcon(!!item.vocabDone, item.vocabRetries) }}</span>
        <span
          v-if="openTip === 'vocab'"
          class="absolute left-1/2 top-full z-20 mt-1 -translate-x-1/2 whitespace-nowrap rounded-lg bg-brand-700 px-2 py-1 text-[11px] font-bold text-white shadow-pop"
        >{{ vocabTip }}</span>
      </button>
      <button
        type="button"
        class="relative grid h-8 min-w-8 place-items-center rounded-xl bg-white px-1.5 text-sm font-black text-brand-700"
        :title="phraseTip"
        :aria-label="phraseTip"
        @click.stop="toggleTip('phrase')"
      >
        <span aria-hidden="true">💬{{ quizReportIcon(!!item.phraseDone, item.phraseRetries) }}</span>
        <span
          v-if="openTip === 'phrase'"
          class="absolute left-1/2 top-full z-20 mt-1 -translate-x-1/2 whitespace-nowrap rounded-lg bg-brand-700 px-2 py-1 text-[11px] font-bold text-white shadow-pop"
        >{{ phraseTip }}</span>
      </button>
      <button
        type="button"
        class="relative grid h-8 min-w-8 place-items-center rounded-xl bg-white px-1.5 text-sm font-black text-brand-700"
        :title="recordTip"
        :aria-label="recordTip"
        @click.stop="toggleTip('record')"
      >
        <span aria-hidden="true">🎤{{ recordReportIcon(!!item.recordDone, item.recordScore) }}</span>
        <span
          v-if="openTip === 'record'"
          class="absolute left-1/2 top-full z-20 mt-1 -translate-x-1/2 whitespace-nowrap rounded-lg bg-brand-700 px-2 py-1 text-[11px] font-bold text-white shadow-pop"
        >{{ recordTip }}</span>
      </button>
      <button
        v-if="item.videoUrl"
        type="button"
        class="relative grid h-8 min-w-8 place-items-center rounded-xl bg-white px-1.5 text-sm font-black text-candy"
        title="看这页朗读"
        aria-label="看这页朗读"
        @click.stop="openReading"
      >
        <span aria-hidden="true">▶</span>
      </button>
    </div>
  </div>
</template>
