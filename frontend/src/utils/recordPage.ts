import { pickVideoRecorderMime } from './mediaMime'

export type PageClip = {
  blob: Blob
  durationSec: number
  score: number
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('书页图加载失败'))
    img.src = src
  })
}

export async function recordPageClip(imageUrl: string): Promise<{
  stop: () => Promise<PageClip>
  stream: MediaStream
}> {
  const img = await loadImage(imageUrl)
  const canvas = document.createElement('canvas')
  canvas.width = 1280
  canvas.height = 720
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('无法创建画布')
  const draw = () => {
    ctx.fillStyle = '#fff7ed'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    const scale = Math.min(canvas.width / img.width, canvas.height / img.height)
    const w = img.width * scale
    const h = img.height * scale
    ctx.drawImage(img, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h)
  }
  draw()
  const timer = window.setInterval(draw, 200)
  const canvasStream = canvas.captureStream(15)
  const mic = await navigator.mediaDevices.getUserMedia({ audio: true })
  mic.getAudioTracks().forEach((track) => canvasStream.addTrack(track))
  const mime = pickVideoRecorderMime()
  const recorder = mime ? new MediaRecorder(canvasStream, { mimeType: mime }) : new MediaRecorder(canvasStream)
  const chunks: Blob[] = []
  recorder.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data)
  }
  const started = Date.now()
  recorder.start()
  return {
    stream: canvasStream,
    stop: () =>
      new Promise((resolve) => {
        recorder.onstop = () => {
          window.clearInterval(timer)
          mic.getTracks().forEach((track) => track.stop())
          canvasStream.getTracks().forEach((track) => track.stop())
          const blob = new Blob(chunks, { type: recorder.mimeType || 'video/mp4' })
          resolve({
            blob,
            durationSec: Math.max(1, Math.round((Date.now() - started) / 1000)),
            score: 0,
          })
        }
        if (recorder.state !== 'inactive') recorder.stop()
        else recorder.onstop(new Event('stop'))
      }),
  }
}
