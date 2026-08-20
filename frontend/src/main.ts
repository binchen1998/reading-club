import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { resolveToken } from './auth/resolveToken'
import router from './router'
import { useUserStore } from './stores/user'
import { syncUsernameFromUrl } from './utils/username'
import './style.css'

document.addEventListener('dblclick', (event) => event.preventDefault())

;(async () => {
  const urlParams = new URLSearchParams(window.location.search)
  if (await resolveToken(urlParams)) return

  syncUsernameFromUrl()
  const app = createApp(App)
  const pinia = createPinia()
  app.use(pinia)
  useUserStore(pinia).hydrate()
  app.use(router)
  app.mount('#app')
})()
