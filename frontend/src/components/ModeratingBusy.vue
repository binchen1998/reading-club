<script setup lang="ts">
defineProps<{ open: boolean; text?: string }>()
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[130] flex items-center justify-center bg-slate-900/55 p-4"
      >
        <div class="card w-full max-w-sm px-6 py-8 text-center">
          <p class="text-4xl">🔎</p>
          <p class="mt-4 text-lg font-extrabold text-brand-700">
            {{ text || '正在用 AI 审核昵称，请稍等。' }}
          </p>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
