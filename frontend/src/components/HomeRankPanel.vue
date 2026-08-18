<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../api'
import { useUserStore } from '../stores/user'
import { clubLink } from '../utils/username'
import { safeDisplayName } from '../utils/safeDisplayName'
import UserAvatar from './UserAvatar.vue'

const RANK_TABS = ['rise', 'talent', 'honor'] as const
type RankTab = (typeof RANK_TABS)[number]

const user = useUserStore()
const router = useRouter()
const tab = ref<RankTab>('rise')
const loading = ref(false)
const list = ref<any[]>([])
const weekLabel = ref('')
const myRank = ref<number | null>(null)
let loadSeq = 0

const panelTitle = computed(() => {
  if (tab.value === 'rise') return '本周上升榜'
  if (tab.value === 'talent') return '达人榜'
  return '荣誉榜'
})

const meUsername = computed(() => user.profile?.username || user.username)

const selfRankLabel = computed(() => {
  if (myRank.value != null) return `#${myRank.value}`
  const hit = list.value.find((e) => e.username === meUsername.value)
  if (hit?.rank != null) return `#${hit.rank}`
  if (tab.value === 'rise') return '本周暂无朗读'
  if (tab.value === 'talent') return '暂无公开作品'
  return '暂无数据'
})

function isSelf(e: any): boolean {
  return !!meUsername.value && e.username === meUsername.value
}

function displayValue(e: any): string {
  if (tab.value === 'rise') return `+${e.weeklyRise ?? e.weekly_rise ?? 0}`
  if (tab.value === 'honor') return String(e.honorPoints ?? e.honor_points ?? 0)
  return String(e.rating ?? 0)
}

function subline(e: any): string {
  if (tab.value === 'rise') return `本周朗读 ${e.matchCount ?? e.match_count ?? 0} 页`
  if (tab.value === 'honor') return '公开作品获赞'
  return `公开 ${e.workCount ?? 0} 篇 · 均分 ${e.avgScore ?? '-'}`
}

function openProfile(e: any) {
  if (!e.username) return
  router.push(clubLink(`/user/${encodeURIComponent(e.username)}`))
}

async function load() {
  const seq = ++loadSeq
  const currentTab = tab.value
  loading.value = true
  try {
    const path =
      currentTab === 'rise'
        ? '/api/leaderboard/rise'
        : currentTab === 'talent'
          ? '/api/leaderboard'
          : '/api/leaderboard/honor'
    const data = await api(path)
    if (seq !== loadSeq || tab.value !== currentTab) return
    list.value = data.entries || []
    weekLabel.value = data.weekLabel || ''
    myRank.value = data.myRank ?? null
  } catch {
    if (seq === loadSeq && tab.value === currentTab) {
      list.value = []
      myRank.value = null
    }
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

watch(tab, load, { immediate: true })
</script>

<template>
  <div class="card !p-3.5">
    <div class="mb-2.5 space-y-2">
      <div class="min-w-0">
        <div class="text-sm font-extrabold leading-tight text-brand-700">{{ panelTitle }}</div>
        <p v-if="tab === 'rise' && weekLabel" class="mt-0.5 text-xs font-bold text-brand-600/50">
          本周 {{ weekLabel }}
        </p>
      </div>
      <div class="flex flex-wrap gap-1">
        <button
          v-for="t in ([
            ['rise', '上升'],
            ['talent', '达人'],
            ['honor', '荣誉'],
          ] as const)"
          :key="t[0]"
          type="button"
          class="rounded-full border px-2.5 py-1 text-xs font-bold transition"
          :class="
            tab === t[0]
              ? 'border-brand-500 bg-brand-500 text-white'
              : 'border-brand-200 bg-white text-brand-600 hover:bg-brand-50'
          "
          @click="tab = t[0]"
        >
          {{ t[1] }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="py-6 text-center text-sm font-bold text-brand-600/40">加载中…</div>
    <div v-else-if="!list.length" class="py-6 text-center text-sm font-bold text-brand-600/40">
      {{
        tab === 'rise'
          ? '本周还没有上升记录（需本周有朗读）'
          : tab === 'talent'
            ? '暂无数据（公开朗读后计入达人榜）'
            : '暂无数据（公开作品获赞后计入荣誉榜）'
      }}
    </div>
    <div v-else class="max-h-[calc(100vh-9rem)] space-y-1.5 overflow-auto">
      <button
        v-for="e in list"
        :key="`${tab}-${e.rank}-${e.username}`"
        type="button"
        class="flex w-full items-center gap-2 rounded-xl px-1 py-1.5 text-left transition"
        :class="isSelf(e) ? 'bg-brand-50 ring-1 ring-brand-200' : 'hover:bg-brand-50/70'"
        @click="openProfile(e)"
      >
        <span class="w-7 shrink-0 text-center text-xs font-extrabold text-brand-600/40">#{{ e.rank }}</span>
        <UserAvatar :avatar="e.avatar" size="md" rounded="xl" />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-bold text-brand-700">{{ safeDisplayName(e.name, e.username) }}</p>
          <p class="truncate text-xs font-bold text-brand-600/50">{{ subline(e) }}</p>
        </div>
        <span
          class="shrink-0 text-sm font-extrabold"
          :class="tab === 'rise' ? 'text-mint' : tab === 'honor' ? 'text-candy' : 'text-brand-500'"
        >
          {{ displayValue(e) }}
        </span>
      </button>
    </div>

    <div v-if="user.username" class="mt-2.5 border-t border-brand-100 pt-2 text-xs font-bold text-brand-600/50">
      我的排名：{{ selfRankLabel }}
    </div>
  </div>
</template>
