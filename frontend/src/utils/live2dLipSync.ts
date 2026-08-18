/**
 * Live2D 口型：从 TTS AudioElement 做 Web Audio 分析
 * - 时域 RMS + 语音频段能量
 * - 起音强调 + 峰值快衰减 → 音节间自然闭合
 * - 持续有声时叠加音节节律，避免嘴一直张着
 * - 跨域无法挂 Analyser 时，用播放时长类语音包络 fallback
 */

export type LipSyncMode = 'analyser' | 'envelope' | 'idle'

let audioCtx: AudioContext | null = null
let analyser: AnalyserNode | null = null
let sourceNode: MediaElementAudioSourceNode | null = null
let attachedAudio: HTMLAudioElement | null = null
/** true：本模块创建并负责 disconnect；false：外部流式图传入，仅解引用 */
let ownsAnalyser = false
let mode: LipSyncMode = 'idle'
let mouthOpen = 0
let envelopeUntil = 0
let envelopeStartedAt = 0
let envelopeDuration = 0
let rafId = 0
let timeDomain: Float32Array | null = null
let freqDomain: Uint8Array | null = null

/** 慢包络，用于检出音节起音 */
let slowEnergy = 0
/** 峰值保持，衰减制造开合 */
let peakHold = 0
/** 连续有声起始时间（ms） */
let speakingSince = 0

const RMS_WEIGHT = 0.4
const BAND_WEIGHT = 0.6
const GAIN = 5.2
const NOISE_GATE = 0.028
/** 张嘴稍快 */
const ATTACK = 0.55
/** 闭嘴稍慢，避免刚张开就合上 */
const RELEASE = 0.28
const SLOW_EMA = 0.1
const PEAK_DECAY = 0.92
/** 中文音节大致速率 */
const SYLLABLE_HZ = 4.2
const MAX_OPEN = 1

function ensureContext(): AudioContext {
  if (!audioCtx) {
    audioCtx = new AudioContext()
  }
  return audioCtx
}

function clamp01(v: number) {
  return Math.max(0, Math.min(1, v))
}

function speechBandEnergy(freq: Uint8Array, sampleRate: number): number {
  const binHz = sampleRate / (freq.length * 2)
  const lo = Math.max(1, Math.floor(300 / binHz))
  const hi = Math.min(freq.length - 1, Math.ceil(3000 / binHz))
  let sum = 0
  let n = 0
  for (let i = lo; i <= hi; i += 1) {
    sum += freq[i]
    n += 1
  }
  return n ? sum / n / 255 : 0
}

function syllablePulse(now: number, energy: number): number {
  if (energy < 0.1) return 1
  // 持续有声时强制开合，模拟字与字之间的闭口
  const phase = (now / 1000) * SYLLABLE_HZ * Math.PI * 2
  // 谷值保留明显开口（约 0.28），峰值接近全开
  const primary = 0.28 + 0.72 * Math.pow(0.5 + 0.5 * Math.sin(phase), 1.1)
  const secondary = 0.78 + 0.22 * (0.5 + 0.5 * Math.sin(phase * 1.65 + 0.9))
  return clamp01(primary * secondary)
}

function shapeMouthFromEnergy(rawIn: number, now: number): number {
  // 略抬中等音量，让嘴张得更明显
  const raw = clamp01(Math.pow(Math.max(0, rawIn), 0.58))

  if (raw < NOISE_GATE) {
    speakingSince = 0
    slowEnergy *= 0.85
    peakHold *= 0.72
    return 0
  }

  if (!speakingSince) speakingSince = now
  slowEnergy += (raw - slowEnergy) * SLOW_EMA

  // 起音（相对慢包络的突起）→ 张嘴；平稳段衰减 → 闭嘴
  const onset = Math.max(0, raw - slowEnergy * 0.75)
  const drive = Math.max(raw * 0.72, onset * 1.9)

  if (drive > peakHold) peakHold = drive
  else peakHold *= PEAK_DECAY

  let shaped = peakHold
  // 连续说话超过约一音节时长后，叠节律，避免“一直张嘴”
  if (now - speakingSince > 90) {
    shaped *= syllablePulse(now, raw)
  }

  return clamp01(shaped * MAX_OPEN)
}

function computeAnalyserMouth(now: number): number {
  if (!analyser || !timeDomain || !freqDomain) return 0
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  analyser.getFloatTimeDomainData(timeDomain as any)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  analyser.getByteFrequencyData(freqDomain as any)
  let sumSq = 0
  for (let i = 0; i < timeDomain.length; i += 1) {
    const s = timeDomain[i]
    sumSq += s * s
  }
  const rms = Math.sqrt(sumSq / timeDomain.length)
  const band = speechBandEnergy(freqDomain, analyser.context.sampleRate)
  const energy = (rms * RMS_WEIGHT + band * BAND_WEIGHT) * GAIN
  return shapeMouthFromEnergy(energy, now)
}

/** 类语音包络：带音节开合，不是一直张着 */
function computeEnvelopeMouth(now: number): number {
  if (now >= envelopeUntil || envelopeDuration <= 0) return 0
  const t = (now - envelopeStartedAt) / envelopeDuration
  if (t <= 0 || t >= 1) return 0
  const attack = Math.min(1, t / 0.06)
  const release = Math.min(1, (1 - t) / 0.1)
  const gate = Math.min(attack, release)
  const pulse = syllablePulse(now, 0.5)
  return clamp01(gate * pulse * 0.95)
}

function resetShapeState() {
  slowEnergy = 0
  peakHold = 0
  speakingSince = 0
}

function tick() {
  rafId = 0
  const now = performance.now()
  let target = 0
  if (mode === 'analyser') {
    target = computeAnalyserMouth(now)
  } else if (mode === 'envelope') {
    target = computeEnvelopeMouth(now)
    if (now >= envelopeUntil) {
      mode = 'idle'
      target = 0
      resetShapeState()
    }
  }
  const alpha = target > mouthOpen ? ATTACK : RELEASE
  mouthOpen += (target - mouthOpen) * alpha
  if (mouthOpen < 0.012 && target < 0.012) mouthOpen = 0

  if (mode !== 'idle' || mouthOpen > 0.005) {
    rafId = requestAnimationFrame(tick)
  }
}

function ensureTicking() {
  if (!rafId) rafId = requestAnimationFrame(tick)
}

function teardownGraph() {
  try {
    sourceNode?.disconnect()
  } catch {
    /* ignore */
  }
  if (ownsAnalyser) {
    try {
      analyser?.disconnect()
    } catch {
      /* ignore */
    }
  }
  sourceNode = null
  attachedAudio = null
  analyser = null
  ownsAnalyser = false
}

function startEnvelopeFallback(audio: HTMLAudioElement) {
  const dur = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : 1.2
  envelopeStartedAt = performance.now()
  envelopeDuration = dur * 1000
  envelopeUntil = envelopeStartedAt + envelopeDuration
  mode = 'envelope'
  resetShapeState()
  ensureTicking()
}

/**
 * 挂到正在播放的 TTS Audio。同一元素可重复 attach。
 */
export async function attachLipSyncAudio(audio: HTMLAudioElement): Promise<void> {
  if (attachedAudio === audio && mode === 'analyser') {
    ensureTicking()
    return
  }
  teardownGraph()
  attachedAudio = audio
  resetShapeState()

  try {
    audio.crossOrigin = 'anonymous'
    const ctx = ensureContext()
    if (ctx.state === 'suspended') await ctx.resume()

    analyser = ctx.createAnalyser()
    ownsAnalyser = true
    analyser.fftSize = 1024
    // 降低平滑，保留音节间的能量起伏
    analyser.smoothingTimeConstant = 0.12
    timeDomain = new Float32Array(analyser.fftSize)
    freqDomain = new Uint8Array(analyser.frequencyBinCount)

    sourceNode = ctx.createMediaElementSource(audio)
    sourceNode.connect(analyser)
    analyser.connect(ctx.destination)
    mode = 'analyser'
    ensureTicking()
  } catch (err) {
    console.warn('[Live2D LipSync] analyser unavailable, envelope fallback', err)
    teardownGraph()
    attachedAudio = audio
    const onMeta = () => startEnvelopeFallback(audio)
    if (Number.isFinite(audio.duration) && audio.duration > 0) onMeta()
    else audio.addEventListener('loadedmetadata', onMeta, { once: true })
    if (mode !== 'envelope') {
      envelopeStartedAt = performance.now()
      envelopeDuration = 1500
      envelopeUntil = envelopeStartedAt + envelopeDuration
      mode = 'envelope'
      ensureTicking()
    }
  }
}

/**
 * 挂到外部 Web Audio 图中的 Analyser（Qwen 流式无缝接播）。
 * 不负责 disconnect，避免打断播放图。
 */
export async function attachLipSyncAnalyser(node: AnalyserNode): Promise<void> {
  if (analyser === node && mode === 'analyser' && !ownsAnalyser) {
    ensureTicking()
    return
  }
  teardownGraph()
  attachedAudio = null
  ownsAnalyser = false
  analyser = node
  timeDomain = new Float32Array(analyser.fftSize)
  freqDomain = new Uint8Array(analyser.frequencyBinCount)
  resetShapeState()
  try {
    if (analyser.context.state === 'suspended') {
      await analyser.context.resume()
    }
  } catch {
    /* ignore */
  }
  mode = 'analyser'
  ensureTicking()
}

export function detachLipSyncAudio(audio?: HTMLAudioElement | null) {
  if (audio && attachedAudio && audio !== attachedAudio) return
  teardownGraph()
  mode = 'idle'
  envelopeUntil = 0
  resetShapeState()
  ensureTicking()
}

export function getMouthOpen(): number {
  return mouthOpen
}

export function getLipSyncMode(): LipSyncMode {
  return mode
}
