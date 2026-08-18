<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api'
import { clubLink } from '../utils/username'

const data = ref<any>(null)

onMounted(async () => {
  data.value = await api('/api/catalog')
})
</script>

<template>
  <div v-if="data" class="space-y-5">
    <div>
      <h1 class="text-3xl font-extrabold text-brand-700">章节书书架</h1>
      <p class="mt-1 font-bold text-brand-600/80">先开放 Nate the Great 做实验，其它系列已经导入书目。</p>
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <component
        :is="s.readable ? 'router-link' : 'div'"
        v-for="s in data.series"
        :key="s.id"
        :to="s.readable ? clubLink(`/series/${s.id}`) : undefined"
        class="card block transition"
        :class="s.readable ? 'hover:bg-white' : 'opacity-60'"
      >
        <span class="chip" :class="s.readable ? 'bg-mint/15 text-mint' : 'bg-brand-100 text-brand-600'">
          {{ s.readable ? '可试读' : '已导入 · 暂未开放' }}
        </span>
        <h2 class="mt-3 text-xl font-extrabold text-brand-700">{{ s.title }}</h2>
        <p class="font-bold text-brand-600/60">{{ s.book_count }} 本</p>
      </component>
    </div>
  </div>
</template>
