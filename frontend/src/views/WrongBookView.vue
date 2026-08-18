<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api'
import { clubLink } from '../utils/username'

const scope = ref<'current' | 'history'>('current')
const items = ref<any[]>([])

async function load() {
  const data = await api(`/api/wrongbook?scope=${scope.value}`)
  items.value = data.items || []
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <div>
      <h1 class="text-3xl font-extrabold text-brand-700">错题本</h1>
      <p class="mt-1 font-bold text-brand-600/80">词汇和短语混在一起。做对会从当前错题消失，历史里还留着。</p>
    </div>
    <div class="flex gap-2">
      <button
        class="rounded-full px-4 py-2 text-sm font-extrabold"
        :class="scope === 'current' ? 'bg-candy text-white' : 'bg-white text-brand-700'"
        type="button"
        @click="scope = 'current'; load()"
      >
        现在的错题
      </button>
      <button
        class="rounded-full px-4 py-2 text-sm font-extrabold"
        :class="scope === 'history' ? 'bg-candy text-white' : 'bg-white text-brand-700'"
        type="button"
        @click="scope = 'history'; load()"
      >
        历史错题
      </button>
    </div>
    <p v-if="!items.length" class="card font-bold text-brand-600/60">
      {{ scope === 'current' ? '太棒了，当前没有错题。' : '还没有历史错题。' }}
    </p>
    <div v-for="item in items" :key="item.id" class="card flex items-center justify-between gap-3">
      <div>
        <span class="chip bg-brand-100 text-brand-700">{{ item.kind === 'phrase' ? '短语' : '词汇' }}</span>
        <p class="mt-2 text-2xl font-extrabold text-brand-700">{{ item.en }}</p>
        <p class="font-bold text-brand-600">{{ item.zh }}</p>
        <p class="mt-1 text-sm font-bold text-brand-500">
          {{ item.bookTitle }} · 第 {{ item.page }} 页 · 错 {{ item.wrongCount }} 次
        </p>
      </div>
      <router-link
        v-if="item.seriesId && item.bookSlug && item.chapterId"
        class="btn-primary shrink-0"
        :to="clubLink(`/read/${item.seriesId}/${item.bookSlug}/${item.chapterId}`)"
      >
        再练
      </router-link>
    </div>
  </div>
</template>
