import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '../api'
import { isGuestUsername } from '../utils/guestUser'
import { hasCustomNickname } from '../utils/nickname'
import { safeDisplayName } from '../utils/safeDisplayName'
import { readUsername, writeUsername } from '../utils/username'

export const useUserStore = defineStore('user', () => {
  const username = ref('')
  const profile = ref<any>(null)
  const moderating = ref(false)

  const isGuest = computed(() => isGuestUsername(username.value))
  const nickname = computed(() => safeDisplayName(profile.value?.nickname, username.value))
  const avatar = computed(() => profile.value?.avatarUrl || profile.value?.avatar || '📖')
  const customNickname = computed(
    () => profile.value?.hasCustomNickname ?? hasCustomNickname(username.value, profile.value?.nickname),
  )

  function applyMe(me: any) {
    profile.value = me
    if (me?.username) username.value = writeUsername(me.username)
  }

  function hydrate() {
    username.value = readUsername()
  }

  function login(name: string) {
    username.value = writeUsername(name)
  }

  async function loadMe() {
    if (!username.value) return
    applyMe(await api('/api/users/me'))
  }

  async function setNickname(value: string) {
    moderating.value = true
    try {
      applyMe(await api('/api/users/nickname', { method: 'PUT', body: JSON.stringify({ nickname: value }) }))
    } finally {
      moderating.value = false
    }
  }

  async function setBio(value: string) {
    moderating.value = true
    try {
      applyMe(await api('/api/users/bio', { method: 'PUT', body: JSON.stringify({ bio: value }) }))
    } finally {
      moderating.value = false
    }
  }

  return {
    username,
    profile,
    moderating,
    isGuest,
    nickname,
    avatar,
    customNickname,
    hydrate,
    login,
    loadMe,
    setNickname,
    setBio,
  }
})
