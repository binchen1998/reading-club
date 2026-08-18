import { pickVideoRecorderMime } from './mediaMime'
import type { PageClip } from './recordPage'

function wait(el: HTMLMediaElement, ev: string, timeoutMs = 20000) {
  return new Promise<void>((resolve, reject) => {
    const t = window.setTimeout(() => reject(new Error('片段加载超时')), timeoutMs)
    const done = () => {
      window.clearTimeout(t)
      resolve()
    }
    el.addEventListener(ev, done, { once: true })
    el.addEventListener('error', () => {
      window.clearTimeout(t)
      reject(new Error('片段加载失败'))
    }, { once: true })
  })
}

export async function concatClips(clips: PageClip[]): Promise<PageClip> {
  const usable = clips.filter((c) => c.blob.size > 1000)
  if (!usable.length) throw new Error('没有可合并的录音')
  if (usable.length === 1) return usable[0]

  const canvas = document.createElement('canvas')
  canvas.width = 1280
  canvas.height = 720
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('无法创建画布')
  const canvasStream = canvas.captureStream(30)
  const audioCtx = new AudioContext()
  const dest = audioCtx.createMediaStreamDestination()
  dest.stream.getAudioTracks().forEach((track) => canvasStream.addTrack(track))
  const mime = pickVideoRecorderMime()
  const recorder = mime ? new MediaRecorder(canvasStream, { mimeType: mime }) : new MediaRecorder(canvasStream)
  const chunks: Blob[] = []
  recorder.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data)
  }
  recorder.start(250)
  const started = Date.now()
  for (const clip of usable) {
    const video = document.createElement('video')
    video.src = URL.createObjectURL(clip.blob)
    video.muted = true
    await video.play().catch(() => undefined)
    await wait(video, 'playing').catch(() => undefined)
    const source = audioCtx.createMediaElementSource(video)
    source.connect(dest)
    video.muted = false
    await new Promise<void>((resolve) => {
      const draw = () => {
        if (video.paused || video.ended) return
        ctx.fillStyle = '#111'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        requestAnimationFrame(draw)
      }
      draw()
      video.onended = () => resolve()
    })
    source.disconnect()
    URL.revokeObjectURL(video.src)
  }
  await new Promise<void>((resolve) => {
    recorder.addEventListener('stop', () => resolve(), { once: true })
    recorder.stop()
  })
  canvasStream.getTracks().forEach((track) => track.stop())
  await audioCtx.close().catch(() => undefined)
  return {
    blob: new Blob(chunks, { type: recorder.mimeType || 'video/mp4' }),
    durationSec: Math.max(1, Math.round((Date.now() - started) / 1000)),
    score: Math.round(usable.reduce((sum, c) => sum + c.score, 0) / usable.length),
  }
}
