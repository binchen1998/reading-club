import { createRouter, createWebHistory } from 'vue-router'

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
    { path: '/square/:id', component: SquareDetailView, meta: { auth: true } },
    { path: '/me', component: ProfileView, meta: { auth: true } },
    { path: '/user/:userKey', component: ProfileView, meta: { auth: true } },
    { path: '/messages', component: MessagesView, meta: { auth: true } },
    { path: '/day', component: DayView, meta: { auth: true } },
    { path: '/series/:seriesId', component: SeriesView, meta: { auth: true } },
    { path: '/series/:seriesId/:bookSlug', component: BookView, meta: { auth: true } },
    { path: '/read/:seriesId/:bookSlug/:chapterId', component: LessonView, meta: { auth: true } },
    { path: '/admin/:tab?', component: AdminView },
  ],
})

router.beforeEach((to) => {
  if (to.path.startsWith('/admin')) return true
  const fromUrl = syncUsernameFromUrl(to.fullPath.includes('?') ? to.fullPath.slice(to.fullPath.indexOf('?')) : window.location.search)
  const qUser = typeof to.query.username === 'string' ? to.query.username : ''
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
