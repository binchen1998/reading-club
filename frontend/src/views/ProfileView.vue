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

const userKey = computed(() => decodeURIComponent(String(route.params.userKey || user.username || '')))
const loading = ref(true)
const data = ref<any | null>(null)
const error = ref('')
const toggling = ref(false)
const worksPage = ref(1)
const wall = ref<any[]>([])
const wallTotal = ref(0)
const wallPage = ref(1)
const wallContent = ref('')
const replyTo = ref<any | null>(null)
const wallPosting = ref(false)
const removingWallId = ref<number | null>(null)
const modal = ref<'followers' | 'following' | ''>('')
const people = ref<any[]>([])
const peopleTotal = ref(0)
const peoplePage = ref(1)
const nickInput = ref('')
const nickError = ref('')
const savingNick = ref(false)
const bioInput = ref('')
const bioError = ref('')
const savingBio = ref(false)
const activeTab = ref<'works' | 'wall'>('works')

const owner = computed(() => data.value?.user || data.value || {})
const isSelf = computed(() => Boolean(data.value?.isSelf || owner.value.username === user.username))
const moderatingText = computed(() => {
  if (savingNick.value) return '正在用 AI 审核昵称，请稍等。'
  if (savingBio.value) return '正在用 AI 审核个人介绍，请稍等。'
  if (wallPosting.value) return '正在用 AI 审核留言，请稍等。'
  return '正在用 AI 审核，请稍等。'
})

async function load() {
  if (!userKey.value) return
  loading.value = true
  error.value = ''
  try {
    data.value = await api(
      `/api/profile/${encodeURIComponent(userKey.value)}?page=${worksPage.value}&page_size=12`,
    )
    nickInput.value = user.profile?.hasCustomNickname ? user.profile.nickname : ''
    bioInput.value = owner.value.bio || ''
    await loadWall()
  } catch (e: any) {
    error.value = e?.message || '加载失败'
    data.value = null
  } finally {
    loading.value = false
  }
}

async function loadWall() {
  const res = await api(
    `/api/profile/${encodeURIComponent(userKey.value)}/messages?page=${wallPage.value}&page_size=20`,
  )
  wall.value = res.items || []
  wallTotal.value = res.total || 0
}

async function toggleFollow() {
  if (!data.value || user.isGuest || isSelf.value) return
  toggling.value = true
  try {
    const key = encodeURIComponent(owner.value.username || userKey.value)
    const res = data.value.isFollowing
      ? await api(`/api/profile/${key}/unfollow`, { method: 'POST' })
      : await api(`/api/profile/${key}/follow`, { method: 'POST' })
    data.value.isFollowing = res.following ?? res.isFollowing
    data.value.followers = res.followers
  } finally {
    toggling.value = false
  }
}

async function postWall() {
  if (!wallContent.value.trim() || wallPosting.value || user.isGuest) return
  wallPosting.value = true
  error.value = ''
  try {
    await api(`/api/profile/${encodeURIComponent(userKey.value)}/messages`, {
      method: 'POST',
      body: JSON.stringify({
        content: wallContent.value.trim(),
        parent_id: replyTo.value?.id,
      }),
    })
    wallContent.value = ''
    replyTo.value = null
    await loadWall()
  } catch (e: any) {
    error.value = e?.message || '留言未通过审核'
  } finally {
    wallPosting.value = false
  }
}

async function removeWall(id: number) {
  if (removingWallId.value != null) return
  removingWallId.value = id
  try {
    await api(`/api/profile/${encodeURIComponent(userKey.value)}/messages/${id}`, { method: 'DELETE' })
    await loadWall()
  } catch (e: any) {
    error.value = e?.message || '删除失败'
  } finally {
    removingWallId.value = null
  }
}

async function openPeople(type: 'followers' | 'following') {
  modal.value = type
  peoplePage.value = 1
  await loadPeople()
}

async function loadPeople() {
  if (!modal.value) return
  const res = await api(
    `/api/profile/${encodeURIComponent(userKey.value)}/${modal.value}?page=${peoplePage.value}&page_size=20`,
  )
  people.value = res.items || []
  peopleTotal.value = res.total || 0
}

async function saveNickname() {
  const value = nickInput.value.trim()
  if (!value) {
    nickError.value = '请填写昵称'
    return
  }
  savingNick.value = true
  nickError.value = ''
  try {
    await user.setNickname(value)
    data.value = { ...data.value, user: { ...data.value.user, ...user.profile } }
  } catch (e: any) {
    nickError.value = e?.message || '昵称未通过审核或已被使用'
  } finally {
    savingNick.value = false
  }
}

async function saveBio() {
  savingBio.value = true
  bioError.value = ''
  try {
    await user.setBio(bioInput.value.trim())
    data.value = {
      ...data.value,
      bio: user.profile?.bio || '',
      user: { ...data.value.user, ...user.profile },
    }
  } catch (e: any) {
    bioError.value = e?.message || '个人介绍未通过审核'
  } finally {
    savingBio.value = false
  }
}

watch(userKey, () => {
  worksPage.value = 1
  wallPage.value = 1
  activeTab.value = 'works'
  load()
})

onMounted(async () => {
  user.hydrate()
  if (user.username) await user.loadMe()
  await load()
})
</script>

<template>
  <div class="space-y-4">
    <div v-if="loading" class="card py-10 text-center font-bold text-brand-600/50">加载中…</div>
    <div v-else-if="error && !data" class="card py-10 text-center font-bold text-candy">{{ error }}</div>
    <template v-else-if="data">
      <section class="card flex flex-wrap items-center gap-4">
        <UserAvatar :avatar="owner.avatarUrl || owner.avatar" size="xl" rounded="2xl" />
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <h2 class="truncate text-xl font-extrabold text-brand-700">
              {{ safeDisplayName(owner.nickname, owner.username) }}
            </h2>
            <button
              v-if="!isSelf && !user.isGuest"
              type="button"
              class="rounded-full px-3 py-1 text-xs font-bold text-white"
              :class="data.isFollowing ? 'bg-slate-400' : 'bg-brand-500'"
              :disabled="toggling"
              @click="toggleFollow"
            >
              {{ toggling ? '…' : data.isFollowing ? '已关注' : '关注' }}
            </button>
          </div>
          <p class="mt-1 text-xs font-bold text-brand-600/60">
            <button type="button" @click="openPeople('followers')">粉丝 {{ data.followers ?? 0 }}</button>
            ·
            <button type="button" @click="openPeople('following')">关注 {{ data.following ?? 0 }}</button>
          </p>
          <p class="mt-2 line-clamp-2 text-sm text-brand-600/80">
            {{ owner.bio || '这个人很神秘，还没有写介绍…' }}
          </p>
        </div>
      </section>

      <div v-if="isSelf" class="card space-y-4">
        <div class="space-y-2">
          <label class="text-xs font-bold text-brand-600">公开昵称（必须唯一，提交后由 AI 审核）</label>
          <div class="flex gap-2">
            <input
              v-model="nickInput"
              maxlength="50"
              class="min-w-0 flex-1 rounded-2xl border-2 border-brand-200 px-3 py-2 text-sm font-bold outline-none focus:border-brand-400"
              placeholder="给自己起一个独一无二的昵称"
            />
            <button class="btn-primary px-4 text-sm" type="button" :disabled="savingNick" @click="saveNickname">
              {{ savingNick ? '审核中…' : '保存' }}
            </button>
          </div>
          <p v-if="nickError" class="text-sm font-bold text-candy">{{ nickError }}</p>
        </div>
        <div class="space-y-2">
          <label class="text-xs font-bold text-brand-600">个人介绍（提交后由 AI 审核）</label>
          <div class="flex gap-2">
            <input
              v-model="bioInput"
              maxlength="200"
              class="min-w-0 flex-1 rounded-2xl border-2 border-brand-200 px-3 py-2 text-sm font-bold outline-none focus:border-brand-400"
              placeholder="介绍一下自己"
            />
            <button class="btn-primary px-4 text-sm" type="button" :disabled="savingBio" @click="saveBio">
              {{ savingBio ? '审核中…' : '保存' }}
            </button>
          </div>
          <p v-if="bioError" class="text-sm font-bold text-candy">{{ bioError }}</p>
        </div>
      </div>

      <div class="flex gap-1 overflow-x-auto rounded-2xl bg-white/80 p-1 shadow-sm">
        <button
          type="button"
          class="shrink-0 rounded-xl px-3 py-2 text-sm font-extrabold"
          :class="activeTab === 'works' ? 'bg-brand-500 text-white shadow-pop' : 'text-brand-600 hover:bg-white'"
          @click="activeTab = 'works'"
        >
          公开朗读
        </button>
        <button
          type="button"
          class="shrink-0 rounded-xl px-3 py-2 text-sm font-extrabold"
          :class="activeTab === 'wall' ? 'bg-brand-500 text-white shadow-pop' : 'text-brand-600 hover:bg-white'"
          @click="activeTab = 'wall'"
        >
          留言板
        </button>
      </div>

      <div v-show="activeTab === 'works'" class="space-y-3">
        <p v-if="!data.works?.length" class="card py-6 text-center text-sm font-bold text-brand-600/40">
          还没有公开作品。
        </p>
        <div v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <router-link
            v-for="work in data.works"
            :key="work.id"
            class="card overflow-hidden !p-0"
            :to="clubLink(`/square/${work.id}`)"
          >
            <div class="aspect-video overflow-hidden bg-slate-900">
              <img v-if="work.thumbUrl" :src="work.thumbUrl" alt="" class="h-full w-full object-cover" />
              <video
                v-else-if="work.videoUrl"
                :src="`${work.videoUrl}#t=2`"
                class="h-full w-full object-cover"
                muted
                playsinline
                preload="metadata"
              />
              <div v-else class="grid h-full place-items-center text-3xl">📖</div>
            </div>
            <div class="p-2">
              <p class="truncate text-xs font-extrabold text-brand-700">
                {{ work.bookTitle }} · 第 {{ work.page }} 页
              </p>
              <p class="text-xs font-bold text-brand-600">{{ work.overallScore }} 分 · ♥ {{ work.likeCount }}</p>
            </div>
          </router-link>
        </div>
        <Pagination
          :total="data.worksTotal || data.total || 0"
          :page="worksPage"
          :page-size="12"
          @change="(n) => { worksPage = n; load() }"
        />
      </div>

      <div v-show="activeTab === 'wall'" class="card space-y-3">
        <p class="text-xs font-bold text-brand-600/50">留言经审核后展示</p>
        <div v-if="!user.isGuest" class="space-y-2">
          <p v-if="replyTo" class="text-xs font-bold text-brand-600">
            回复 {{ safeDisplayName(replyTo.authorName, replyTo.authorUsername || replyTo.username) }}
            <button type="button" class="ml-2 text-candy" @click="replyTo = null">取消</button>
          </p>
          <div class="flex gap-2">
            <input
              v-model="wallContent"
              maxlength="500"
              class="min-w-0 flex-1 rounded-2xl border-2 border-brand-200 px-3 py-2 text-sm outline-none focus:border-brand-400"
              placeholder="写下想说的话…"
              :disabled="wallPosting"
              @keyup.enter="postWall"
            />
            <button
              type="button"
              class="btn-primary shrink-0 px-4 py-2 text-sm"
              :disabled="wallPosting || !wallContent.trim()"
              @click="postWall"
            >
              {{ wallPosting ? '审核中…' : '发送' }}
            </button>
          </div>
          <p v-if="error" class="text-sm font-bold text-candy">{{ error }}</p>
        </div>
        <div v-if="!wall.length" class="py-4 text-center text-sm font-bold text-brand-600/40">还没有留言</div>
        <div v-for="message in wall" :key="message.id" class="rounded-2xl bg-brand-50 p-3">
          <div class="flex gap-2">
            <UserAvatar :avatar="message.authorAvatar" size="sm" />
            <div class="min-w-0 flex-1">
              <p class="text-xs font-bold text-brand-600/70">
                {{ safeDisplayName(message.authorName, message.authorUsername || message.username) }}
              </p>
              <p class="text-sm text-brand-700">{{ message.content }}</p>
              <button
                v-if="!user.isGuest"
                type="button"
                class="mt-1 text-xs font-bold text-brand-500"
                @click="replyTo = message"
              >
                回复
              </button>
              <button
                v-if="isSelf || (message.authorUsername || message.username) === user.username"
                type="button"
                class="ml-3 text-xs font-bold text-brand-600/40"
                :disabled="removingWallId === message.id"
                @click="removeWall(message.id)"
              >
                {{ removingWallId === message.id ? '删除中…' : '删除' }}
              </button>
            </div>
          </div>
          <div
            v-for="reply in message.replies || []"
            :key="reply.id"
            class="ml-8 mt-2 flex gap-2 border-l-2 border-brand-200 pl-3"
          >
            <UserAvatar :avatar="reply.authorAvatar" size="xs" />
            <div>
              <p class="text-xs font-bold text-brand-600/70">
                {{ safeDisplayName(reply.authorName, reply.authorUsername || reply.username) }}
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
                v-if="isSelf || (reply.authorUsername || reply.username) === user.username"
                type="button"
                class="ml-3 text-xs font-bold text-brand-600/40"
                :disabled="removingWallId === reply.id"
                @click="removeWall(reply.id)"
              >
                {{ removingWallId === reply.id ? '删除中…' : '删除' }}
              </button>
            </div>
          </div>
        </div>
        <Pagination :total="wallTotal" :page="wallPage" :page-size="20" @change="(n) => { wallPage = n; loadWall() }" />
      </div>
    </template>

    <ModeratingBusy :open="user.moderating || wallPosting" :text="moderatingText" />

    <div
      v-if="modal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-2"
      @click.self="modal = ''"
    >
      <div class="card max-h-[85vh] w-full max-w-sm overflow-y-auto">
        <div class="mb-2 flex justify-between">
          <h3 class="font-extrabold text-brand-700">{{ modal === 'followers' ? '粉丝' : '关注' }}</h3>
          <button type="button" class="btn-ghost px-2 py-1 text-xs" @click="modal = ''">关闭</button>
        </div>
        <router-link
          v-for="person in people"
          :key="person.username"
          class="mt-2 flex items-center gap-2"
          :to="clubLink(`/user/${encodeURIComponent(person.username)}`)"
          @click="modal = ''"
        >
          <UserAvatar :avatar="person.avatar" size="sm" />
          <span class="text-sm font-bold text-brand-700">
            {{ safeDisplayName(person.nickname, person.username) }}
          </span>
        </router-link>
        <p v-if="!people.length" class="py-6 text-center text-sm font-bold text-brand-600/40">暂无</p>
        <Pagination
          :total="peopleTotal"
          :page="peoplePage"
          :page-size="20"
          @change="(n) => { peoplePage = n; loadPeople() }"
        />
      </div>
    </div>
  </div>
</template>
