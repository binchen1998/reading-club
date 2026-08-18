<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '../api'
import { clubLink } from '../utils/username'

const route = useRoute()
const data = ref<any>(null)

onMounted(async () => {
  data.value = await api(`/api/series/${route.params.seriesId}`)
})
</script>

<template>
  <div v-if="data" class="space-y-5">
    <h1 class="text-3xl font-extrabold text-brand-700">{{ data.series.title }}</h1>
    <p v-if="!data.series.readable" class="card font-bold text-brand-600">
      这个系列已入库，实验成功后再开放阅读。
    </p>
    <div class="grid gap-3 sm:grid-cols-2">
      <div v-for="book in data.books" :key="book.slug" class="card">
        <p class="text-xs font-bold text-brand-500">No. {{ book.number }}</p>
        <h2 class="mt-1 text-lg font-extrabold text-brand-700">{{ book.title }}</h2>
        <router-link
          v-if="book.readable"
          class="btn-primary mt-3"
          :to="clubLink(`/series/${route.params.seriesId}/${book.slug}`)"
        >开始读</router-link>
        <p v-else class="mt-3 font-bold text-brand-600/50">{{ book.ready ? '未开放' : '仅书目' }}</p>
      </div>
    </div>
  </div>
</template>
