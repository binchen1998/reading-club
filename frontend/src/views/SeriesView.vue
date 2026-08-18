<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '../api'
import { clubLink } from '../utils/username'

type BookRow = {
  slug: string
  title: string
  number?: number
  ready?: boolean
  lastPage?: number
  lastChapterId?: string
  finished?: boolean
}

const route = useRoute()
const data = ref<any>(null)

onMounted(async () => {
  data.value = await api(`/api/series/${route.params.seriesId}`)
})

function bookLink(book: BookRow) {
  const seriesId = String(route.params.seriesId)
  if (book.lastChapterId && book.lastPage) {
    return clubLink(`/read/${seriesId}/${book.slug}/${book.lastChapterId}?page=${book.lastPage}`)
  }
  return clubLink(`/series/${seriesId}/${book.slug}`)
}

function bookLabel(book: BookRow) {
  if (!book.ready) return '仅书目'
  if (book.finished) return '已读完'
  if (book.lastPage) return `上次读到第 ${book.lastPage} 页`
  return '开始读'
}
</script>

<template>
  <div v-if="data" class="space-y-5">
    <h1 class="text-3xl font-extrabold text-brand-700">{{ data.series.title }}</h1>
    <div class="grid gap-3 sm:grid-cols-2">
      <div v-for="book in data.books" :key="book.slug" class="card">
        <p class="text-xs font-bold text-brand-500">No. {{ book.number }}</p>
        <h2 class="mt-1 text-lg font-extrabold text-brand-700">{{ book.title }}</h2>
        <router-link
          v-if="book.ready"
          class="mt-3 w-full"
          :class="book.lastPage ? 'btn-ghost' : 'btn-primary'"
          :to="bookLink(book)"
        >
          {{ bookLabel(book) }}
        </router-link>
        <p v-else class="mt-3 font-bold text-brand-600/50">仅书目</p>
      </div>
    </div>
  </div>
</template>
