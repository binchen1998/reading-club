<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '../api'
import { clubLink } from '../utils/username'

const route = useRoute()
const item = ref<any>(null)

async function load() {
  item.value = await api(`/api/square/${route.params.id}`)
}

async function like() {
  const res = await api(`/api/square/${route.params.id}/like`, { method: 'POST' })
  item.value = { ...item.value, liked: res.liked, likeCount: res.likeCount }
}

onMounted(load)
</script>

<template>
  <div v-if="item" class="mx-auto max-w-2xl space-y-4">
    <router-link class="font-extrabold text-brand-600" :to="clubLink('/square')">← 广场</router-link>
    <h1 class="text-2xl font-extrabold text-brand-700">{{ item.bookTitle }} · 第 {{ item.page }} 页</h1>
    <p class="font-bold text-brand-600">
      <router-link :to="clubLink(`/user/${encodeURIComponent(item.username)}`)">{{ item.nickname }}</router-link>
      · {{ item.overallScore }} 分
    </p>
    <video v-if="item.videoUrl" class="w-full rounded-3xl bg-black" :src="item.videoUrl" controls playsinline />
    <button class="btn-candy" type="button" @click="like">
      {{ item.liked ? '已赞' : '点赞' }} · {{ item.likeCount }}
    </button>
  </div>
</template>
