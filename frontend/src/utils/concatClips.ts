import { pickVideoRecorderMime } from './mediaMime'
import type { PageClip } from './recordPage'

function wait(el: HTMLMediaElement, ev: string, timeoutMs = 8000) {
  return new Promise<void>((resolve) => {
    if (ev === 'playing' && !el.paused && el.readyState >= 2) {
      resolve()
      return
    }
    const t = window.setTimeout(() => resolve(), timeoutMs)
    const done = () => {
      window.clearTimeout(t)
      resolve()
    }
    el.addEventListener(ev, done, { once: true })
    el.addEventListener('error', done, { once: true })
  })
}

function waitClipEnd(video: HTMLVideoElement, timeoutMs: number) {
  return new Promise<void>((resolve) => {
    if (video.ended || (video.paused && video.currentTime > 0.2)) {
      resolve()
      return
    }
    const timer = window.setTimeout(resolve, timeoutMs)
    const done = () => {
      window.clearTimeout(timer)
      resolve()
    }
    video.addEventListener('ended', done, { once: true })
    video.addEventListener('error', done, { once: true })
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
    video.playsInline = true
    video.preload = 'auto'
    video.src = URL.createObjectURL(clip.blob)
    video.muted = true
    try {
      await video.play()
    } catch {
      /* 继续尝试画一帧 */
    }
    await wait(video, 'playing', 6000)
    const source = audioCtx.createMediaElementSource(video)
    source.connect(dest)
    video.muted = false
    const maxMs = Math.max(8000, (clip.durationSec || 8) * 1000 + 4000)
    const draw = () => {
      if (video.paused || video.ended) return
      ctx.fillStyle = '#111'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      try {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      } catch {
        /* ignore */
      }
      requestAnimationFrame(draw)
    }
    draw()
    await waitClipEnd(video, maxMs)
    source.disconnect()
    URL.revokeObjectURL(video.src)
    video.removeAttribute('src')
    video.load()
  }
  await new Promise<void>((resolve) => {
    const timer = window.setTimeout(resolve, 4000)
    recorder.addEventListener(
      'stop',
      () => {
        window.clearTimeout(timer)
        resolve()
      },
      { once: true },
    )
    try {
      if (recorder.state === 'recording') recorder.requestData()
      recorder.stop()
    } catch {
      window.clearTimeout(timer)
      resolve()
    }
  })
  canvasStream.getTracks().forEach((track) => track.stop())
  await audioCtx.close().catch(() => undefined)
  if (!chunks.length) throw new Error('合并录音失败')
  return {
    blob: new Blob(chunks, { type: recorder.mimeType || 'video/mp4' }),
    durationSec: Math.max(1, Math.round((Date.now() - started) / 1000)),
    score: Math.round(usable.reduce((sum, c) => sum + c.score, 0) / usable.length),
  }
}
