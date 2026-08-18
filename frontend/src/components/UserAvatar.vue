<script setup lang="ts">
import { computed } from 'vue'

import { isAvatarUrl } from '../utils/avatar'

const props = withDefaults(
  defineProps<{
    avatar?: string | null
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
    rounded?: 'md' | 'lg' | 'xl' | '2xl' | 'full'
  }>(),
  {
    avatar: '📖',
    size: 'md',
    rounded: 'full',
  },
)

const sizeClass: Record<string, string> = {
  xs: 'h-6 w-6 text-sm',
  sm: 'h-8 w-8 text-base',
  md: 'h-10 w-10 text-xl',
  lg: 'h-12 w-12 text-2xl',
  xl: 'h-14 w-14 text-3xl',
}

const roundedClass: Record<string, string> = {
  md: 'rounded-md',
  lg: 'rounded-lg',
  xl: 'rounded-xl',
  '2xl': 'rounded-2xl',
  full: 'rounded-full',
}

const display = computed(() => props.avatar || '📖')
const image = computed(() => isAvatarUrl(display.value))
const boxClass = computed(() => [sizeClass[props.size], roundedClass[props.rounded], 'shrink-0 overflow-hidden'])
</script>

<template>
  <img
    v-if="image"
    :src="display"
    alt="头像"
    class="bg-brand-100 object-cover"
    :class="boxClass"
  />
  <span
    v-else
    class="inline-flex items-center justify-center bg-brand-100 leading-none"
    :class="boxClass"
  >
    {{ display }}
  </span>
</template>
