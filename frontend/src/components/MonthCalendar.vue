<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '../api'
import { serverNow, syncServerTime } from '../utils/serverTime'

const props = defineProps<{ selectedDate?: string }>()
const emit = defineEmits<{ select: [date: string] }>()

const today = serverNow().toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' })
const viewYear = ref(Number(today.slice(0, 4)))
const viewMonth = ref(Number(today.slice(5, 7)))
const report = ref<any>(null)
const weekdayLabels = ['一', '二', '三', '四', '五', '六', '日']

const monthTitle = computed(() => `${viewYear.value}年${viewMonth.value}月`)
const gridCells = computed(() => {
  const cells: Array<any | null> = []
  if (!report.value) return Array.from({ length: 42 }, () => null)
  for (let i = 0; i < report.value.first_weekday; i += 1) cells.push(null)
  for (const day of report.value.days || []) cells.push(day)
  while (cells.length < 42) cells.push(null)
  return cells
})

async function load() {
  const data = await api(`/api/reports/month?year=${viewYear.value}&month=${viewMonth.value}`)
  syncServerTime(data.server_now)
  report.value = data
}

function prevMonth() {
  if (viewMonth.value === 1) {
    viewYear.value -= 1
    viewMonth.value = 12
  } else viewMonth.value -= 1
}

function nextMonth() {
  if (viewMonth.value === 12) {
    viewYear.value += 1
    viewMonth.value = 1
  } else viewMonth.value += 1
}

function onDay(day: any) {
  if (!day || day.is_future || !day.active) return
  emit('select', day.date)
}

watch([viewYear, viewMonth], load)
onMounted(load)
</script>

<template>
  <section class="card">
    <div class="mb-3 flex items-center justify-between">
      <button class="font-extrabold text-brand-600" type="button" @click="prevMonth">‹</button>
      <p class="font-extrabold text-brand-700">{{ monthTitle }}</p>
      <button class="font-extrabold text-brand-600" type="button" @click="nextMonth">›</button>
    </div>
    <div class="grid grid-cols-7 gap-1 text-center text-xs font-bold text-brand-500">
      <span v-for="w in weekdayLabels" :key="w">{{ w }}</span>
    </div>
    <div class="mt-1 grid grid-cols-7 gap-1">
      <button
        v-for="(day, i) in gridCells"
        :key="i"
        type="button"
        class="aspect-square rounded-xl text-sm font-extrabold"
        :class="!day
          ? 'invisible'
          : day.is_future
            ? 'text-brand-300'
            : day.active
              ? (props.selectedDate === day.date ? 'bg-candy text-white' : 'bg-mint/20 text-mint')
              : 'text-brand-600'"
        :disabled="!day || day.is_future || !day.active"
        @click="onDay(day)"
      >
        {{ day?.day || '' }}
      </button>
    </div>
    <p class="mt-3 text-xs font-bold text-brand-500">绿底表示那天有学习。点日期看每页完成情况。</p>
  </section>
</template>
