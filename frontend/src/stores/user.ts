import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api } from '../api'
import { readUsername, writeUsername } from '../utils/username'

export const useUserStore = defineStore('user', () => {
  const username = ref('')
  const nickname = ref('')
  const avatar = ref('')

  function hydrate() {
    username.value = readUsername()
  }

  function login(name: string) {
    username.value = writeUsername(name)
  }

  async function loadMe() {
    if (!username.value) return
    const me = await api('/api/users/me')
    nickname.value = me.nickname || me.username
    avatar.value = me.avatar || ''
  }

  return { username, nickname, avatar, hydrate, login, loadMe }
})
