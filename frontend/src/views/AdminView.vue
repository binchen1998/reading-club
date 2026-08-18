<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ADMIN_TOKEN_KEY, adminApi } from '../api'
import {
  streamAdminWorkerLogs,
  type WorkerLogLine,
  type WorkerStatus,
} from '../utils/adminWorkerSse'

const route = useRoute()
const router = useRouter()

const TABS = [
  { key: 'overview', label: '概览' },
  { key: 'users', label: '用户' },
  { key: 'practices', label: '朗读' },
  { key: 'wall', label: '留言' },
  { key: 'wrongs', label: '错题' },
  { key: 'assets', label: '资源' },
  { key: 'lessons', label: '课稿' },
  { key: 'worker', label: 'Worker' },
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
const contentTree = ref<any[]>([])
const openSeries = ref<Record<string, boolean>>({})
const openBooks = ref<Record<string, boolean>>({})
const clearing = ref('')
const clearHint = ref('')
const workerStatus = ref<WorkerStatus>({})
const workerLogs = ref<WorkerLogLine[]>([])
const workerFollow = ref(true)
const workerLive = ref(false)
const logBox = ref<HTMLElement | null>(null)
let workerAbort: AbortController | null = null

function kindLabel(kind?: string) {
  if (kind === 'lesson') return '课稿'
  if (kind === 'tts') return 'TTS'
  if (kind === 'ocr') return '词框'
  if (kind === 'chat') return '助教'
  return kind || '任务'
}

function logTone(level?: string) {
  const value = (level || '').toUpperCase()
  if (value === 'ERROR' || value === 'CRITICAL') return 'text-red-300'
  if (value === 'WARNING') return 'text-amber-300'
  return 'text-emerald-200'
}

function logTime(iso?: string) {
  if (!iso) return ''
  return iso.includes('T') ? iso.slice(11, 19) : iso
}

function scrollLogs() {
  const el = logBox.value
  if (el) el.scrollTop = el.scrollHeight
}

function applyWorkerEvent(event: { status?: WorkerStatus; logs?: WorkerLogLine[]; line?: WorkerLogLine }) {
  if (event.status) workerStatus.value = event.status
  if (event.logs) {
    workerLogs.value = event.logs
    if (workerFollow.value) nextTick(scrollLogs)
  }
  if (event.line) {
    workerLogs.value = [...workerLogs.value, event.line].slice(-400)
    if (workerFollow.value) nextTick(scrollLogs)
  }
}

function stopWorkerStream() {
  workerLive.value = false
  workerAbort?.abort()
  workerAbort = null
}

async function startWorkerStream() {
  stopWorkerStream()
  const ac = new AbortController()
  workerAbort = ac
  workerLive.value = true
  try {
    await streamAdminWorkerLogs((event) => applyWorkerEvent(event), ac.signal)
    if (!ac.signal.aborted && tab.value === 'worker' && loggedIn.value) {
      workerLive.value = false
      window.setTimeout(() => {
        if (tab.value === 'worker' && loggedIn.value) void startWorkerStream()
      }, 1200)
    }
  } catch (e: any) {
    if (ac.signal.aborted) return
    workerLive.value = false
    error.value = e?.message || 'worker 日志断开'
  }
}

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
  stopWorkerStream()
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
    if (tab.value === 'lessons') {
      const res = await adminApi('/api/admin/content')
      contentTree.value = res.series || []
    }
    if (tab.value === 'worker') {
      void startWorkerStream()
    } else {
      stopWorkerStream()
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

function bookKey(seriesId: string, slug: string) {
  return `${seriesId}/${slug}`
}

function confirmClear(label: string) {
  return window.confirm(`确定清除${label}的课稿和词框？清除后会在后台重新生成。`)
}

async function clearContent(seriesId: string, bookSlug = '', chapter?: number, label = '') {
  if (!confirmClear(label || seriesId) || clearing.value) return
  clearing.value = `${seriesId}/${bookSlug || ''}/${chapter || ''}`
  clearHint.value = ''
  try {
    const res = await adminApi('/api/admin/content/clear', {
      method: 'POST',
      body: JSON.stringify({
        series_id: seriesId,
        book_slug: bookSlug,
        chapter: chapter || null,
      }),
    })
    clearHint.value = `已清除课稿 ${res.lessons || 0}、词框 ${res.ocrFiles || 0}，正在重新生成 ${res.queued || 0} 项`
    await loadTab()
  } catch (e: any) {
    error.value = e?.message || '清除失败'
  } finally {
    clearing.value = ''
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
onUnmounted(stopWorkerStream)
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

      <div v-if="tab === 'worker'" class="space-y-3">
        <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div class="card">
            <div class="text-xs font-bold text-brand-600/50">后台进行中</div>
            <div class="mt-1 text-2xl font-extrabold text-brand-700">
              {{ workerStatus.background?.active_count ?? 0 }}
            </div>
          </div>
          <div class="card">
            <div class="text-xs font-bold text-brand-600/50">后台排队</div>
            <div class="mt-1 text-2xl font-extrabold text-brand-700">
              {{ workerStatus.background?.queued_count ?? 0 }}
            </div>
          </div>
          <div class="card">
            <div class="text-xs font-bold text-brand-600/50">即时任务</div>
            <div class="mt-1 text-2xl font-extrabold text-brand-700">
              {{ workerStatus.interactive?.length ?? 0 }}
            </div>
          </div>
          <div class="card">
            <div class="text-xs font-bold text-brand-600/50">日志流</div>
            <div class="mt-1 text-lg font-extrabold" :class="workerLive ? 'text-mint' : 'text-candy'">
              {{ workerLive ? '已连接' : '未连接' }}
            </div>
          </div>
        </div>
        <div
          v-if="(workerStatus.background?.active || []).length || (workerStatus.interactive || []).length"
          class="card space-y-2"
        >
          <p class="text-sm font-extrabold text-brand-700">正在生成</p>
          <p
            v-for="item in workerStatus.background?.active || []"
            :key="`bg-${item}`"
            class="rounded-2xl bg-brand-50 px-3 py-2 text-sm font-bold text-brand-700"
          >
            后台章节 · {{ item }}
          </p>
          <p
            v-for="job in workerStatus.interactive || []"
            :key="job.job_id || job.key"
            class="rounded-2xl bg-brand-50 px-3 py-2 text-sm font-bold text-brand-700"
          >
            {{ kindLabel(job.kind) }} · {{ job.status === 'running' ? '进行中' : '排队' }}
            <span class="ml-2 font-medium text-brand-600/70">{{ job.preview || job.key }}</span>
          </p>
        </div>
        <div
          v-if="(workerStatus.background?.queued || []).length"
          class="card space-y-2"
        >
          <p class="text-sm font-extrabold text-brand-700">排队中</p>
          <p
            v-for="item in workerStatus.background?.queued || []"
            :key="`q-${item}`"
            class="text-sm font-bold text-brand-600/70"
          >
            {{ item }}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <label class="flex items-center gap-2 text-sm font-bold text-brand-700">
            <input v-model="workerFollow" type="checkbox" />
            跟随滚动
          </label>
          <button type="button" class="btn-ghost px-3 py-1 text-xs" @click="workerLogs = []">清空显示</button>
        </div>
        <div
          ref="logBox"
          class="h-[28rem] overflow-auto rounded-3xl bg-slate-950 px-4 py-3 font-mono text-xs leading-6 shadow-pop"
        >
          <p v-if="!workerLogs.length" class="text-slate-500">还没有 worker 日志。打开阅读页生成后会实时出现在这里。</p>
          <p v-for="(line, index) in workerLogs" :key="line.id || index" :class="logTone(line.level)">
            <span class="text-slate-500">{{ logTime(line.iso) }}</span>
            <span class="ml-2 text-slate-400">{{ line.level }}</span>
            <span class="ml-2">{{ line.message }}</span>
          </p>
        </div>
      </div>

      <div v-if="tab === 'lessons'" class="space-y-3">
        <p class="text-sm font-bold text-brand-600/70">
          可按套书、单本或单章清除课稿和词框。生成有问题时用这个重来，不会删用户朗读或进度。
        </p>
        <p v-if="clearHint" class="text-sm font-bold text-mint">{{ clearHint }}</p>
        <div v-if="!contentTree.length" class="card py-8 text-center text-sm font-bold text-brand-600/50">
          还没有系列
        </div>
        <div v-for="series in contentTree" :key="series.id" class="card space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <button
              type="button"
              class="min-w-0 flex-1 text-left text-lg font-extrabold text-brand-700"
              @click="openSeries[series.id] = !openSeries[series.id]"
            >
              {{ openSeries[series.id] ? '▼' : '▶' }} {{ series.title }}
            </button>
            <button
              type="button"
              class="btn-ghost px-3 py-1 text-xs"
              :disabled="!!clearing"
              @click="clearContent(series.id, '', undefined, series.title)"
            >
              {{ clearing.startsWith(`${series.id}//`) ? '清除中…' : '清除本套' }}
            </button>
          </div>
          <div v-if="openSeries[series.id]" class="space-y-2">
            <div v-for="book in series.books" :key="book.slug" class="rounded-2xl bg-brand-50 p-3">
              <div class="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  class="min-w-0 flex-1 text-left font-extrabold text-brand-700"
                  :disabled="!book.ready"
                  @click="openBooks[bookKey(series.id, book.slug)] = !openBooks[bookKey(series.id, book.slug)]"
                >
                  {{ book.ready ? (openBooks[bookKey(series.id, book.slug)] ? '▼' : '▶') : '·' }}
                  {{ book.title }}
                  <span class="ml-2 text-xs font-bold text-brand-600/50">
                    {{ book.ready ? `课稿 ${book.generated}/${book.chapterCount}` : '仅书目' }}
                  </span>
                </button>
                <button
                  v-if="book.ready"
                  type="button"
                  class="btn-ghost px-3 py-1 text-xs"
                  :disabled="!!clearing"
                  @click="clearContent(series.id, book.slug, undefined, book.title)"
                >
                  {{ clearing === `${series.id}/${book.slug}/` ? '清除中…' : '清除本书' }}
                </button>
              </div>
              <div v-if="openBooks[bookKey(series.id, book.slug)]" class="mt-2 space-y-1">
                <div
                  v-for="ch in book.chapters"
                  :key="ch.id"
                  class="flex items-center gap-2 rounded-xl bg-white px-3 py-2"
                >
                  <p class="min-w-0 flex-1 text-sm font-bold text-brand-700">
                    {{ ch.title }}
                    <span class="ml-2 text-xs text-brand-600/50">
                      {{ ch.generating ? '生成中' : ch.generated ? '已生成' : '未生成' }}
                    </span>
                  </p>
                  <button
                    type="button"
                    class="text-xs font-bold text-candy"
                    :disabled="!!clearing"
                    @click="clearContent(series.id, book.slug, ch.chapter, ch.title)"
                  >
                    {{ clearing === `${series.id}/${book.slug}/${ch.chapter}` ? '清除中…' : '清除这章' }}
                  </button>
                </div>
                <p v-if="!book.chapters.length" class="px-3 py-2 text-xs font-bold text-brand-600/40">
                  还没有切出章节
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
