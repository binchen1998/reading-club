<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

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
const handleEl = ref<HTMLDivElement | null>(null)
const pos = ref<{ left: number; top: number; width: number } | null>(null)
const dragging = ref(false)

const DRAG_THRESHOLD = 3
let activePointer: number | null = null
let pending = false
let dragOffsetX = 0
let dragOffsetY = 0
let startClientX = 0
let startClientY = 0
let startLeft = 0
let startTop = 0
let startWidth = 0

watch(
  () => props.open,
  (open) => {
    if (open) {
      pos.value = null
      dragging.value = false
    }
    stopDrag()
  },
)

function stopDrag() {
  window.removeEventListener('pointermove', onWindowMove)
  window.removeEventListener('pointerup', onWindowUp)
  window.removeEventListener('pointercancel', onWindowUp)
  pending = false
  dragging.value = false
  activePointer = null
}

function onDragStart(e: PointerEvent) {
  if (!props.draggable) return
  if (e.button != null && e.button !== 0) return
  if ((e.target as HTMLElement).closest('button')) return
  const el = cardEl.value
  if (!el) return
  e.preventDefault()
  const rect = el.getBoundingClientRect()
  activePointer = e.pointerId
  pending = true
  dragging.value = true
  startClientX = e.clientX
  startClientY = e.clientY
  startLeft = rect.left
  startTop = rect.top
  startWidth = rect.width
  dragOffsetX = e.clientX - rect.left
  dragOffsetY = e.clientY - rect.top
  window.addEventListener('pointermove', onWindowMove)
  window.addEventListener('pointerup', onWindowUp)
  window.addEventListener('pointercancel', onWindowUp)
  try {
    handleEl.value?.setPointerCapture(e.pointerId)
  } catch {
    /* ignore */
  }
}

function applyPos(clientX: number, clientY: number) {
  const maxL = Math.max(8, window.innerWidth - 80)
  const maxT = Math.max(8, window.innerHeight - 48)
  pos.value = {
    left: Math.min(Math.max(8, clientX - dragOffsetX), maxL),
    top: Math.min(Math.max(8, clientY - dragOffsetY), maxT),
    width: startWidth,
  }
}

function onWindowMove(e: PointerEvent) {
  if (activePointer !== e.pointerId) return
  if (pending) {
    const dx = e.clientX - startClientX
    const dy = e.clientY - startClientY
    if (dx * dx + dy * dy < DRAG_THRESHOLD * DRAG_THRESHOLD) return
    pending = false
    applyPos(startClientX, startClientY)
  }
  applyPos(e.clientX, e.clientY)
}

function onWindowUp(e: PointerEvent) {
  if (activePointer != null && e.pointerId !== activePointer) return
  try {
    if (activePointer != null) handleEl.value?.releasePointerCapture(activePointer)
  } catch {
    /* ignore */
  }
  stopDrag()
}

onBeforeUnmount(stopDrag)

const cardStyle = computed(() => {
  if (!pos.value) return undefined
  return {
    position: 'fixed' as const,
    left: `${pos.value.left}px`,
    top: `${pos.value.top}px`,
    width: `${pos.value.width}px`,
    maxWidth: 'none',
    margin: '0',
  }
})
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div
        v-if="open"
        class="fixed z-[60] p-2 lg:p-4"
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
          class="card relative w-full max-lg:p-3"
          :class="[
            wide ? 'max-w-2xl' : 'max-w-md',
            'pointer-events-auto shadow-pop',
            fixed && dock === 'side' && !pos ? 'flex max-h-[40vh] flex-col overflow-hidden lg:h-[32rem] lg:max-h-[32rem]' : '',
            fixed && dock !== 'side' && !pos ? 'flex h-[32rem] flex-col overflow-hidden' : '',
            !fixed ? 'max-h-[92dvh] overflow-y-auto lg:max-h-[88vh]' : '',
            !pos ? 'animate-pop-in' : '',
            dragging ? 'cursor-grabbing' : '',
          ]"
          :style="cardStyle"
          role="dialog"
          aria-modal="true"
        >
          <button class="game-result-close" type="button" aria-label="关闭" @click="emit('close')">×</button>
          <div
            ref="handleEl"
            class="mb-2 -mx-2 -mt-1 flex items-center gap-1.5 rounded-2xl px-2 py-1 pr-10 lg:mb-4 lg:gap-2 lg:py-2"
            :class="draggable ? 'select-none touch-none' : ''"
            :style="draggable ? { cursor: dragging ? 'grabbing' : 'grab' } : undefined"
            @pointerdown="onDragStart"
          >
            <span v-if="draggable" class="grid h-6 w-5 shrink-0 place-items-center text-brand-400 lg:h-8 lg:w-6" aria-hidden="true">
              <span class="leading-none tracking-tight">⋮⋮</span>
            </span>
            <span v-if="emoji" class="text-lg lg:text-2xl">{{ emoji }}</span>
            <h2 class="text-base font-extrabold text-brand-700 lg:text-xl">{{ title }}</h2>
            <span v-if="draggable" class="ml-auto text-[10px] font-bold text-brand-600/50 lg:text-xs">按住拖走</span>
          </div>
          <div :class="fixed ? 'flex min-h-0 flex-1 flex-col' : ''">
            <slot />
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
