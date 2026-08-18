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
      <p class="mt-1 font-bold text-brand-600/80">页图直接用原站资源，打开就能读。</p>
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <router-link
        v-for="s in data.series"
        :key="s.id"
        :to="clubLink(`/series/${s.id}`)"
        class="card block transition hover:bg-white"
      >
        <span class="chip bg-mint/15 text-mint">可阅读</span>
        <h2 class="mt-3 text-xl font-extrabold text-brand-700">{{ s.title }}</h2>
        <p class="font-bold text-brand-600/60">{{ s.book_count }} 本</p>
      </router-link>
    </div>
  </div>
</template>
