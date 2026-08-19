import { pickVideoRecorderMime } from './mediaMime'
import type { PageClip } from './recordPage'

export function isMergeAborted(err: unknown) {
  return (err instanceof DOMException && err.name === 'AbortError') || (err instanceof Error && err.name === 'AbortError')
}

function abortError() {
  return new DOMException('合并已取消', 'AbortError')
}

function throwIfAborted(signal?: AbortSignal) {
  if (signal?.aborted) throw abortError()
}

function wait(el: HTMLMediaElement, ev: string, timeoutMs = 8000, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError())
      return
    }
    if (ev === 'playing' && !el.paused && el.readyState >= 2) {
      resolve()
      return
    }
    const t = window.setTimeout(() => resolve(), timeoutMs)
    const done = () => {
      cleanup()
      resolve()
    }
    const onAbort = () => {
      cleanup()
      reject(abortError())
    }
    const cleanup = () => {
      window.clearTimeout(t)
      el.removeEventListener(ev, done)
      el.removeEventListener('error', done)
      signal?.removeEventListener('abort', onAbort)
    }
    el.addEventListener(ev, done, { once: true })
    el.addEventListener('error', done, { once: true })
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

function waitClipEnd(video: HTMLVideoElement, timeoutMs: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError())
      return
    }
    if (video.ended || (video.paused && video.currentTime > 0.2)) {
      resolve()
      return
    }
    const timer = window.setTimeout(resolve, timeoutMs)
    const done = () => {
      cleanup()
      resolve()
    }
    const onAbort = () => {
      cleanup()
      reject(abortError())
    }
    const cleanup = () => {
      window.clearTimeout(timer)
      video.removeEventListener('ended', done)
      video.removeEventListener('error', done)
      signal?.removeEventListener('abort', onAbort)
    }
    video.addEventListener('ended', done, { once: true })
    video.addEventListener('error', done, { once: true })
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

function waitRecorderStop(recorder: MediaRecorder, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError())
      return
    }
    const timer = window.setTimeout(resolve, 4000)
    const done = () => {
      cleanup()
      resolve()
    }
    const onAbort = () => {
      cleanup()
      reject(abortError())
    }
    const cleanup = () => {
      window.clearTimeout(timer)
      recorder.removeEventListener('stop', done)
      signal?.removeEventListener('abort', onAbort)
    }
    recorder.addEventListener('stop', done, { once: true })
    signal?.addEventListener('abort', onAbort, { once: true })
    try {
      if (recorder.state === 'recording') recorder.requestData()
      if (recorder.state !== 'inactive') recorder.stop()
    } catch {
      cleanup()
      resolve()
    }
  })
}

function releaseVideo(video: HTMLVideoElement, source?: MediaElementAudioSourceNode | null) {
  try {
    video.pause()
  } catch {
    /* ignore */
  }
  source?.disconnect()
  const src = video.src
  video.removeAttribute('src')
  video.load()
  if (src && src.startsWith('blob:')) URL.revokeObjectURL(src)
}

export async function concatClips(
  clips: PageClip[],
  onProgress?: (info: { percent: number; text: string }) => void,
  signal?: AbortSignal,
): Promise<PageClip> {
  const usable = clips.filter((c) => c.blob.size > 1000)
  if (!usable.length) throw new Error('没有可合并的录音')
  const report = (percent: number, text: string) => {
    onProgress?.({ percent: Math.max(0, Math.min(100, Math.round(percent))), text })
  }
  throwIfAborted(signal)
  if (usable.length === 1) {
    report(100, '本页只有一段，无需合并')
    return usable[0]
  }

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

  let currentVideo: HTMLVideoElement | null = null
  let currentSource: MediaElementAudioSourceNode | null = null
  let cleaned = false
  const cleanup = () => {
    if (cleaned) return
    cleaned = true
    if (currentVideo) releaseVideo(currentVideo, currentSource)
    currentVideo = null
    currentSource = null
    try {
      if (recorder.state !== 'inactive') recorder.stop()
    } catch {
      /* ignore */
    }
    canvasStream.getTracks().forEach((track) => track.stop())
    void audioCtx.close().catch(() => undefined)
  }

  try {
    recorder.start(250)
    const started = Date.now()
    for (let i = 0; i < usable.length; i += 1) {
      throwIfAborted(signal)
      const clip = usable[i]
      report((i / usable.length) * 90, `正在合并第 ${i + 1} / ${usable.length} 段`)
      const video = document.createElement('video')
      video.playsInline = true
      video.preload = 'auto'
      video.src = URL.createObjectURL(clip.blob)
      video.muted = true
      currentVideo = video
      const onTime = () => {
        const dur = video.duration || clip.durationSec || 1
        const t = Math.min(1, (video.currentTime || 0) / Math.max(0.1, dur))
        report(((i + t) / usable.length) * 90, `正在合并第 ${i + 1} / ${usable.length} 段`)
      }
      video.addEventListener('timeupdate', onTime)
      try {
        await video.play()
      } catch {
        /* 继续尝试画一帧 */
      }
      await wait(video, 'playing', 6000, signal)
      throwIfAborted(signal)
      const source = audioCtx.createMediaElementSource(video)
      currentSource = source
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
      await waitClipEnd(video, maxMs, signal)
      video.removeEventListener('timeupdate', onTime)
      releaseVideo(video, source)
      if (currentVideo === video) currentVideo = null
      if (currentSource === source) currentSource = null
    }
    throwIfAborted(signal)
    report(95, '正在收尾…')
    await waitRecorderStop(recorder, signal)
    if (!chunks.length) throw new Error('合并录音失败')
    report(100, '合并完成')
    return {
      blob: new Blob(chunks, { type: recorder.mimeType || 'video/mp4' }),
      durationSec: Math.max(1, Math.round((Date.now() - started) / 1000)),
      score: Math.round(usable.reduce((sum, c) => sum + c.score, 0) / usable.length),
    }
  } finally {
    cleanup()
  }
}
