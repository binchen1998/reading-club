import { ensureTts } from './ensureAsset'

export const ASSISTANT_FISH_TEACHER = 'Magic'

type Listener = {
  onPlay?: (audio: HTMLAudioElement) => void
  onStreamAnalyser?: (analyser: AnalyserNode) => void
  onStop?: () => void
}

const listeners = new Set<Listener>()
let current: HTMLAudioElement | null = null
let activeTeacher = ''

export function subscribeTtsPlayback(listener: Listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function getActiveTtsTeacher() {
  return activeTeacher
}

export function stopAssistantSpeak() {
  activeTeacher = ''
  if (current) {
    current.pause()
    current.onended = null
    current.onerror = null
    current = null
  }
  listeners.forEach((item) => item.onStop?.())
}

export async function speakAssistantText(text: string) {
  const value = (text || '').trim()
  if (!value) return
  stopAssistantSpeak()
  const url = await ensureTts(value, '助教回复')
  if (!url) return
  const audio = new Audio(url)
  current = audio
  activeTeacher = ASSISTANT_FISH_TEACHER
  listeners.forEach((item) => item.onPlay?.(audio))
  await new Promise<void>((resolve) => {
    const done = () => {
      audio.onended = null
      audio.onerror = null
      if (current === audio) current = null
      activeTeacher = ''
      listeners.forEach((item) => item.onStop?.())
      resolve()
    }
    audio.onended = done
    audio.onerror = done
    audio.play().catch(done)
  })
}
