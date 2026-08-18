import { createRouter, createWebHistory, type LocationQuery } from 'vue-router'

import AdminView from './views/AdminView.vue'
import BookView from './views/BookView.vue'
import BooksView from './views/BooksView.vue'
import DayView from './views/DayView.vue'
import EntryView from './views/EntryView.vue'
import HomeView from './views/HomeView.vue'
import LessonView from './views/LessonView.vue'
import MessagesView from './views/MessagesView.vue'
import ProfileView from './views/ProfileView.vue'
import SeriesView from './views/SeriesView.vue'
import SquareDetailView from './views/SquareDetailView.vue'
import SquareView from './views/SquareView.vue'
import WrongBookView from './views/WrongBookView.vue'
import { readUsername, syncUsernameFromUrl, writeUsername } from './utils/username'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: EntryView },
    { path: '/home', component: HomeView, meta: { auth: true } },
    { path: '/books', component: BooksView, meta: { auth: true } },
    { path: '/wrong-book', component: WrongBookView, meta: { auth: true } },
    { path: '/square', component: SquareView, meta: { auth: true } },
    { path: '/square/:id', component: SquareDetailView, meta: { auth: true, secondary: true } },
    { path: '/me', component: ProfileView, meta: { auth: true } },
    { path: '/user/:userKey', component: ProfileView, meta: { auth: true, secondary: true } },
    { path: '/messages', component: MessagesView, meta: { auth: true } },
    { path: '/day', component: DayView, meta: { auth: true, secondary: true } },
    { path: '/series/:seriesId', component: SeriesView, meta: { auth: true, secondary: true } },
    { path: '/series/:seriesId/:bookSlug', component: BookView, meta: { auth: true, secondary: true } },
    { path: '/read/:seriesId/:bookSlug/:chapterId', component: LessonView, meta: { auth: true, secondary: true } },
    { path: '/admin/:tab?', component: AdminView },
  ],
})

function queryString(query: LocationQuery, key: string): string {
  const raw = query[key]
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value.trim() : ''
}

function queryUsername(query: LocationQuery): string {
  return queryString(query, 'username')
}

router.beforeEach((to) => {
  if (to.path.startsWith('/admin')) return true
  if (to.path === '/home' && !queryUsername(to.query) && !queryString(to.query, 'token')) {
    window.alert('链接里必须带 username，无法打开首页')
    return false
  }
  const fromUrl = syncUsernameFromUrl(to.fullPath.includes('?') ? to.fullPath.slice(to.fullPath.indexOf('?')) : window.location.search)
  const qUser = queryUsername(to.query)
  if (qUser) writeUsername(qUser)
  const user = qUser || fromUrl || readUsername()
  if (to.meta.auth && !user) {
    return { path: '/', query: { return_url: to.fullPath } }
  }
  if (user && to.query.username !== user) {
    return { path: to.path, query: { ...to.query, username: user }, hash: to.hash, replace: true }
  }
  return true
})

export default router
