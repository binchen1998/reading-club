<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ADMIN_TOKEN_KEY, adminApi } from '../api'

const route = useRoute()
const router = useRouter()

const TABS = [
  { key: 'overview', label: '概览' },
  { key: 'users', label: '用户' },
  { key: 'practices', label: '朗读' },
  { key: 'wall', label: '留言' },
  { key: 'wrongs', label: '错题' },
  { key: 'assets', label: '资源' },
] as const

const tab = ref((route.params.tab as string) || 'overview')
const username = ref('admin')
const password = ref('')
const loggedIn = ref(!!localStorage.getItem(ADMIN_TOKEN_KEY))
const loggingIn = ref(false)
const error = ref('')
const stats = ref<any>(null)
const users = ref<any[]>([])
const practices = ref<any[]>([])
const wrongs = ref<any[]>([])
const assets = ref<any[]>([])
const wallItems = ref<any[]>([])
const wallStatus = ref('pending')
const userQuery = ref('')
const muting = ref('')
const assetKind = ref('all')
const wrongStatus = ref('open')

async function login() {
  if (loggingIn.value) return
  error.value = ''
  loggingIn.value = true
  try {
    const res = await adminApi('/api/admin/login', {
      method: 'POST',
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value,
      }),
    })
    localStorage.setItem(ADMIN_TOKEN_KEY, res.token)
    loggedIn.value = true
    await loadTab()
  } catch (e: any) {
    error.value = e?.message || '登录失败'
  } finally {
    loggingIn.value = false
  }
}

function logout() {
  localStorage.removeItem(ADMIN_TOKEN_KEY)
  loggedIn.value = false
}

async function loadTab() {
  if (!loggedIn.value) return
  error.value = ''
  try {
    if (tab.value === 'overview') {
      stats.value = await adminApi('/api/admin/stats')
    }
    if (tab.value === 'users') {
      const res = await adminApi(
        `/api/admin/users?q=${encodeURIComponent(userQuery.value.trim())}&limit=200`,
      )
      users.value = Array.isArray(res) ? res : res?.items || []
    }
    if (tab.value === 'practices') {
      const res = await adminApi('/api/admin/practices?limit=100')
      practices.value = res.items || res || []
    }
    if (tab.value === 'wrongs') {
      const res = await adminApi(`/api/admin/wrongs?status=${encodeURIComponent(wrongStatus.value)}`)
      wrongs.value = res.items || []
    }
    if (tab.value === 'assets') {
      const res = await adminApi(`/api/admin/assets?kind=${encodeURIComponent(assetKind.value)}`)
      assets.value = res.items || []
    }
    if (tab.value === 'wall') {
      const res = await adminApi(`/api/admin/wall?status=${encodeURIComponent(wallStatus.value)}&limit=100`)
      wallItems.value = res.items || res || []
    }
  } catch (e: any) {
    error.value = e?.message || '加载失败'
    if (String(e?.message || '').includes('令牌') || String(e?.message || '').includes('权限')) {
      logout()
    }
  }
}

function switchTab(name: string) {
  tab.value = name
  router.replace({ path: `/admin/${name}` })
  loadTab()
}

async function searchUsers() {
  if (tab.value !== 'users') return
  await loadTab()
}

async function setMute(u: any, muted: boolean) {
  if (!u?.username || muting.value) return
  muting.value = u.username
  try {
    const res = await adminApi(`/api/admin/users/${encodeURIComponent(u.username)}/mute`, {
      method: 'PUT',
      body: JSON.stringify({ muted }),
    })
    u.isMuted = res.isMuted ?? res.is_muted ?? muted
    u.is_muted = u.isMuted
  } catch (e: any) {
    error.value = e?.message || '操作失败'
  } finally {
    muting.value = ''
  }
}

async function unpublishPractice(id: number) {
  try {
    await adminApi(`/api/admin/practices/${id}/unpublish`, { method: 'PUT', body: '{}' })
    await loadTab()
  } catch (e: any) {
    error.value = e?.message || '操作失败'
  }
}

async function reviewWall(id: number, approved: boolean) {
  try {
    await adminApi(`/api/admin/wall/${id}/${approved ? 'approve' : 'reject'}`, { method: 'PUT', body: '{}' })
    await loadTab()
  } catch (e: any) {
    error.value = e?.message || '操作失败'
  }
}

async function publishPractice(id: number) {
  try {
    await adminApi(`/api/admin/practices/${id}/publish`, { method: 'PUT', body: '{}' })
    await loadTab()
  } catch (e: any) {
    error.value = e?.message || '操作失败'
  }
}

watch(
  () => route.params.tab,
  (v) => {
    tab.value = (v as string) || 'overview'
  },
)

onMounted(loadTab)
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-4 px-4 py-6">
    <header class="text-center">
      <h1 class="text-2xl font-extrabold text-brand-700">管理后台</h1>
      <p class="mt-1 text-sm font-bold text-brand-600/60">默认账号 admin / 密码 coding61</p>
    </header>

    <div v-if="!loggedIn" class="card mx-auto max-w-md space-y-3">
      <input
        v-model="username"
        placeholder="管理员用户名"
        class="w-full rounded-2xl border-2 border-brand-200 px-4 py-3 text-sm font-bold outline-none focus:border-brand-400"
        @keyup.enter="login"
      />
      <input
        v-model="password"
        type="password"
        placeholder="管理员密码"
        class="w-full rounded-2xl border-2 border-brand-200 px-4 py-3 text-sm font-bold outline-none focus:border-brand-400"
        @keyup.enter="login"
      />
      <button type="button" class="btn-primary w-full" :disabled="loggingIn" @click="login">
        {{ loggingIn ? '登录中…' : '登录' }}
      </button>
      <p v-if="error" class="text-center text-sm font-bold text-candy">{{ error }}</p>
    </div>

    <template v-else>
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="t in TABS"
          :key="t.key"
          type="button"
          class="px-4 py-2 text-sm"
          :class="tab === t.key ? 'btn-primary' : 'btn-ghost'"
          @click="switchTab(t.key)"
        >
          {{ t.label }}
        </button>
        <button type="button" class="btn-ghost ml-auto px-3 py-2 text-sm" @click="logout">退出</button>
      </div>

      <p v-if="error" class="text-sm font-bold text-candy">{{ error }}</p>

      <div v-if="tab === 'overview' && stats" class="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div class="card">
          <div class="text-xs font-bold text-brand-600/50">用户</div>
          <div class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.user_count ?? 0 }}</div>
        </div>
        <div class="card">
          <div class="text-xs font-bold text-brand-600/50">朗读</div>
          <div class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.practice_count ?? 0 }}</div>
        </div>
        <div class="card">
          <div class="text-xs font-bold text-brand-600/50">已完成</div>
          <div class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.completed_count ?? 0 }}</div>
        </div>
        <div class="card">
          <div class="text-xs font-bold text-brand-600/50">今日朗读</div>
          <div class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.today_practices ?? 0 }}</div>
        </div>
        <div class="card">
          <div class="text-xs font-bold text-brand-600/50">未消错题</div>
          <div class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.wrong_open ?? 0 }}</div>
        </div>
        <div class="card">
          <div class="text-xs font-bold text-brand-600/50">TTS 资源</div>
          <div class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.tts_count ?? 0 }}</div>
        </div>
        <div class="card">
          <div class="text-xs font-bold text-brand-600/50">词框资源</div>
          <div class="mt-1 text-2xl font-extrabold text-brand-700">{{ stats.ocr_count ?? 0 }}</div>
        </div>
      </div>

      <div v-if="tab === 'users'" class="space-y-3">
        <div class="flex gap-2">
          <input
            v-model="userQuery"
            class="min-w-0 flex-1 rounded-2xl border-2 border-brand-200 px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="搜索用户名 / 昵称"
            @keyup.enter="searchUsers"
          />
          <button type="button" class="btn-ghost px-4 py-2 text-sm" @click="searchUsers">搜索</button>
        </div>
        <div class="card overflow-x-auto !p-0">
          <table class="w-full min-w-[640px] text-sm">
            <thead class="bg-brand-50 text-left text-brand-600/70">
              <tr>
                <th class="px-4 py-3">用户</th>
                <th class="px-4 py-3">朗读数</th>
                <th class="px-4 py-3">状态</th>
                <th class="px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.username" class="border-t border-brand-100">
                <td class="px-4 py-3">
                  <div class="font-bold text-brand-700">{{ u.nickname || u.username }}</div>
                  <div class="text-xs text-brand-600/50">{{ u.username }}</div>
                </td>
                <td class="px-4 py-3">{{ u.practice_count ?? 0 }}</td>
                <td class="px-4 py-3">
                  <span
                    class="rounded-full px-2 py-0.5 text-xs font-semibold"
                    :class="(u.isMuted ?? u.is_muted) ? 'bg-red-100 text-red-500' : 'bg-emerald-100 text-emerald-600'"
                  >
                    {{ (u.isMuted ?? u.is_muted) ? '已禁言' : '正常' }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <button
                    type="button"
                    class="rounded-full px-3 py-1 text-xs font-bold"
                    :class="(u.isMuted ?? u.is_muted) ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'"
                    :disabled="muting === u.username"
                    @click="setMute(u, !(u.isMuted ?? u.is_muted))"
                  >
                    {{ muting === u.username ? '处理中…' : (u.isMuted ?? u.is_muted) ? '解除禁言' : '禁言' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!users.length" class="p-6 text-center text-sm text-brand-600/50">没有匹配的用户</div>
        </div>
      </div>

      <div v-if="tab === 'practices'" class="card overflow-x-auto !p-0">
        <table class="w-full min-w-[720px] text-sm">
          <thead class="bg-brand-50 text-left text-brand-600/70">
            <tr>
              <th class="px-4 py-3">用户</th>
              <th class="px-4 py-3">书 / 页</th>
              <th class="px-4 py-3">日期</th>
              <th class="px-4 py-3">分数</th>
              <th class="px-4 py-3">公开</th>
              <th class="px-4 py-3">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in practices" :key="p.id" class="border-t border-brand-100">
              <td class="px-4 py-3">{{ p.username || '-' }}</td>
              <td class="px-4 py-3">{{ p.bookTitle || p.book_title || '-' }} · 第 {{ p.page }} 页</td>
              <td class="px-4 py-3">{{ p.lessonDate || p.lesson_date || '-' }}</td>
              <td class="px-4 py-3">{{ p.overallScore ?? p.overall_score ?? '-' }}</td>
              <td class="px-4 py-3">{{ (p.isPublic ?? p.is_public) ? '是' : '否' }}</td>
              <td class="px-4 py-3">
                <a
                  v-if="p.videoUrl || p.video_url"
                  :href="p.videoUrl || p.video_url"
                  target="_blank"
                  rel="noopener"
                  class="mr-2 text-xs font-bold text-brand-500"
                >
                  观看
                </a>
                <button
                  v-if="p.isPublic ?? p.is_public"
                  type="button"
                  class="text-xs font-bold text-candy"
                  @click="unpublishPractice(p.id)"
                >
                  下架
                </button>
                <button
                  v-else
                  type="button"
                  class="text-xs font-bold text-brand-500"
                  @click="publishPractice(p.id)"
                >
                  上架
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!practices.length" class="p-6 text-center text-sm text-brand-600/50">暂无朗读</div>
      </div>

      <div v-if="tab === 'wall'" class="space-y-3">
        <div class="flex gap-2">
          <button
            v-for="s in ['pending', 'approved', 'rejected', 'all']"
            :key="s"
            type="button"
            class="px-4 py-2 text-sm"
            :class="wallStatus === s ? 'btn-primary' : 'btn-ghost'"
            @click="wallStatus = s; loadTab()"
          >
            {{ s === 'pending' ? '待审' : s === 'approved' ? '已通过' : s === 'rejected' ? '已拒绝' : '全部' }}
          </button>
        </div>
        <div v-if="!wallItems.length" class="card py-8 text-center text-sm font-bold text-brand-600/50">
          没有留言
        </div>
        <div v-for="msg in wallItems" :key="msg.id" class="card space-y-2">
          <p class="text-sm font-bold text-brand-700">
            {{ msg.authorName || msg.authorUsername }} → {{ msg.wallName || msg.wallUsername }}
          </p>
          <p class="text-sm text-brand-600">{{ msg.content }}</p>
          <p class="text-xs font-bold text-brand-600/50">{{ msg.status }} · {{ msg.createdAt || '' }}</p>
          <div v-if="msg.status === 'pending'" class="flex gap-2">
            <button type="button" class="btn-primary px-3 py-1 text-xs" @click="reviewWall(msg.id, true)">通过</button>
            <button type="button" class="btn-ghost px-3 py-1 text-xs" @click="reviewWall(msg.id, false)">拒绝</button>
          </div>
        </div>
      </div>

      <div v-if="tab === 'wrongs'" class="space-y-3">
        <div class="flex gap-2">
          <button
            type="button"
            class="px-4 py-2 text-sm"
            :class="wrongStatus === 'open' ? 'btn-primary' : 'btn-ghost'"
            @click="wrongStatus = 'open'; loadTab()"
          >
            当前错题
          </button>
          <button
            type="button"
            class="px-4 py-2 text-sm"
            :class="wrongStatus === 'resolved' ? 'btn-primary' : 'btn-ghost'"
            @click="wrongStatus = 'resolved'; loadTab()"
          >
            已消除
          </button>
        </div>
        <div class="card overflow-x-auto !p-0">
          <table class="w-full min-w-[720px] text-sm">
            <thead class="bg-brand-50 text-left text-brand-600/70">
              <tr>
                <th class="px-4 py-3">用户</th>
                <th class="px-4 py-3">类型</th>
                <th class="px-4 py-3">内容</th>
                <th class="px-4 py-3">书 / 页</th>
                <th class="px-4 py-3">次数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in wrongs" :key="w.id" class="border-t border-brand-100">
                <td class="px-4 py-3">{{ w.username }}</td>
                <td class="px-4 py-3">{{ w.kind === 'phrase' ? '短语' : '词汇' }}</td>
                <td class="px-4 py-3">
                  <div class="font-bold text-brand-700">{{ w.en }}</div>
                  <div class="text-xs text-brand-600/50">{{ w.zh }}</div>
                </td>
                <td class="px-4 py-3">{{ w.bookTitle || '-' }} · 第 {{ w.page }} 页</td>
                <td class="px-4 py-3">{{ w.wrongCount }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="!wrongs.length" class="p-6 text-center text-sm text-brand-600/50">暂无错题</div>
        </div>
      </div>

      <div v-if="tab === 'assets'" class="space-y-3">
        <div class="flex gap-2">
          <button
            v-for="k in ['all', 'tts', 'ocr']"
            :key="k"
            type="button"
            class="px-4 py-2 text-sm"
            :class="assetKind === k ? 'btn-primary' : 'btn-ghost'"
            @click="assetKind = k; loadTab()"
          >
            {{ k === 'all' ? '全部' : k === 'tts' ? 'TTS' : '词框' }}
          </button>
        </div>
        <div class="card overflow-x-auto !p-0">
          <table class="w-full min-w-[720px] text-sm">
            <thead class="bg-brand-50 text-left text-brand-600/70">
              <tr>
                <th class="px-4 py-3">类型</th>
                <th class="px-4 py-3">用途</th>
                <th class="px-4 py-3">内容</th>
                <th class="px-4 py-3">来源</th>
                <th class="px-4 py-3">时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in assets" :key="a.id" class="border-t border-brand-100">
                <td class="px-4 py-3">{{ a.kind === 'ocr' ? '词框' : 'TTS' }}</td>
                <td class="px-4 py-3">{{ a.label || '-' }}</td>
                <td class="max-w-xs truncate px-4 py-3" :title="a.preview">{{ a.preview || a.assetKey }}</td>
                <td class="px-4 py-3">{{ a.source }}</td>
                <td class="px-4 py-3">{{ a.createdAt || '-' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="!assets.length" class="p-6 text-center text-sm text-brand-600/50">还没有按需生成的资源</div>
        </div>
      </div>
    </template>
  </div>
</template>
