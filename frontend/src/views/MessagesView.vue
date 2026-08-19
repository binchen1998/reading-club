<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '../api'
import Pagination from '../components/Pagination.vue'
import { clubLink } from '../utils/username'
import { safeDisplayName } from '../utils/safeDisplayName'

const route = useRoute()
const router = useRouter()

const items = ref<any[]>([])
const total = ref(0)
const page = ref(Math.max(1, Number(route.query.msgPage) || 1))
const loading = ref(true)

const labels: Record<string, string> = {
  follow: '关注了你',
  comment: '评论了你的朗读',
  wall_message: '在你的留言板留言',
  like: '赞了你的朗读',
}

async function markAllReadOnce() {
  try {
    const res = await api('/api/users/notifications/read-all', { method: 'POST' })
    window.dispatchEvent(
      new CustomEvent('notifications-read-all', {
        detail: { unread_count: res?.unreadCount ?? res?.unread_count ?? 0 },
      }),
    )
  } catch {
    /* ignore */
  }
}

async function loadList() {
  loading.value = true
  try {
    const res = await api(`/api/users/notifications?page=${page.value}&page_size=20`)
    items.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

function open(item: any) {
  const type = item.type || item.kind
  const actor = item.actorUsername || item.actor_username
  const refId = item.refId || item.ref_id
  if ((type === 'comment' || type === 'like') && refId) {
    router.push(clubLink(`/square/${refId}`))
  } else if ((type === 'wall_message' || type === 'follow') && actor) {
    router.push(clubLink(`/user/${encodeURIComponent(actor)}`))
  }
}

function changePage(next: number) {
  page.value = next
  router.replace(clubLink(`/messages?msgPage=${next}`))
  loadList()
}

onMounted(async () => {
  await markAllReadOnce()
  await loadList()
})
</script>

<template>
  <div class="space-y-4">
    <section class="card">
      <h2 class="mb-3 text-lg font-extrabold text-brand-700">消息中心</h2>
      <div v-if="loading" class="py-8 text-center text-sm font-bold text-brand-600/50">加载中…</div>
      <div v-else-if="!items.length" class="py-8 text-center text-sm font-bold text-brand-600/50">
        暂时没有新消息
      </div>
      <button
        v-for="item in items"
        :key="item.id"
        type="button"
        class="flex w-full gap-3 border-t border-brand-100 py-3 text-left first:border-t-0"
        @click="open(item)"
      >
        <div class="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-50 text-base">
          {{ (item.type || item.kind) === 'follow' ? '👋' : (item.type || item.kind) === 'like' ? '♥' : '💬' }}
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-base font-bold text-brand-700">
            <span>{{
              safeDisplayName(item.actorNickname || item.actor_nickname, item.actorUsername || item.actor_username)
            }}</span>
            {{ labels[item.type || item.kind] || item.message || '发来一条消息' }}
          </p>
        </div>
        <time class="shrink-0 text-xs text-brand-600/40">
          {{ String(item.createdAt || item.created_at || '').slice(0, 10) }}
        </time>
      </button>
      <Pagination :total="total" :page="page" :page-size="20" @change="changePage" />
    </section>
  </div>
</template>
