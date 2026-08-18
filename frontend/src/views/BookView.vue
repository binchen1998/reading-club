<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '../api'
import { clubLink } from '../utils/username'

const route = useRoute()
const router = useRouter()
const data = ref<any>(null)
const error = ref('')

onMounted(async () => {
  try {
    data.value = await api(`/api/books/${route.params.seriesId}/${route.params.bookSlug}`)
    const chapterId = data.value?.chapters?.[0]?.id || 'ch01'
    await router.replace(
      clubLink(`/read/${route.params.seriesId}/${route.params.bookSlug}/${chapterId}`),
    )
  } catch (e: any) {
    error.value = e?.message || '打不开这本书'
  }
})
</script>

<template>
  <div class="space-y-5">
    <p v-if="error" class="font-bold text-candy">{{ error }}</p>
    <p v-else class="font-bold text-brand-600/70">正在打开全书…</p>
  </div>
</template>
