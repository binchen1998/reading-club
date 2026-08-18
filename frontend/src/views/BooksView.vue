<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api'
import { clubLink } from '../utils/username'
import { loadSeriesCovers } from '../utils/seriesCovers'

const data = ref<any>(null)
const covers = ref<Record<string, string>>({})

function coverOf(series: { id: string; cover?: string }) {
  return covers.value[series.id] || series.cover || ''
}

onMounted(async () => {
  const [catalog, coverMap] = await Promise.all([
    api('/api/catalog'),
    loadSeriesCovers().catch(() => ({})),
  ])
  data.value = catalog
  covers.value = coverMap
})
</script>

<template>
  <div v-if="data" class="space-y-5">
    <div>
      <h1 class="text-3xl font-extrabold text-brand-700">章节书书架</h1>
      <p class="mt-1 font-bold text-brand-600/80">页图直接用原站资源，打开就能读。</p>
    </div>
    <div class="grid grid-cols-5 gap-3">
      <router-link
        v-for="s in data.series"
        :key="s.id"
        :to="clubLink(`/series/${s.id}`)"
        class="card block overflow-hidden !p-0 transition hover:-translate-y-0.5 hover:bg-white"
      >
        <div class="aspect-[3/4] overflow-hidden bg-brand-100">
          <img v-if="coverOf(s)" :src="coverOf(s)" :alt="s.title" class="h-full w-full object-cover" />
          <div v-else class="grid h-full place-items-center text-3xl">📖</div>
        </div>
        <div class="space-y-0.5 p-2">
          <h2 class="line-clamp-2 text-base font-extrabold leading-snug text-brand-700">{{ s.title }}</h2>
          <p class="text-xs font-bold text-brand-600/60">{{ s.book_count }} 本</p>
        </div>
      </router-link>
    </div>
  </div>
</template>
