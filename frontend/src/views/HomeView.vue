<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../api'
import MonthCalendar from '../components/MonthCalendar.vue'
import { clubLink } from '../utils/username'
import { useUserStore } from '../stores/user'
import { quizReportText, recordReportText } from '../utils/reportText'
import { serverTodayIso, syncServerTime } from '../utils/serverTime'

const router = useRouter()
const user = useUserStore()
const stats = ref<any>(null)
const selectedDate = ref(serverTodayIso())
const dayItems = ref<any[]>([])

async function loadStats() {
  const data = await api('/api/reports/home-stats')
  syncServerTime(data.server_now)
  stats.value = data
}

async function loadDay(date: string) {
  selectedDate.value = date
  const data = await api(`/api/reports/day?date=${date}`)
  dayItems.value = data.items || []
}

onMounted(async () => {
  user.hydrate()
  await user.loadMe()
  await loadStats()
  await loadDay(selectedDate.value)
})
</script>

<template>
  <div class="space-y-5">
    <div>
      <h1 class="text-3xl font-extrabold text-brand-700">{{ user.nickname || user.username }} 的阅读首页</h1>
      <p class="mt-1 font-bold text-brand-600/80">按页统计单词、短语和朗读。点日历看当天。</p>
    </div>
    <div v-if="stats" class="grid gap-3 sm:grid-cols-4">
      <div class="card text-center">
        <p class="text-xs font-extrabold text-brand-500">昨天</p>
        <p class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.yesterday_count || 0 }} 页</p>
        <p class="text-sm font-bold text-brand-600">{{ stats.yesterday_minutes || 0 }} 分钟</p>
      </div>
      <div class="card text-center">
        <p class="text-xs font-extrabold text-brand-500">本周</p>
        <p class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.week_count || 0 }} 页</p>
        <p class="text-sm font-bold text-brand-600">{{ stats.week_minutes || 0 }} 分钟</p>
      </div>
      <div class="card text-center">
        <p class="text-xs font-extrabold text-brand-500">本月</p>
        <p class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.month_count || 0 }} 页</p>
        <p class="text-sm font-bold text-brand-600">{{ stats.month_minutes || 0 }} 分钟</p>
      </div>
      <div class="card text-center">
        <p class="text-xs font-extrabold text-brand-500">总共</p>
        <p class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.total_count || 0 }} 页</p>
        <p class="text-sm font-bold text-brand-600">{{ stats.total_minutes || 0 }} 分钟</p>
      </div>
    </div>
    <div class="grid gap-4 lg:grid-cols-[320px_1fr]">
      <MonthCalendar :selected-date="selectedDate" @select="loadDay" />
      <section class="card space-y-3">
        <div class="flex items-center justify-between">
          <h2 class="font-extrabold text-brand-700">{{ selectedDate }} 的学习</h2>
          <button class="btn-primary" type="button" @click="router.push(clubLink('/books'))">去读书</button>
        </div>
        <p v-if="!dayItems.length" class="font-bold text-brand-600/60">这天还没有按页记录。</p>
        <div v-for="item in dayItems" :key="`${item.bookSlug}-${item.page}`" class="rounded-2xl bg-brand-50 px-4 py-3">
          <p class="font-extrabold text-brand-700">{{ item.bookTitle || item.bookSlug }} · 第 {{ item.page }} 页</p>
          <p class="mt-1 text-sm font-bold text-brand-600">
            单词 {{ quizReportText(item.vocabDone, item.vocabRetries) }}
            · 短语 {{ quizReportText(item.phraseDone, item.phraseRetries) }}
            · 朗读 {{ recordReportText(item.recordDone, item.recordScore) }}
          </p>
          <button
            v-if="item.videoUrl"
            class="mt-2 text-sm font-extrabold text-candy"
            type="button"
            @click="router.push(clubLink(`/square/${item.recordingId}`))"
          >
            看这页朗读
          </button>
        </div>
      </section>
    </div>
  </div>
</template>
