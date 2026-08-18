<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useUserCamera } from '../composables/useUserCamera'

const PIP_W = 168
const PIP_H = 126
const MARGIN = 16
const ANCHOR_GAP = 10

const { enabled, stream, pos, close, setPos, resetPos } = useUserCamera()
const videoEl = ref<HTMLVideoElement | null>(null)
const rootEl = ref<HTMLDivElement | null>(null)
const dragging = ref(false)
const userMoved = ref(false)

let dragOffsetX = 0
let dragOffsetY = 0
let pointerId: number | null = null

function clampPos(left: number, top: number) {
  const maxL = Math.max(MARGIN, window.innerWidth - PIP_W - MARGIN)
  const maxT = Math.max(MARGIN, window.innerHeight - PIP_H - MARGIN)
  return {
    left: Math.min(maxL, Math.max(MARGIN, left)),
    top: Math.min(maxT, Math.max(MARGIN, top)),
  }
}

function anchorRect(): DOMRect | null {
  const el = document.querySelector('[data-camera-pip-anchor]')
  return el instanceof HTMLElement ? el.getBoundingClientRect() : null
}

function placeAboveAnchor() {
  const rect = anchorRect()
  if (rect) {
    const left = rect.left + (rect.width - PIP_W) / 2
    const top = rect.top - PIP_H - ANCHOR_GAP
    const next = clampPos(left, top)
    setPos(next.left, next.top)
    return
  }
  setPos(
    Math.max(MARGIN, window.innerWidth - PIP_W - MARGIN),
    Math.max(MARGIN, window.innerHeight - PIP_H - 120),
  )
}

function bindStream() {
  const el = videoEl.value
  if (!el) return
  if (stream.value) {
    if (el.srcObject !== stream.value) {
      el.srcObject = stream.value
    }
    el.play().catch(() => {})
  } else {
    el.srcObject = null
  }
}

async function ensureVisibleAndBound() {
  if (!enabled.value || !stream.value) return
  if (!userMoved.value || !pos.value) placeAboveAnchor()
  await nextTick()
  bindStream()
}

watch(stream, (s) => {
  if (s) void ensureVisibleAndBound()
})

watch(enabled, (on) => {
  if (!on) {
    userMoved.value = false
    resetPos()
    return
  }
  void ensureVisibleAndBound()
})

watch(videoEl, (el) => {
  if (el) bindStream()
})

function onPointerDown(e: PointerEvent) {
  if ((e.target as HTMLElement).closest('[data-pip-close]')) return
  const el = rootEl.value
  if (!el) return
  dragging.value = true
  pointerId = e.pointerId
  el.setPointerCapture(e.pointerId)
  const rect = el.getBoundingClientRect()
  dragOffsetX = e.clientX - rect.left
  dragOffsetY = e.clientY - rect.top
}

function onPointerMove(e: PointerEvent) {
  if (!dragging.value || pointerId !== e.pointerId) return
  userMoved.value = true
  const next = clampPos(e.clientX - dragOffsetX, e.clientY - dragOffsetY)
  setPos(next.left, next.top)
}

function onPointerUp(e: PointerEvent) {
  if (pointerId !== e.pointerId) return
  dragging.value = false
  pointerId = null
  rootEl.value?.releasePointerCapture(e.pointerId)
}

function onClose() {
  close()
}

function onResize() {
  if (!pos.value) return
  if (!userMoved.value) {
    placeAboveAnchor()
    return
  }
  const next = clampPos(pos.value.left, pos.value.top)
  setPos(next.left, next.top)
}

onMounted(() => {
  window.addEventListener('resize', onResize)
  void ensureVisibleAndBound()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (videoEl.value) videoEl.value.srcObject = null
})
</script>

<template>
  <div
    v-if="enabled && stream && pos"
    ref="rootEl"
    class="user-camera-pip"
    :class="{ dragging }"
    :style="{
      left: `${pos.left}px`,
      top: `${pos.top}px`,
      width: `${PIP_W}px`,
      height: `${PIP_H}px`,
    }"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  >
    <video
      ref="videoEl"
      class="pip-video"
      autoplay
      playsinline
      muted
    />
    <button
      type="button"
      data-pip-close
      class="pip-close"
      title="关闭摄像头"
      @pointerdown.stop
      @click.stop="onClose"
    >
      ✕
    </button>
    <div class="pip-hint">拖动调整位置</div>
  </div>
</template>

<style scoped>
.user-camera-pip {
  position: fixed;
  z-index: 70;
  overflow: hidden;
  border-radius: 16px;
  border: 2px solid rgba(255, 255, 255, 0.92);
  box-shadow:
    0 10px 28px rgba(15, 23, 42, 0.22),
    0 0 0 1px rgba(249, 115, 22, 0.25);
  background: #0f172a;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.user-camera-pip.dragging {
  cursor: grabbing;
}

.pip-video {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1);
  pointer-events: none;
}

.pip-close {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 2;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.pip-close:hover {
  background: rgba(15, 23, 42, 0.9);
}

.pip-hint {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 4px 8px;
  background: linear-gradient(transparent, rgba(15, 23, 42, 0.65));
  color: rgba(255, 255, 255, 0.85);
  font-size: 10px;
  font-weight: 600;
  text-align: center;
  pointer-events: none;
}
</style>
