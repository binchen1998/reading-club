<script setup lang="ts">
import { generateLabel } from '../stores/generate'
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div
        v-if="generateLabel"
        class="fixed inset-0 z-[120] flex items-center justify-center bg-slate-900/55 p-4"
      >
        <div class="card w-full max-w-md animate-pop-in px-6 py-8 text-center">
          <p class="text-4xl">⏳</p>
          <p class="mt-4 text-lg font-extrabold leading-8 text-brand-700">
            你是第一个读这页的人，正在生成{{ generateLabel }}，请稍等。
          </p>
          <p class="mt-3 text-sm font-bold text-brand-600/70">生成后会保存，后面的人不用再等。</p>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
