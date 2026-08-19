<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '../api'
import Pagination from '../components/Pagination.vue'
import ProfileEditDialog from '../components/ProfileEditDialog.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { useUserStore } from '../stores/user'
import { clubLink } from '../utils/username'
import { safeDisplayName } from '../utils/safeDisplayName'

const user = useUserStore()

const loading = ref(true)
const error = ref('')
const data = ref<any | null>(null)
const works = ref<any[]>([])
const worksTotal = ref(0)
const worksPage = ref(1)
const profileOpen = ref(false)
const modal = ref<'followers' | 'following' | ''>('')
const people = ref<any[]>([])
const peopleTotal = ref(0)
const peoplePage = ref(1)

const owner = computed(() => data.value?.user || user.profile || {})
const userKey = computed(() => String(owner.value.username || user.username || ''))

async function loadProfile() {
  if (!userKey.value) return
  data.value = await api(`/api/profile/${encodeURIComponent(userKey.value)}?page=1&page_size=1`)
}

async function loadWorks() {
  const res = await api(`/api/practice/mine?page=${worksPage.value}&page_size=12`)
  works.value = res.items || []
  worksTotal.value = res.total || 0
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await loadProfile()
    await loadWorks()
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function onProfileSaved() {
  if (!data.value) return
  data.value = {
    ...data.value,
    bio: user.profile?.bio || '',
    nickname: user.profile?.nickname,
    user: { ...data.value.user, ...user.profile },
  }
}

async function openPeople(type: 'followers' | 'following') {
  modal.value = type
  peoplePage.value = 1
  await loadPeople()
}

async function loadPeople() {
  if (!modal.value || !userKey.value) return
  const res = await api(
    `/api/profile/${encodeURIComponent(userKey.value)}/${modal.value}?page=${peoplePage.value}&page_size=20`,
  )
  people.value = res.items || []
  peopleTotal.value = res.total || 0
}

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
            <button type="button" class="btn-ghost px-3 py-1 text-xs" @click="profileOpen = true">
              编辑资料
            </button>
            <router-link class="btn-ghost px-3 py-1 text-xs" :to="clubLink('/me/home')">
              个人主页
            </router-link>
          </div>
          <p v-if="owner.username" class="mt-1 text-xs font-bold text-brand-600/50">
            ID：{{ owner.username }}
          </p>
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

      <section class="space-y-3">
        <h3 class="px-1 text-base font-extrabold text-brand-700">我的朗读</h3>
        <p v-if="error" class="text-sm font-bold text-candy">{{ error }}</p>
        <p v-if="!works.length" class="card py-6 text-center text-sm font-bold text-brand-600/40">
          还没有朗读作品。
        </p>
        <div v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <router-link
            v-for="work in works"
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
              <p class="truncate text-sm font-extrabold text-brand-700">
                {{ work.bookTitle }} · 第 {{ work.page }} 页
              </p>
              <p class="flex flex-wrap items-center gap-2 text-xs font-bold text-brand-600">
                <span>{{ work.overallScore }} 分 · ♥ {{ work.likeCount }}</span>
                <span
                  class="rounded-full px-2 py-0.5 text-[10px] font-extrabold"
                  :class="work.isPublic ? 'bg-mint/20 text-mint' : 'bg-brand-100 text-brand-600'"
                >
                  {{ work.isPublic ? '已公开' : '仅自己可见' }}
                </span>
              </p>
            </div>
          </router-link>
        </div>
        <Pagination
          :total="worksTotal"
          :page="worksPage"
          :page-size="12"
          @change="(n) => { worksPage = n; loadWorks() }"
        />
      </section>
    </template>

    <ProfileEditDialog :open="profileOpen" @close="profileOpen = false" @saved="onProfileSaved" />

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
          <span class="text-base font-bold text-brand-700">
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
