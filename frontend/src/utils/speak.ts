import { ensureTts } from './ensureAsset'

const urlCache = new Map<string, string>()

let currentAudio: HTMLAudioElement | null = null

export function stopSpeak() {
  if (!currentAudio) return
  currentAudio.pause()
  currentAudio.onended = null
  currentAudio.onerror = null
  currentAudio = null
}

async function playUrl(url: string): Promise<void> {
  stopSpeak()
  const audio = new Audio(url)
  currentAudio = audio
  await new Promise<void>((resolve) => {
    const done = () => {
      audio.onended = null
      audio.onerror = null
      if (currentAudio === audio) currentAudio = null
      resolve()
    }
    audio.onended = done
    audio.onerror = done
    audio.play().catch(done)
  })
}

export async function speakText(text: string, purpose = '单词发音'): Promise<void> {
  const value = (text || '').trim()
  if (!value) return
  const cached = urlCache.get(value.toLowerCase())
  const url = cached || (await ensureTts(value, purpose))
  if (!url) return
  if (urlCache.size > 200) urlCache.clear()
  urlCache.set(value.toLowerCase(), url)
  await playUrl(url)
}
