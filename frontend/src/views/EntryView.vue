<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useUserStore } from '../stores/user'
import { readUsername, withUsernameQuery } from '../utils/username'

const router = useRouter()
const route = useRoute()
const user = useUserStore()
const name = ref(readUsername())

function enter() {
  const value = name.value.trim()
  if (!value) return
  user.login(value)
  const next = typeof route.query.return_url === 'string' ? route.query.return_url : '/home'
  router.push(withUsernameQuery(next, value))
}

if (readUsername()) {
  router.replace(withUsernameQuery('/home'))
}
</script>

<template>
  <div class="flex min-h-[70vh] flex-col items-center justify-center">
    <div class="mb-6 text-center">
      <div class="animate-float text-7xl">📖</div>
      <h1 class="mt-2 text-3xl font-extrabold text-brand-700">英语阅读俱乐部</h1>
      <p class="mt-1 font-bold text-brand-600/80">通过 ?username= 进入，不用注册</p>
    </div>
    <section class="card w-full max-w-md animate-pop-in space-y-4">
      <h2 class="text-xl font-extrabold text-brand-700">你是谁？</h2>
      <input
        v-model="name"
        class="w-full rounded-2xl border border-brand-200 bg-white/80 px-4 py-3 font-bold text-brand-700 outline-none ring-brand-400 focus:ring-2"
        placeholder="用户名"
        @keyup.enter="enter"
      />
      <button class="btn-candy w-full" type="button" @click="enter">进入俱乐部</button>
    </section>
  </div>
</template>
