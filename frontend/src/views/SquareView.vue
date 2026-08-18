<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api'
import HomeRankPanel from '../components/HomeRankPanel.vue'
import Pagination from '../components/Pagination.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { clubLink } from '../utils/username'

const PAGE_SIZE = 12
const sort = ref('latest')
const page = ref(1)
const items = ref<any[]>([])
const total = ref(0)
const stats = ref<any>(null)
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const [list, s] = await Promise.all([
      api(`/api/square/list?sort=${sort.value}&page=${page.value}&page_size=${PAGE_SIZE}`),
      api('/api/square/stats'),
    ])
    items.value = list.items || []
    total.value = Number(list.total || 0)
    stats.value = s
  } finally {
    loading.value = false
  }
}

function onSort(next: string) {
  if (sort.value === next) return
  sort.value = next
  page.value = 1
  load()
}

function changePage(next: number) {
  page.value = next
  load()
}

onMounted(load)
</script>

<template>
  <div class="grid grid-cols-[minmax(0,1fr)_300px] items-start gap-3">
    <section class="min-w-0 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <h1 class="text-2xl font-extrabold text-brand-700 lg:text-3xl">朗读广场</h1>
          <div class="flex gap-1">
            <button
              class="rounded-full px-2.5 py-1 text-xs font-extrabold"
              :class="sort === 'latest' ? 'bg-candy text-white' : 'bg-white text-brand-700'"
              type="button"
              @click="onSort('latest')"
            >
              最新
            </button>
            <button
              class="rounded-full px-2.5 py-1 text-xs font-extrabold"
              :class="sort === 'likes' ? 'bg-candy text-white' : 'bg-white text-brand-700'"
              type="button"
              @click="onSort('likes')"
            >
              最热
            </button>
          </div>
        </div>
        <div class="square-stats-bar shrink-0">
          <div class="square-stat-item">
            <span class="square-stat-num">{{ stats?.publicCount ?? '—' }}</span>
            <span class="square-stat-label">公开</span>
          </div>
          <div class="square-stat-divider" />
          <div class="square-stat-item">
            <span class="square-stat-num">+{{ stats?.todayCount ?? 0 }}</span>
            <span class="square-stat-label">今日新增</span>
          </div>
        </div>
      </div>

      <p v-if="loading" class="card py-8 text-center font-bold text-brand-600/50">加载中…</p>
      <p v-else-if="!items.length" class="card font-bold text-brand-600/60">
        广场还没有作品，读完一页并选择公开就会出现。
      </p>
      <div v-else class="grid grid-cols-4 gap-2">
        <router-link
          v-for="item in items"
          :key="item.id"
          class="card block overflow-hidden !p-0 transition hover:-translate-y-0.5"
          :to="clubLink(`/square/${item.id}`)"
        >
          <div class="relative aspect-video overflow-hidden bg-brand-100">
            <img
              v-if="item.thumbUrl"
              :src="item.thumbUrl"
              alt=""
              class="h-full w-full object-cover"
            />
            <video
              v-else-if="item.videoUrl"
              :src="`${item.videoUrl}#t=0.4`"
              class="h-full w-full object-cover"
              muted
              playsinline
              preload="metadata"
            />
            <div v-else class="grid h-full place-items-center text-4xl">📖</div>
            <span
              class="absolute left-1.5 top-1.5 rounded-full bg-white/90 px-1.5 py-0.5 text-xs font-extrabold text-brand-600 shadow-sm"
            >
              {{ item.overallScore || 0 }}分
            </span>
          </div>
          <div class="space-y-1 p-2">
            <p class="truncate text-xs font-extrabold text-brand-700">
              {{ item.bookTitle }} · 第 {{ item.page }} 页
            </p>
            <div class="flex items-center gap-1.5">
              <UserAvatar :avatar="item.avatar" size="xs" />
              <span class="truncate text-xs font-bold text-brand-600/70">{{ item.nickname }}</span>
              <span class="ml-auto shrink-0 text-xs font-bold text-candy">♥ {{ item.likeCount || 0 }}</span>
            </div>
          </div>
        </router-link>
      </div>
      <Pagination :total="total" :page="page" :page-size="PAGE_SIZE" @change="changePage" />
    </section>
    <aside class="sticky top-0">
      <HomeRankPanel />
    </aside>
  </div>
</template>

<style scoped>
.square-stats-bar {
  display: flex;
  align-items: center;
  width: fit-content;
  background: #fff;
  border: 1px solid rgba(249, 115, 22, 0.28);
  border-radius: 0.9rem;
  padding: 6px 0;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.square-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 0 18px;
}

.square-stat-num {
  font-size: 0.95rem;
  font-weight: 800;
  color: #ea580c;
  line-height: 1.2;
}

.square-stat-label {
  font-size: 0.68rem;
  color: #fb923c;
  white-space: nowrap;
}

.square-stat-divider {
  width: 1px;
  height: 22px;
  background: rgba(251, 146, 60, 0.45);
  flex-shrink: 0;
}
</style>
