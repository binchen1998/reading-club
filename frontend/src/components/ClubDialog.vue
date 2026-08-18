<script setup lang="ts">
withDefaults(
  defineProps<{
    open: boolean
    title: string
    emoji?: string
    wide?: boolean
    dock?: 'center' | 'bottom' | 'side'
    fixed?: boolean
  }>(),
  { emoji: '', wide: false, dock: 'center', fixed: false },
)

const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div
        v-if="open"
        class="fixed z-[60] p-4"
        :class="{
          'inset-x-0 bottom-0 flex justify-center pointer-events-none': dock === 'bottom',
          'inset-0 flex items-end justify-center pointer-events-none lg:items-center lg:justify-end': dock === 'side',
          'inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm': dock === 'center',
        }"
        @click.self="emit('close')"
      >
        <div
          class="card relative w-full animate-pop-in"
          :class="[
            wide ? 'max-w-2xl' : 'max-w-md',
            dock === 'bottom' || dock === 'side' ? 'pointer-events-auto shadow-pop' : '',
            fixed && dock === 'side' ? 'flex max-h-[40vh] flex-col overflow-hidden lg:h-[32rem] lg:max-h-[32rem]' : '',
            fixed && dock !== 'side' ? 'flex h-[32rem] flex-col overflow-hidden' : '',
            !fixed ? 'max-h-[88vh] overflow-y-auto' : '',
          ]"
          role="dialog"
          aria-modal="true"
        >
          <button class="game-result-close" type="button" aria-label="关闭" @click="emit('close')">×</button>
          <div class="mb-4 flex items-center gap-2 pr-8">
            <span v-if="emoji" class="text-2xl">{{ emoji }}</span>
            <h2 class="text-xl font-extrabold text-brand-700">{{ title }}</h2>
          </div>
          <div :class="fixed ? 'flex min-h-0 flex-1 flex-col' : ''">
            <slot />
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
