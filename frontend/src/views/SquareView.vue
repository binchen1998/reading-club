<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api'
import { clubLink } from '../utils/username'

const sort = ref('latest')
const items = ref<any[]>([])
const stats = ref<any>(null)

async function load() {
  const [list, s] = await Promise.all([
    api(`/api/square/list?sort=${sort.value}`),
    api('/api/square/stats'),
  ])
  items.value = list.items || []
  stats.value = s
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-end justify-between gap-3">
      <div>
        <h1 class="text-3xl font-extrabold text-brand-700">朗读广场</h1>
        <p class="mt-1 font-bold text-brand-600/80">
          大家分享的朗读。公开作品 {{ stats?.publicCount || 0 }} · 今天 {{ stats?.todayCount || 0 }}
        </p>
      </div>
      <div class="flex gap-2">
        <button class="rounded-full px-3 py-1 text-sm font-extrabold" :class="sort === 'latest' ? 'bg-candy text-white' : 'bg-white'" type="button" @click="sort = 'latest'; load()">最新</button>
        <button class="rounded-full px-3 py-1 text-sm font-extrabold" :class="sort === 'likes' ? 'bg-candy text-white' : 'bg-white'" type="button" @click="sort = 'likes'; load()">最热</button>
      </div>
    </div>
    <p v-if="!items.length" class="card font-bold text-brand-600/60">广场还没有作品，读完一页并上传就会出现（worker 大约一分钟刷新）。</p>
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <router-link v-for="item in items" :key="item.id" class="card block" :to="clubLink(`/square/${item.id}`)">
        <p class="font-extrabold text-brand-700">{{ item.bookTitle }} · 第 {{ item.page }} 页</p>
        <p class="text-sm font-bold text-brand-600">{{ item.nickname }} · {{ item.overallScore }} 分 · ❤️ {{ item.likeCount }}</p>
      </router-link>
    </div>
  </div>
</template>
