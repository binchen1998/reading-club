<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '../api'
import { quizReportText, recordReportText } from '../utils/reportText'

const route = useRoute()
const date = String(route.query.date || '')
const items = ref<any[]>([])

onMounted(async () => {
  if (!date) return
  const data = await api(`/api/reports/day?date=${date}`)
  items.value = data.items || []
})
</script>

<template>
  <div class="space-y-4">
    <h1 class="text-3xl font-extrabold text-brand-700">{{ date }} 的学习</h1>
    <p v-if="!items.length" class="card font-bold text-brand-600/60">这天没有记录。</p>
    <div v-for="item in items" :key="`${item.bookSlug}-${item.page}`" class="card">
      <p class="font-extrabold text-brand-700">{{ item.bookTitle }} · 第 {{ item.page }} 页</p>
      <p class="font-bold text-brand-600">
        单词 {{ quizReportText(item.vocabDone, item.vocabRetries) }} ·
        短语 {{ quizReportText(item.phraseDone, item.phraseRetries) }} ·
        朗读 {{ recordReportText(item.recordDone, item.recordScore) }}
      </p>
    </div>
  </div>
</template>
