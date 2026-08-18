<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { api } from './api'
import GenerateBusy from './components/GenerateBusy.vue'
import { clubLink } from './utils/username'
import { useUserStore } from './stores/user'

const route = useRoute()
const user = useUserStore()
const unreadCount = ref(0)
let unreadTimer: number | undefined
const reading = computed(() => route.path.startsWith('/read/'))
const adminPage = computed(() => route.path.startsWith('/admin'))
const onMessages = computed(() => route.path === '/messages')
const navItems = [
  { path: '/home', label: '首页', match: ['/home', '/day'] },
  { path: '/books', label: '书架', match: ['/books', '/series'] },
  { path: '/wrong-book', label: '错题本', match: ['/wrong-book'] },
  { path: '/square', label: '广场', match: ['/square'] },
  { path: '/messages', label: '消息', match: ['/messages'] },
  { path: '/me', label: '我的', match: ['/me', '/user'] },
] as const

function navActive(match: readonly string[]) {
  return match.some((prefix) => route.path === prefix || route.path.startsWith(`${prefix}/`))
}

function navClass(active: boolean) {
  return active
    ? 'relative rounded-full bg-sunny/80 px-3 py-1 text-brand-700'
    : 'relative rounded-full px-3 py-1 text-brand-700 hover:bg-white'
}

const backNav = computed(() => {
  const seriesId = String(route.params.seriesId || '')
  const bookSlug = String(route.params.bookSlug || '')
  if (route.path.startsWith('/series/') && bookSlug) return { label: '← 书架', to: clubLink(`/series/${seriesId}`) }
  if (route.path.startsWith('/series/')) return { label: '← 全部系列', to: clubLink('/books') }
  return null
})

async function loadUnread() {
  if (!user.username || user.isGuest) {
    unreadCount.value = 0
    return
  }
  try {
    const res = await api('/api/users/notifications/unread-count')
    unreadCount.value = Number(res.count ?? res.unreadCount ?? 0)
  } catch {
    /* ignore */
  }
}

function onReadAll(event: Event) {
  const detail = (event as CustomEvent).detail
  unreadCount.value = Number(detail?.unread_count ?? 0)
}

onMounted(() => {
  user.hydrate()
  if (user.username) user.loadMe()
  loadUnread()
  window.addEventListener('notifications-read-all', onReadAll)
  unreadTimer = window.setInterval(loadUnread, 60_000)
})

onUnmounted(() => {
  window.removeEventListener('notifications-read-all', onReadAll)
  if (unreadTimer) window.clearInterval(unreadTimer)
})
</script>

<template>
  <div class="app-shell" :class="reading ? 'h-[100dvh] overflow-hidden' : ''">
    <div class="app-shell-inner" :class="reading ? 'h-full overflow-hidden' : ''">
      <header
        v-if="!reading && !adminPage"
        class="sticky top-0 z-30 border-b border-brand-200/50 bg-white/55 backdrop-blur"
      >
        <div class="relative mx-auto flex min-h-[3.5rem] max-w-[1400px] items-center justify-between gap-3 px-4 py-3 lg:px-6">
          <RouterLink :to="clubLink('/home')" class="flex items-center gap-2 text-lg font-extrabold text-brand-700">
            <span class="animate-float">📖</span>
            <span class="max-md:hidden">英语阅读俱乐部</span>
          </RouterLink>
          <RouterLink
            v-if="backNav"
            class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded-full bg-white/90 px-5 py-2 text-sm font-extrabold text-brand-700 shadow-pop"
            :to="backNav.to"
          >
            {{ backNav.label }}
          </RouterLink>
          <nav class="flex flex-wrap items-center justify-end gap-2 text-sm font-extrabold">
            <RouterLink
              v-for="item in navItems"
              :key="item.path"
              :class="navClass(navActive(item.match))"
              :to="clubLink(item.path)"
            >
              {{ item.label }}
              <span
                v-if="item.path === '/messages' && unreadCount && !onMessages"
                class="absolute -right-1 -top-1 grid min-w-4 place-items-center rounded-full bg-candy px-1 text-[10px] font-black text-white"
              >
                {{ unreadCount > 99 ? '99+' : unreadCount }}
              </span>
            </RouterLink>
          </nav>
        </div>
      </header>
      <main
        class="mx-auto"
        :class="reading ? 'h-[100dvh] overflow-hidden px-2 pb-2 pt-14' : 'max-w-[1400px] px-4 pb-16 pt-4 lg:px-6'"
      >
        <RouterView v-slot="{ Component, route: r }">
          <transition name="fade">
            <component :is="Component" v-if="Component" :key="r.fullPath" />
          </transition>
        </RouterView>
      </main>
      <GenerateBusy />
    </div>
  </div>
</template>
