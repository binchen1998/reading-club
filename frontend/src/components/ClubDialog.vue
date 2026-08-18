<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    emoji?: string
    wide?: boolean
    dock?: 'center' | 'bottom' | 'side'
    fixed?: boolean
    draggable?: boolean
  }>(),
  { emoji: '', wide: false, dock: 'center', fixed: false, draggable: false },
)

const emit = defineEmits<{ close: [] }>()

const cardEl = ref<HTMLDivElement | null>(null)
const pos = ref<{ left: number; top: number } | null>(null)
const dragging = ref(false)
let dragOffsetX = 0
let dragOffsetY = 0

watch(
  () => props.open,
  (open) => {
    if (open) {
      pos.value = null
      dragging.value = false
    }
  },
)

function onDragStart(e: PointerEvent) {
  if (!props.draggable) return
  if ((e.target as HTMLElement).closest('button')) return
  const el = cardEl.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  dragOffsetX = e.clientX - rect.left
  dragOffsetY = e.clientY - rect.top
  pos.value = { left: rect.left, top: rect.top }
  dragging.value = true
  el.setPointerCapture(e.pointerId)
}

function onDragMove(e: PointerEvent) {
  if (!dragging.value) return
  const left = Math.min(Math.max(8, e.clientX - dragOffsetX), window.innerWidth - 80)
  const top = Math.min(Math.max(8, e.clientY - dragOffsetY), window.innerHeight - 48)
  pos.value = { left, top }
}

function onDragEnd(e: PointerEvent) {
  if (!dragging.value) return
  dragging.value = false
  try {
    cardEl.value?.releasePointerCapture(e.pointerId)
  } catch {
    /* ignore */
  }
}

const cardStyle = computed(() => {
  if (!pos.value) return undefined
  return {
    position: 'fixed' as const,
    left: `${pos.value.left}px`,
    top: `${pos.value.top}px`,
    width: 'min(28rem, calc(100vw - 2rem))',
    margin: '0',
  }
})
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div
        v-if="open"
        class="fixed z-[60] p-4"
        :class="
          pos
            ? 'inset-0 pointer-events-none'
            : {
                'inset-x-0 bottom-0 flex justify-center pointer-events-none': dock === 'bottom',
                'inset-0 flex items-end justify-center pointer-events-none lg:items-center lg:justify-end': dock === 'side',
                'inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm': dock === 'center',
              }
        "
        @click.self="emit('close')"
      >
        <div
          ref="cardEl"
          class="card relative w-full"
          :class="[
            wide ? 'max-w-2xl' : 'max-w-md',
            'pointer-events-auto shadow-pop',
            fixed && dock === 'side' && !pos ? 'flex max-h-[40vh] flex-col overflow-hidden lg:h-[32rem] lg:max-h-[32rem]' : '',
            fixed && dock !== 'side' && !pos ? 'flex h-[32rem] flex-col overflow-hidden' : '',
            !fixed ? 'max-h-[88vh] overflow-y-auto' : '',
            !pos ? 'animate-pop-in' : '',
            dragging ? 'cursor-grabbing' : '',
          ]"
          :style="cardStyle"
          role="dialog"
          aria-modal="true"
        >
          <button class="game-result-close" type="button" aria-label="关闭" @click="emit('close')">×</button>
          <div
            class="mb-4 flex items-center gap-2 pr-8"
            :class="draggable ? 'select-none touch-none' : ''"
            :style="draggable ? { cursor: dragging ? 'grabbing' : 'grab' } : undefined"
            @pointerdown="onDragStart"
            @pointermove="onDragMove"
            @pointerup="onDragEnd"
            @pointercancel="onDragEnd"
          >
            <span v-if="emoji" class="text-2xl">{{ emoji }}</span>
            <h2 class="text-xl font-extrabold text-brand-700">{{ title }}</h2>
            <span v-if="draggable" class="ml-auto text-xs font-bold text-brand-600/50">拖标题可挪开</span>
          </div>
          <div :class="fixed ? 'flex min-h-0 flex-1 flex-col' : ''">
            <slot />
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
