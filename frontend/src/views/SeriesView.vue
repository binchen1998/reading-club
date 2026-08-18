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
  return clubLink(`/read/${seriesId}/${book.slug}/ch01`)
}

function bookLabel(book: BookRow) {
  if (!book.ready) return '仅书目'
  if (book.finished) return '再读'
  if (book.lastPage) return '继续'
  return '开始读'
}

function bookHint(book: BookRow) {
  if (!book.ready) return ''
  if (book.finished) return '已读完'
  if (book.lastPage) return `上次读到第 ${book.lastPage} 页`
  return ''
}
</script>

<template>
  <div v-if="data" class="space-y-5">
    <h1 class="text-3xl font-extrabold text-brand-700">{{ data.series.title }}</h1>
    <div class="grid gap-3 sm:grid-cols-2">
      <div v-for="book in data.books" :key="book.slug" class="card flex items-center gap-3 !py-4">
        <div class="min-w-0 flex-1">
          <p class="text-xs font-bold text-brand-500">No. {{ book.number }}</p>
          <h2 class="mt-0.5 text-xl font-extrabold leading-snug text-brand-700">{{ book.title }}</h2>
          <p v-if="bookHint(book)" class="mt-1 text-xs font-bold text-brand-600/50">{{ bookHint(book) }}</p>
        </div>
        <router-link
          v-if="book.ready"
          class="shrink-0 rounded-full px-3 py-1.5 text-sm font-extrabold"
          :class="book.lastPage ? 'btn-ghost !px-3 !py-1.5' : 'btn-primary !px-3 !py-1.5'"
          :to="bookLink(book)"
        >
          {{ bookLabel(book) }}
        </router-link>
        <p v-else class="shrink-0 text-sm font-bold text-brand-600/50">仅书目</p>
      </div>
    </div>
  </div>
</template>
