<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../api'
import MonthCalendar from '../components/MonthCalendar.vue'
import StudyRecordLine from '../components/StudyRecordLine.vue'
import { clubLink } from '../utils/username'
import { scheduleHomeActiveReport } from '../utils/plausible'
import { useUserStore } from '../stores/user'
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
  scheduleHomeActiveReport(user.username)
  await loadStats()
  await loadDay(selectedDate.value)
})
</script>

<template>
  <div class="space-y-3 lg:space-y-5">
    <div>
      <h1 class="text-2xl font-extrabold text-brand-700 lg:text-3xl">{{ user.nickname || user.username }} 的阅读首页</h1>
    </div>
    <div v-if="stats" class="grid grid-cols-4 gap-1.5 lg:gap-3">
      <div class="card !p-2 text-center lg:!p-5">
        <p class="text-xs font-extrabold text-brand-500">昨天</p>
        <p class="mt-0.5 text-lg font-extrabold text-brand-700 lg:mt-1 lg:text-2xl">{{ stats.yesterday_count || 0 }} 页</p>
        <p class="text-xs font-bold text-brand-600 lg:text-sm">{{ stats.yesterday_minutes || 0 }} 分钟</p>
      </div>
      <div class="card !p-2 text-center lg:!p-5">
        <p class="text-xs font-extrabold text-brand-500">本周</p>
        <p class="mt-0.5 text-lg font-extrabold text-brand-700 lg:mt-1 lg:text-2xl">{{ stats.week_count || 0 }} 页</p>
        <p class="text-xs font-bold text-brand-600 lg:text-sm">{{ stats.week_minutes || 0 }} 分钟</p>
      </div>
      <div class="card !p-2 text-center lg:!p-5">
        <p class="text-xs font-extrabold text-brand-500">本月</p>
        <p class="mt-0.5 text-lg font-extrabold text-brand-700 lg:mt-1 lg:text-2xl">{{ stats.month_count || 0 }} 页</p>
        <p class="text-xs font-bold text-brand-600 lg:text-sm">{{ stats.month_minutes || 0 }} 分钟</p>
      </div>
      <div class="card !p-2 text-center lg:!p-5">
        <p class="text-xs font-extrabold text-brand-500">总共</p>
        <p class="mt-0.5 text-lg font-extrabold text-brand-700 lg:mt-1 lg:text-2xl">{{ stats.total_count || 0 }} 页</p>
        <p class="text-xs font-bold text-brand-600 lg:text-sm">{{ stats.total_minutes || 0 }} 分钟</p>
      </div>
    </div>
    <div class="grid grid-cols-[minmax(0,min(20rem,38vw))_minmax(0,1fr)] gap-2 lg:gap-4">
      <MonthCalendar :selected-date="selectedDate" @select="loadDay" />
      <section class="card min-w-0 space-y-2 !p-3 lg:space-y-3 lg:!p-5">
        <div class="flex items-center justify-between gap-2">
          <h2 class="min-w-0 truncate text-base font-extrabold text-brand-700">{{ selectedDate }} 的学习</h2>
          <button class="btn-primary shrink-0 px-3 py-1.5 text-xs lg:px-5 lg:py-3 lg:text-base" type="button" @click="router.push(clubLink('/books'))">去读书</button>
        </div>
        <p v-if="!dayItems.length" class="font-bold text-brand-600/60">这天还没有按页记录。</p>
        <StudyRecordLine v-for="item in dayItems" :key="`${item.bookSlug}-${item.page}`" :item="item" />
      </section>
    </div>
  </div>
</template>
