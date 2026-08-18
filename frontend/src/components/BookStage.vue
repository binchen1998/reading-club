<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { clampScale, loadBookScale, saveBookScale } from '../utils/bookZoom'
import { inflateBox, normalize, type Box } from '../utils/text'

const props = defineProps<{
  src: string
  boxes: Box[]
  hotspots?: Box[]
  activeText?: string
  bookKey: string
}>()

const emit = defineEmits<{ select: [box: Box] }>()

const viewport = ref<HTMLElement | null>(null)
const scale = ref(1)
const panX = ref(0)
const panY = ref(0)

let pinchStart = 0
let pinchScale = 1
let pinching = false
let panning = false
let didGesture = false
let suppressClick = false
let panStartX = 0
let panStartY = 0
let panFromX = 0
let panFromY = 0

const tapHotspots = computed(() => (props.hotspots || []).map((box) => inflateBox(box, 0.35, 0.35)))

function persist() {
  saveBookScale(props.bookKey, scale.value)
}

function applyScale(next: number) {
  scale.value = clampScale(next)
  if (scale.value <= 1) {
    panX.value = 0
    panY.value = 0
  }
}

function distance(touches: TouchList) {
  const a = touches[0]
  const b = touches[1]
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)
}

function onTouchStart(event: TouchEvent) {
  didGesture = false
  if (event.touches.length === 2) {
    pinching = true
    panning = false
    didGesture = true
    pinchStart = distance(event.touches)
    pinchScale = scale.value
    event.preventDefault()
    return
  }
  if (event.touches.length === 1 && scale.value > 1) {
    panning = true
    panStartX = event.touches[0].clientX
    panStartY = event.touches[0].clientY
    panFromX = panX.value
    panFromY = panY.value
  }
}

function onTouchMove(event: TouchEvent) {
  if (pinching && event.touches.length === 2 && pinchStart) {
    didGesture = true
    event.preventDefault()
    applyScale(pinchScale * (distance(event.touches) / pinchStart))
    return
  }
  if (panning && event.touches.length === 1) {
    const dx = event.touches[0].clientX - panStartX
    const dy = event.touches[0].clientY - panStartY
    if (Math.hypot(dx, dy) < 10) return
    didGesture = true
    event.preventDefault()
    panX.value = panFromX + dx
    panY.value = panFromY + dy
  }
}

function onTouchEnd(event: TouchEvent) {
  if (event.touches.length < 2) {
    if (pinching) persist()
    pinching = false
  }
  if (event.touches.length === 0) {
    if (didGesture) {
      suppressClick = true
      window.setTimeout(() => {
        suppressClick = false
      }, 320)
    }
    panning = false
  }
}

function onWheel(event: WheelEvent) {
  if (!event.ctrlKey && !event.metaKey && Math.abs(event.deltaY) < 40) return
  event.preventDefault()
  const factor = event.deltaY > 0 ? 0.94 : 1.06
  applyScale(scale.value * factor)
  persist()
}

function isActive(box: Box) {
  return !!props.activeText && normalize(box.text) === normalize(props.activeText)
}

function onHotspotClick(box: Box) {
  if (suppressClick || didGesture) return
  if (!box.text?.trim()) return
  emit('select', box)
}

watch(
  () => props.bookKey,
  (key) => {
    scale.value = loadBookScale(key)
    panX.value = 0
    panY.value = 0
  },
  { immediate: true },
)

onMounted(() => {
  const el = viewport.value
  if (!el) return
  el.addEventListener('touchstart', onTouchStart, { passive: false })
  el.addEventListener('touchmove', onTouchMove, { passive: false })
  el.addEventListener('touchend', onTouchEnd)
  el.addEventListener('wheel', onWheel, { passive: false })
})

onUnmounted(() => {
  const el = viewport.value
  if (!el) return
  el.removeEventListener('touchstart', onTouchStart)
  el.removeEventListener('touchmove', onTouchMove)
  el.removeEventListener('touchend', onTouchEnd)
  el.removeEventListener('wheel', onWheel)
})
</script>

<template>
  <div ref="viewport" class="book-stage relative h-full min-h-0 w-full overflow-hidden">
    <div
      class="absolute inset-0 flex items-center justify-center"
      :style="{ transform: `translate(${panX}px, ${panY}px) scale(${scale})`, transformOrigin: 'center center' }"
    >
      <div class="relative h-full w-fit">
        <img :src="src" alt="书页" class="block h-full w-auto max-w-none select-none" draggable="false" />
        <div class="pointer-events-none absolute inset-0">
          <div
            v-for="(box, i) in boxes"
            :id="i === 0 ? 'read-box-0' : undefined"
            :key="`mark-${i}`"
            class="book-mark absolute transition-all duration-150"
            :class="box.active ? 'book-mark-read' : 'book-mark-focus'"
            :style="{ left: box.left + '%', top: box.top + '%', width: box.width + '%', height: box.height + '%' }"
          />
        </div>
        <button
          v-for="(box, i) in tapHotspots"
          :key="`hot-${i}-${box.text}`"
          type="button"
          class="book-hotspot absolute z-[15] rounded-sm"
          :class="isActive(box) ? 'book-hotspot-active' : ''"
          :style="{ left: box.left + '%', top: box.top + '%', width: box.width + '%', height: box.height + '%' }"
          :aria-label="box.text"
          @click.stop="onHotspotClick(box)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.book-stage {
  touch-action: none;
}
.book-hotspot {
  cursor: pointer;
  background: transparent;
  border: 1px solid transparent;
}
.book-hotspot:hover {
  background: rgba(249, 115, 22, 0.18);
  border-color: rgba(249, 115, 22, 0.4);
}
.book-hotspot-active {
  background: rgba(251, 146, 60, 0.22);
  border-color: rgba(251, 146, 60, 0.45);
}
</style>
