<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '../api'
import { clubLink } from '../utils/username'

const route = useRoute()
const data = ref<any>(null)

onMounted(async () => {
  data.value = await api(`/api/books/${route.params.seriesId}/${route.params.bookSlug}`)
})
</script>

<template>
  <div v-if="data" class="space-y-5">
    <div>
      <h1 class="text-3xl font-extrabold text-brand-700">{{ data.book.title }}</h1>
      <p class="mt-1 font-bold text-brand-600/80">还没有课稿的章节，第一次打开会现场生成讲解。</p>
    </div>
    <div class="space-y-3">
      <div v-for="ch in data.chapters" :key="ch.id" class="card flex items-center justify-between gap-4">
        <div>
          <p class="text-xl font-extrabold text-brand-700">{{ ch.title }}</p>
          <p class="font-bold text-brand-600/60">{{ ch.title_zh }}</p>
        </div>
        <router-link class="btn-candy shrink-0" :to="clubLink(`/read/${route.params.seriesId}/${route.params.bookSlug}/${ch.id}`)">
          {{ ch.generated ? '读这一章' : '生成并阅读' }}
        </router-link>
      </div>
      <p v-if="!data.chapters.length" class="font-bold text-brand-600/50">还没有开放的章节。</p>
    </div>
  </div>
</template>
