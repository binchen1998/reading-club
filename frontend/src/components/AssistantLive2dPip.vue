<script setup lang="ts">
/**
 * 左下角助教 Live2D：提问回复用 Magic TTS 驱动口型。
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as PIXI from 'pixi.js'

import { useAssistantPipFrame } from '../composables/useAssistantPipFrame'
import {
  ASSISTANT_FISH_TEACHER,
  getActiveTtsTeacher,
  subscribeTtsPlayback,
} from '../utils/assistantTts'
import { ensureCubismCore } from '../utils/live2dCubism'
import {
  attachLipSyncAnalyser,
  attachLipSyncAudio,
  detachLipSyncAudio,
  getMouthOpen,
} from '../utils/live2dLipSync'

const props = defineProps<{
  visible?: boolean
}>()

function publicAsset(path: string) {
  return `/${path.replace(/^\//, '')}`
}

const SIMPLE_MODEL = publicAsset('live2d/models/simple/simple.model3.json')
const MOUTH_PARAMS = ['ParamMouthOpenY', 'PARAM_MOUTH_OPEN_Y']
/** simple 模型嘴形偏保守，额外放大口型驱动 */
const MOUTH_APPLY_GAIN = 1.85

const canvasEl = ref<HTMLCanvasElement | null>(null)
const ready = ref(false)
const loadError = ref('')

const {
  rootEl,
  pipW,
  pipH,
  dragging,
  resizing,
  userMoved,
  pipStyle,
  applyLayoutAfterSizeChange,
  placeDefault,
  onPointerDown,
  onResizePointerDown,
  onPointerMove,
  onPointerUp,
} = useAssistantPipFrame({
  defaultAspect: 4 / 3,
  onFrameChange: () => resizePixi(),
})

type Live2DModelType = import('pixi-live2d-display').Live2DModel
let app: PIXI.Application | null = null
let model: Live2DModelType | null = null
let unsubTts: (() => void) | null = null
let mouthTicker: ((dt: number) => void) | null = null
let initPromise: Promise<void> | null = null
;(window as unknown as { PIXI: typeof PIXI }).PIXI = PIXI

function layoutModel() {
  if (!app || !model) return
  const w = app.screen.width
  const h = app.screen.height
  model.scale.set(1)
  model.anchor.set(0.5, 0.5)
  const mw = model.width || 1
  const mh = model.height || 1
  const scale = Math.min(w / mw, h / mh) * 1.28
  model.scale.set(scale)
  model.position.set(w / 2, h * 0.58)
}

function applyMouth(v: number) {
  const core = model?.internalModel?.coreModel as
    | { setParameterValueById?: (id: string, value: number) => void }
    | undefined
  if (!core?.setParameterValueById) return
  const open = Math.max(0, Math.min(1, v * MOUTH_APPLY_GAIN))
  for (const id of MOUTH_PARAMS) {
    try {
      core.setParameterValueById(id, open)
    } catch {
      /* ignore */
    }
  }
}

function destroyPixi() {
  if (app && mouthTicker) {
    try {
      app.ticker.remove(mouthTicker)
    } catch {
      /* ignore */
    }
  }
  mouthTicker = null
  if (model) {
    try {
      app?.stage.removeChild(model)
      model.destroy()
    } catch {
      /* ignore */
    }
  }
  model = null
  if (app) {
    try {
      app.destroy(true, { children: true })
    } catch {
      /* ignore */
    }
  }
  app = null
  ready.value = false
}

async function initPixi() {
  if (app || initPromise) return initPromise || undefined
  loadError.value = ''
  initPromise = (async () => {
    await nextTick()
    if (!canvasEl.value) throw new Error('Live2D canvas 未就绪')
    await ensureCubismCore()
    const { Live2DModel } = await import('pixi-live2d-display/cubism4')
    Live2DModel.registerTicker(PIXI.Ticker)

    app = new PIXI.Application({
      view: canvasEl.value,
      width: pipW.value,
      height: pipH.value,
      backgroundAlpha: 0,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
      // pixi-live2d-display 内嵌 Pixi v6 对象，v7 EventSystem hitTest 会报
      // isInteractive is not a function；拖拽走外层 DOM，这里关掉交互即可
      eventFeatures: {
        move: false,
        globalMove: false,
        click: false,
        wheel: false,
      },
    })
    app.stage.eventMode = 'none'
    app.stage.interactiveChildren = false
    try {
      // 摘掉 canvas/window 上的 Pixi 指针监听，避免 hitTest 扫到 Live2D 内部旧版节点
      app.renderer.events?.setTargetElement(null)
    } catch {
      /* ignore */
    }

    model = await Live2DModel.from(SIMPLE_MODEL, { autoInteract: false })
    model.eventMode = 'none'
    model.interactiveChildren = false
    // 兼容库内仍写 interactive=true 的旧路径
    ;(model as unknown as { interactive?: boolean }).interactive = false
    app.stage.addChild(model)
    try {
      model.internalModel.motionManager.stopAllMotions()
    } catch {
      /* ignore */
    }
    layoutModel()
    requestAnimationFrame(() => layoutModel())

    mouthTicker = () => {
      applyMouth(getMouthOpen())
    }
    app.ticker.add(mouthTicker)
    ready.value = true
  })()
    .catch((e: unknown) => {
      loadError.value = e instanceof Error ? e.message : 'Live2D 加载失败'
      console.warn('[AssistantLive2dPip]', e)
      destroyPixi()
    })
    .finally(() => {
      initPromise = null
    })

  return initPromise
}

function resizePixi() {
  if (!app) return
  app.renderer.resize(pipW.value, pipH.value)
  layoutModel()
}

async function onTtsPlay(audio: HTMLAudioElement) {
  // 仅 Magic（助教）音色驱动口型，避免 Jasmin 讲解误带动画
  if (getActiveTtsTeacher() !== ASSISTANT_FISH_TEACHER) return
  try {
    if (!app) await initPixi()
    else resizePixi()
    await attachLipSyncAudio(audio)
  } catch (e) {
    console.warn('[AssistantLive2dPip] lip-sync failed', e)
  }
}

async function onTtsStreamAnalyser(analyser: AnalyserNode) {
  if (getActiveTtsTeacher() !== ASSISTANT_FISH_TEACHER) return
  try {
    if (!app) await initPixi()
    else resizePixi()
    await attachLipSyncAnalyser(analyser)
  } catch (e) {
    console.warn('[AssistantLive2dPip] stream lip-sync failed', e)
  }
}

function onTtsStop() {
  if (getActiveTtsTeacher() !== ASSISTANT_FISH_TEACHER) return
  detachLipSyncAudio()
}

function onResize() {
  applyLayoutAfterSizeChange()
}

watch(
  () => props.visible,
  async (on) => {
    if (on) {
      applyLayoutAfterSizeChange()
      if (!app) await initPixi()
      else resizePixi()
    } else {
      detachLipSyncAudio()
      destroyPixi()
      userMoved.value = false
    }
  },
)

onMounted(async () => {
  applyLayoutAfterSizeChange()
  await nextTick()
  if (!userMoved.value) placeDefault()
  unsubTts = subscribeTtsPlayback({
    onPlay: onTtsPlay,
    onStreamAnalyser: onTtsStreamAnalyser,
    onStop: onTtsStop,
  })
  window.addEventListener('resize', onResize)
  if (props.visible) await initPixi()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  unsubTts?.()
  unsubTts = null
  detachLipSyncAudio()
  destroyPixi()
})
</script>

<template>
  <div
    v-if="visible"
    ref="rootEl"
    class="assistant-pip-root"
    :class="{ dragging, resizing }"
    :style="pipStyle"
    aria-label="助教"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
  >
    <div
      class="assistant-badge"
      :style="{ fontSize: `${pipH < 120 ? 10 : 11}px`, padding: pipH < 120 ? '2px 6px' : '3px 8px' }"
    >
      助教
    </div>
    <div class="assistant-frame">
      <canvas ref="canvasEl" class="assistant-canvas" />
      <div v-if="!ready && !loadError" class="assistant-status">助教准备中…</div>
      <div v-else-if="loadError" class="assistant-status assistant-status-err">形象加载失败</div>
    </div>
    <div class="resize-handle nw" @pointerdown="onResizePointerDown($event, 'nw')" />
    <div class="resize-handle ne" @pointerdown="onResizePointerDown($event, 'ne')" />
    <div class="resize-handle sw" @pointerdown="onResizePointerDown($event, 'sw')" />
    <div class="resize-handle se" @pointerdown="onResizePointerDown($event, 'se')" />
  </div>
</template>

<style scoped>
.assistant-pip-root {
  position: fixed;
  z-index: 80;
  overflow: visible;
  cursor: grab;
  touch-action: none;
  user-select: none;
}
.assistant-pip-root.dragging {
  cursor: grabbing;
}
.assistant-pip-root.resizing {
  cursor: nwse-resize;
}
.resize-handle {
  position: absolute;
  z-index: 2;
  width: 16px;
  height: 16px;
  background: transparent;
  border: 0;
  box-shadow: none;
}
.resize-handle.nw {
  top: -6px;
  left: -6px;
  cursor: nwse-resize;
}
.resize-handle.ne {
  top: -6px;
  right: -6px;
  cursor: nesw-resize;
}
.resize-handle.sw {
  bottom: -6px;
  left: -6px;
  cursor: nesw-resize;
}
.resize-handle.se {
  bottom: -6px;
  right: -6px;
  cursor: nwse-resize;
}
.assistant-frame {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-style: solid;
  border-color: rgba(255, 255, 255, 0.92);
  border-width: inherit;
  border-radius: inherit;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.28);
  background: linear-gradient(160deg, #ecfeff 0%, #cffafe 55%, #a5f3fc 100%);
}
.assistant-canvas {
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.assistant-status {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 800;
  color: rgb(14 116 144 / 0.9);
  pointer-events: none;
}
.assistant-status-err {
  color: rgb(185 28 28 / 0.9);
}
.assistant-badge {
  position: absolute;
  left: 50%;
  bottom: calc(100% + 6px);
  transform: translateX(-50%);
  white-space: nowrap;
  border-radius: 999px;
  background: rgba(14, 116, 144, 0.85);
  color: rgba(255, 255, 255, 0.95);
  font-weight: 800;
  line-height: 1.2;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.2);
}
</style>
