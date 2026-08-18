import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import { useUserStore } from './stores/user'
import { syncUsernameFromUrl } from './utils/username'
import './style.css'

syncUsernameFromUrl()
const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
useUserStore(pinia).hydrate()
app.use(router)
app.mount('#app')
