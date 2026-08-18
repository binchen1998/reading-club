<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '../api'

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
        单词 {{ item.vocabDone ? '已完成' : '未做' }} ·
        短语 {{ item.phraseDone ? '已完成' : '未做' }} ·
        朗读 {{ item.recordDone ? `已录 ${item.recordScore}分` : '未录' }}
      </p>
    </div>
  </div>
</template>
