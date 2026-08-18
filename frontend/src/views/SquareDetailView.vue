<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '../api'
import ModeratingBusy from '../components/ModeratingBusy.vue'
import Pagination from '../components/Pagination.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { useUserStore } from '../stores/user'
import { clubLink } from '../utils/username'
import { safeDisplayName } from '../utils/safeDisplayName'

const route = useRoute()
const user = useUserStore()

const recordingId = computed(() => Number(route.params.id))
const loading = ref(true)
const item = ref<any | null>(null)
const comment = ref('')
const comments = ref<any[]>([])
const commentsTotal = ref(0)
const commentsPage = ref(1)
const replyTo = ref<any | null>(null)
const posting = ref(false)
const liking = ref(false)
const removingId = ref<number | null>(null)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    item.value = await api(`/api/square/${recordingId.value}`)
    await loadComments()
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadComments() {
  const res = await api(`/api/square/${recordingId.value}/comments?page=${commentsPage.value}&page_size=20`)
  comments.value = res.items || []
  commentsTotal.value = res.total || 0
}

async function toggleLike() {
  if (!item.value || user.isGuest || liking.value) return
  liking.value = true
  try {
    const res = item.value.liked
      ? await api(`/api/square/${recordingId.value}/like`, { method: 'DELETE' })
      : await api(`/api/square/${recordingId.value}/like`, { method: 'POST' })
    item.value.liked = res.liked
    item.value.likeCount = res.likeCount ?? item.value.likeCount
  } finally {
    liking.value = false
  }
}

async function submitComment() {
  if (!comment.value.trim() || posting.value || user.isGuest) return
  posting.value = true
  error.value = ''
  try {
    await api(`/api/square/${recordingId.value}/comments`, {
      method: 'POST',
      body: JSON.stringify({
        content: comment.value.trim(),
        parent_id: replyTo.value?.id,
      }),
    })
    comment.value = ''
    replyTo.value = null
    await loadComments()
  } catch (e: any) {
    error.value = e?.message || '评论失败'
  } finally {
    posting.value = false
  }
}

async function removeComment(id: number) {
  if (removingId.value != null) return
  removingId.value = id
  try {
    await api(`/api/square/${recordingId.value}/comments/${id}`, { method: 'DELETE' })
    await loadComments()
  } catch (e: any) {
    error.value = e?.message || '删除失败'
  } finally {
    removingId.value = null
  }
}

function canDelete(row: any) {
  return row?.username === user.username || item.value?.username === user.username
}

function changeComments(next: number) {
  commentsPage.value = next
  loadComments()
}

watch(recordingId, () => {
  commentsPage.value = 1
  replyTo.value = null
  comment.value = ''
  load()
})

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <router-link class="font-extrabold text-brand-600" :to="clubLink('/square')">← 广场</router-link>
    <div v-if="loading" class="card py-10 text-center font-bold text-brand-600/50">加载中…</div>
    <div v-else-if="error && !item" class="card py-10 text-center font-bold text-candy">{{ error }}</div>
    <template v-else-if="item">
      <div class="card overflow-hidden !p-0">
        <div class="flex flex-col lg:flex-row">
          <div class="relative max-h-[50vh] w-full bg-black lg:w-1/2">
            <video
              class="max-h-[50vh] w-full object-contain"
              :src="item.videoUrl"
              controls
              playsinline
            />
            <div
              v-if="item.overallScore > 0"
              class="absolute left-2 top-2 grid h-10 w-10 place-items-center rounded-xl bg-brand-500 text-sm font-black text-white shadow-pop"
            >
              {{ item.overallScore }}
            </div>
          </div>
          <div class="flex min-w-0 flex-1 flex-col gap-3 p-4">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <h2 class="truncate text-lg font-extrabold text-brand-700">
                  {{ item.bookTitle }} · 第 {{ item.page }} 页
                </h2>
                <p v-if="item.lessonDate" class="mt-0.5 text-xs font-bold text-brand-600/60">
                  课次日期：{{ item.lessonDate }}
                </p>
              </div>
              <button
                v-if="!user.isGuest"
                type="button"
                class="shrink-0 rounded-full px-3 py-1.5 text-sm font-bold disabled:opacity-50"
                :class="item.liked ? 'bg-candy text-white' : 'bg-candy/10 text-candy'"
                :disabled="liking"
                @click="toggleLike"
              >
                {{ liking ? '…' : '♥' }} {{ item.likeCount || 0 }}
              </button>
              <span v-else class="shrink-0 rounded-full bg-candy/10 px-3 py-1.5 text-sm font-bold text-candy">
                ♥ {{ item.likeCount || 0 }}
              </span>
            </div>
            <router-link
              class="flex items-center gap-2 text-left"
              :to="clubLink(`/user/${encodeURIComponent(item.username)}`)"
            >
              <UserAvatar :avatar="item.avatar" size="sm" rounded="xl" />
              <div class="min-w-0">
                <div class="truncate font-extrabold text-brand-700">
                  {{ safeDisplayName(item.nickname, item.username) }}
                </div>
                <div class="text-xs text-brand-600/50">点击查看主页</div>
              </div>
            </router-link>
          </div>
        </div>
      </div>

      <section class="card space-y-3">
        <h3 class="font-extrabold text-brand-700">评论</h3>
        <p v-if="replyTo" class="text-xs font-bold text-brand-600">
          回复 {{ safeDisplayName(replyTo.authorName, replyTo.username) }}
          <button type="button" class="ml-2 text-candy" @click="replyTo = null">取消</button>
        </p>
        <div v-if="!user.isGuest" class="flex gap-2">
          <input
            v-model="comment"
            class="min-w-0 flex-1 rounded-2xl border-2 border-brand-200 px-3 py-2 text-sm outline-none focus:border-brand-400"
            maxlength="500"
            placeholder="说点好听的…"
          />
          <button
            type="button"
            class="btn-primary shrink-0 px-4 py-2 text-sm"
            :disabled="posting || !comment.trim()"
            @click="submitComment"
          >
            {{ posting ? '审核中…' : '发送' }}
          </button>
        </div>
        <p v-if="error" class="text-sm font-bold text-candy">{{ error }}</p>
        <div v-if="!comments.length" class="py-4 text-center text-sm font-bold text-brand-600/40">暂无评论</div>
        <div v-for="c in comments" :key="c.id" class="rounded-2xl bg-brand-50 p-3">
          <div class="flex gap-2">
            <UserAvatar :avatar="c.authorAvatar" size="sm" />
            <div class="min-w-0 flex-1">
              <p class="text-xs font-bold text-brand-600/70">
                {{ safeDisplayName(c.authorName, c.username) }}
              </p>
              <p class="mt-0.5 text-sm text-brand-700">{{ c.content }}</p>
              <button
                v-if="!user.isGuest"
                type="button"
                class="mt-1 text-xs font-bold text-brand-500"
                @click="replyTo = c"
              >
                回复
              </button>
              <button
                v-if="canDelete(c)"
                type="button"
                class="ml-3 text-xs font-bold text-brand-600/40"
                :disabled="removingId === c.id"
                @click="removeComment(c.id)"
              >
                {{ removingId === c.id ? '删除中…' : '删除' }}
              </button>
            </div>
          </div>
          <div
            v-for="reply in c.replies || []"
            :key="reply.id"
            class="ml-8 mt-2 flex gap-2 border-l-2 border-brand-200 pl-3"
          >
            <UserAvatar :avatar="reply.authorAvatar" size="xs" />
            <div>
              <p class="text-xs font-bold text-brand-600/70">
                {{ safeDisplayName(reply.authorName, reply.username) }}
              </p>
              <p class="text-sm text-brand-700">{{ reply.content }}</p>
              <button
                v-if="!user.isGuest"
                type="button"
                class="mt-1 text-xs font-bold text-brand-500"
                @click="replyTo = reply"
              >
                回复
              </button>
              <button
                v-if="canDelete(reply)"
                type="button"
                class="ml-3 text-xs font-bold text-brand-600/40"
                :disabled="removingId === reply.id"
                @click="removeComment(reply.id)"
              >
                {{ removingId === reply.id ? '删除中…' : '删除' }}
              </button>
            </div>
          </div>
        </div>
        <Pagination :total="commentsTotal" :page="commentsPage" :page-size="20" @change="changeComments" />
      </section>
    </template>
    <ModeratingBusy :open="posting" text="正在用 AI 审核评论，请稍等。" />
  </div>
</template>
