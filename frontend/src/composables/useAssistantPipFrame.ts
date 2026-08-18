import { computed, ref } from 'vue'

import { computePipSize } from '../utils/pipLayout'

const STORAGE_KEY = 'club-assistant-pip-frame-v2'
const MIN_W = 64
const MIN_H = 80
/** 助教正下方提问按钮预留高度（按钮 + 间距） */
export const ASSISTANT_ASK_STACK = 40

const pipW = ref(90)
const pipH = ref(120)
const margin = ref(12)
const left = ref(0)
const top = ref(0)
const userMoved = ref(false)
const userSized = ref(false)
const extraBottom = ref(0)

function bottomReserve() {
  return ASSISTANT_ASK_STACK + extraBottom.value
}

export type AssistantResizeCorner = 'nw' | 'ne' | 'sw' | 'se'

function readStoredSize(): { w: number; h: number } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as { w?: unknown; h?: unknown }
    const w = Number(parsed.w)
    const h = Number(parsed.h)
    if (Number.isFinite(w) && Number.isFinite(h) && w >= MIN_W && h >= MIN_H) {
      return { w: Math.round(w), h: Math.round(h) }
    }
  } catch {
    /* ignore */
  }
  return null
}

function writeStoredSize(w: number, h: number) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ w: Math.round(w), h: Math.round(h) }))
  } catch {
    /* ignore */
  }
}

export function useAssistantPipFrame(options: {
  defaultAspect: number
  onFrameChange?: () => void
}) {
  const rootEl = ref<HTMLDivElement | null>(null)
  const dragging = ref(false)
  const resizing = ref(false)

  let dragOffsetX = 0
  let dragOffsetY = 0
  let pointerId: number | null = null
  let resizeCorner: AssistantResizeCorner | null = null
  let startW = 0
  let startH = 0
  let startL = 0
  let startT = 0
  let startX = 0
  let startY = 0

  function maxBox() {
    return {
      w: Math.max(MIN_W, window.innerWidth - margin.value * 2),
      h: Math.max(MIN_H, window.innerHeight - margin.value * 2),
    }
  }

  function clampSize(w: number, h: number) {
    const max = maxBox()
    return {
      w: Math.min(max.w, Math.max(MIN_W, Math.round(w))),
      h: Math.min(max.h, Math.max(MIN_H, Math.round(h))),
    }
  }

  function clampPos(l: number, t: number, w = pipW.value, h = pipH.value) {
    const maxL = Math.max(margin.value, window.innerWidth - w - margin.value)
    const maxT = Math.max(
      margin.value,
      window.innerHeight - h - margin.value - bottomReserve(),
    )
    return {
      left: Math.min(maxL, Math.max(margin.value, l)),
      top: Math.min(maxT, Math.max(margin.value, t)),
    }
  }

  function applyDefaultSize() {
    const s = computePipSize(window.innerWidth, window.innerHeight, options.defaultAspect)
    margin.value = s.margin
    const next = clampSize(s.width, s.height)
    pipW.value = next.w
    pipH.value = next.h
  }

  function applyStoredOrDefaultSize() {
    const s = computePipSize(window.innerWidth, window.innerHeight, options.defaultAspect)
    margin.value = s.margin
    const stored = readStoredSize()
    if (stored) {
      const next = clampSize(stored.w, stored.h)
      pipW.value = next.w
      pipH.value = next.h
      userSized.value = true
      return
    }
    applyDefaultSize()
  }

  function placeDefault() {
    const leftPad = Math.max(16, margin.value)
    const bottomPad = Math.max(16, margin.value) + bottomReserve()
    const next = clampPos(leftPad, window.innerHeight - pipH.value - bottomPad)
    left.value = next.left
    top.value = next.top
  }

  function persistSize() {
    writeStoredSize(pipW.value, pipH.value)
  }

  function applyLayoutAfterSizeChange() {
    if (userSized.value) {
      const s = computePipSize(window.innerWidth, window.innerHeight, options.defaultAspect)
      margin.value = s.margin
      const next = clampSize(pipW.value, pipH.value)
      pipW.value = next.w
      pipH.value = next.h
    } else {
      applyStoredOrDefaultSize()
    }
    if (!userMoved.value) placeDefault()
    else {
      const next = clampPos(left.value, top.value)
      left.value = next.left
      top.value = next.top
    }
    options.onFrameChange?.()
  }

  const pipStyle = computed(() => ({
    left: `${left.value}px`,
    top: `${top.value}px`,
    width: `${pipW.value}px`,
    height: `${pipH.value}px`,
    borderRadius: `${Math.max(12, Math.round(pipH.value * 0.12))}px`,
    borderWidth: `${pipH.value < 120 ? 2 : 3}px`,
  }))

  function onPointerDown(e: PointerEvent) {
    const el = rootEl.value
    if (!el || resizing.value) return
    dragging.value = true
    el.setPointerCapture(e.pointerId)
    const rect = el.getBoundingClientRect()
    dragOffsetX = e.clientX - rect.left
    dragOffsetY = e.clientY - rect.top
    pointerId = e.pointerId
  }

  function onResizePointerDown(e: PointerEvent, corner: AssistantResizeCorner) {
    e.stopPropagation()
    e.preventDefault()
    const el = rootEl.value
    if (!el) return
    resizing.value = true
    dragging.value = false
    resizeCorner = corner
    startW = pipW.value
    startH = pipH.value
    startL = left.value
    startT = top.value
    startX = e.clientX
    startY = e.clientY
    pointerId = e.pointerId
    el.setPointerCapture(e.pointerId)
  }

  function applyCornerResize(e: PointerEvent) {
    if (!resizeCorner) return
    const dx = e.clientX - startX
    const dy = e.clientY - startY
    let w = startW
    let h = startH
    let l = startL
    let t = startT
    if (resizeCorner === 'se' || resizeCorner === 'ne') w = startW + dx
    if (resizeCorner === 'sw' || resizeCorner === 'nw') w = startW - dx
    if (resizeCorner === 'se' || resizeCorner === 'sw') h = startH + dy
    if (resizeCorner === 'ne' || resizeCorner === 'nw') h = startH - dy

    const next = clampSize(w, h)
    w = next.w
    h = next.h
    if (resizeCorner === 'nw' || resizeCorner === 'sw') l = startL + startW - w
    if (resizeCorner === 'nw' || resizeCorner === 'ne') t = startT + startH - h

    pipW.value = w
    pipH.value = h
    const pos = clampPos(l, t, w, h)
    left.value = pos.left
    top.value = pos.top
    userSized.value = true
    userMoved.value = true
    persistSize()
    options.onFrameChange?.()
  }

  function onPointerMove(e: PointerEvent) {
    if (pointerId !== e.pointerId) return
    if (resizing.value) {
      applyCornerResize(e)
      return
    }
    if (!dragging.value) return
    userMoved.value = true
    const next = clampPos(e.clientX - dragOffsetX, e.clientY - dragOffsetY)
    left.value = next.left
    top.value = next.top
  }

  function onPointerUp(e: PointerEvent) {
    if (pointerId !== e.pointerId) return
    dragging.value = false
    resizing.value = false
    resizeCorner = null
    pointerId = null
    rootEl.value?.releasePointerCapture(e.pointerId)
  }

  return {
    rootEl,
    pipW,
    pipH,
    margin,
    left,
    top,
    dragging,
    resizing,
    userMoved,
    pipStyle,
    applyStoredOrDefaultSize,
    applyLayoutAfterSizeChange,
    placeDefault,
    onPointerDown,
    onResizePointerDown,
    onPointerMove,
    onPointerUp,
  }
}

/** 提问按钮跟助教共用同一套坐标 */
export function useAssistantPipRect() {
  return { left, top, pipW, pipH }
}

/** 底部出现录音条时抬高助教，避免挡住 */
export function setAssistantExtraBottom(px: number) {
  extraBottom.value = Math.max(0, Math.round(px))
  const pad = Math.max(16, margin.value) + bottomReserve()
  if (!userMoved.value) {
    const nextLeft = Math.max(16, margin.value)
    const maxL = Math.max(margin.value, window.innerWidth - pipW.value - margin.value)
    const maxT = Math.max(margin.value, window.innerHeight - pipH.value - pad)
    left.value = Math.min(maxL, nextLeft)
    top.value = Math.min(maxT, Math.max(margin.value, window.innerHeight - pipH.value - pad))
    return
  }
  const maxL = Math.max(margin.value, window.innerWidth - pipW.value - margin.value)
  const maxT = Math.max(margin.value, window.innerHeight - pipH.value - pad)
  left.value = Math.min(maxL, Math.max(margin.value, left.value))
  top.value = Math.min(maxT, Math.max(margin.value, top.value))
}
