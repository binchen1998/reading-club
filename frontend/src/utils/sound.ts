import { ref } from 'vue'

const MUTE_KEY = 'reading-club-muted'
export const isMuted = ref(localStorage.getItem(MUTE_KEY) === '1')

export function toggleMute() {
  isMuted.value = !isMuted.value
  localStorage.setItem(MUTE_KEY, isMuted.value ? '1' : '0')
  if (!isMuted.value) ensureCtx()?.resume()
}

let ctx: AudioContext | null = null

function ensureCtx(): AudioContext | null {
  if (typeof window === 'undefined') return null
  if (!ctx) {
    const AC = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!AC) return null
    ctx = new AC()
  }
  if (ctx.state === 'suspended') void ctx.resume()
  return ctx
}

interface Note {
  freq: number
  start: number
  dur: number
  type?: OscillatorType
  gain?: number
}

function play(notes: Note[]) {
  if (isMuted.value) return
  const ac = ensureCtx()
  if (!ac) return
  const now = ac.currentTime
  for (const n of notes) {
    const osc = ac.createOscillator()
    const g = ac.createGain()
    osc.type = n.type || 'sine'
    osc.frequency.value = n.freq
    const t0 = now + n.start
    const peak = n.gain ?? 0.18
    g.gain.setValueAtTime(0.0001, t0)
    g.gain.exponentialRampToValueAtTime(peak, t0 + 0.012)
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + n.dur)
    osc.connect(g)
    g.connect(ac.destination)
    osc.start(t0)
    osc.stop(t0 + n.dur + 0.02)
  }
}

const N = {
  C5: 523.25,
  D5: 587.33,
  E5: 659.25,
  G5: 783.99,
  A5: 880.0,
  C6: 1046.5,
  E6: 1318.5,
  G6: 1568.0,
}

export const sound = {
  /** 答对 / 朗读过关 */
  celebrate() {
    play([
      { freq: N.C5, start: 0.0, dur: 0.14, type: 'triangle', gain: 0.18 },
      { freq: N.E5, start: 0.1, dur: 0.14, type: 'triangle', gain: 0.18 },
      { freq: N.G5, start: 0.2, dur: 0.16, type: 'triangle', gain: 0.2 },
      { freq: N.C6, start: 0.32, dur: 0.28, type: 'sine', gain: 0.16 },
    ])
  },
  /** 整页 / 本章完成 */
  bigCelebrate() {
    play([
      { freq: N.C5, start: 0.0, dur: 0.16, type: 'triangle', gain: 0.2 },
      { freq: N.E5, start: 0.12, dur: 0.16, type: 'triangle', gain: 0.2 },
      { freq: N.G5, start: 0.24, dur: 0.16, type: 'triangle', gain: 0.2 },
      { freq: N.C6, start: 0.36, dur: 0.28, type: 'triangle', gain: 0.22 },
      { freq: N.E6, start: 0.48, dur: 0.28, type: 'sine', gain: 0.18 },
      { freq: N.G6, start: 0.58, dur: 0.32, type: 'sine', gain: 0.14 },
    ])
  },
  /** 答错 / 未过关 */
  fail() {
    play([
      { freq: 392.0, start: 0.0, dur: 0.12, type: 'square', gain: 0.08 },
      { freq: 277.18, start: 0.1, dur: 0.2, type: 'square', gain: 0.07 },
    ])
  },
  /** 开始录音提示 */
  recStart() {
    play([
      { freq: N.A5, start: 0.0, dur: 0.07, type: 'sine', gain: 0.12 },
      { freq: N.E6, start: 0.09, dur: 0.1, type: 'sine', gain: 0.12 },
    ])
  },
  dismiss() {
    play([{ freq: N.A5, start: 0, dur: 0.06, type: 'triangle', gain: 0.1 }])
  },
}
