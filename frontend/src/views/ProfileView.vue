<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '../api'
import { clubLink } from '../utils/username'
import { useUserStore } from '../stores/user'

const route = useRoute()
const user = useUserStore()
const data = ref<any>(null)
const userKey = computed(() => String(route.params.userKey || user.username))

onMounted(async () => {
  user.hydrate()
  data.value = await api(`/api/profile/${encodeURIComponent(userKey.value)}`)
})
</script>

<template>
  <div v-if="data" class="space-y-5">
    <div class="card">
      <h1 class="text-3xl font-extrabold text-brand-700">{{ data.user.nickname }}</h1>
      <p class="font-bold text-brand-600/70">{{ data.user.username }}</p>
      <p v-if="data.user.bio" class="mt-2 font-bold text-brand-600">{{ data.user.bio }}</p>
    </div>
    <h2 class="font-extrabold text-brand-700">公开朗读</h2>
    <p v-if="!data.works?.length" class="card font-bold text-brand-600/60">还没有公开作品。</p>
    <div class="grid gap-4 sm:grid-cols-2">
      <router-link v-for="work in data.works" :key="work.id" class="card block" :to="clubLink(`/square/${work.id}`)">
        <p class="font-extrabold text-brand-700">{{ work.bookTitle }} · 第 {{ work.page }} 页</p>
        <p class="text-sm font-bold text-brand-600">{{ work.overallScore }} 分 · ❤️ {{ work.likeCount }}</p>
      </router-link>
    </div>
  </div>
</template>
