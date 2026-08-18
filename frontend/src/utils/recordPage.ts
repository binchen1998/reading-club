import { isAvatarUrl } from './avatar'
import { pickAudioRecorderMime, pickVideoRecorderMime } from './mediaMime'

export type PageClip = {
  blob: Blob
  durationSec: number
  score: number
  asrBlob?: Blob
}

export type RecordOverlay = {
  cameraStream?: MediaStream | null
  avatar?: string
  nickname?: string
}

/** 与 new337 成片右上角人像一致：1280 画布上 336px 圆 */
const OVERLAY_SIZE = 336
const OVERLAY_MARGIN = 40

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('书页图加载失败'))
    img.src = src
  })
}

function loadAvatarImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = src
  })
}

function waitRecorderStop(mr: MediaRecorder): Promise<void> {
  return new Promise((resolve) => {
    if (mr.state === 'inactive') {
      resolve()
      return
    }
    mr.addEventListener('stop', () => resolve(), { once: true })
    try {
      mr.stop()
    } catch {
      resolve()
    }
  })
}

function bindCameraVideo(stream: MediaStream): HTMLVideoElement {
  const video = document.createElement('video')
  video.muted = true
  video.playsInline = true
  video.autoplay = true
  video.setAttribute('playsinline', 'true')
  video.style.position = 'fixed'
  video.style.left = '-9999px'
  video.style.width = '2px'
  video.style.height = '2px'
  video.srcObject = stream
  document.body.appendChild(video)
  void video.play().catch(() => undefined)
  return video
}

function roundRectPath(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function drawNicknameTag(ctx: CanvasRenderingContext2D, cx: number, size: number, y: number, nickname?: string) {
  const name = (nickname || '').slice(0, 8)
  if (!name) return
  const tagH = 44
  ctx.font = 'bold 28px "Microsoft YaHei", sans-serif'
  const tw = Math.min(ctx.measureText(name).width + 36, size + 28)
  const tx = cx - tw / 2
  const ty = y + size + 14
  roundRectPath(ctx, tx, ty, tw, tagH, 16)
  ctx.fillStyle = 'rgba(15, 23, 42, 0.72)'
  ctx.fill()
  ctx.fillStyle = '#ffffff'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(name, cx, ty + tagH / 2)
}

function cameraLive(stream?: MediaStream | null) {
  const track = stream?.getVideoTracks()[0]
  return !!track && track.readyState === 'live'
}

function drawVideoOverlay(
  ctx: CanvasRenderingContext2D,
  W: number,
  video: HTMLVideoElement,
  nickname?: string,
) {
  if (video.readyState < 2) return false
  const size = OVERLAY_SIZE
  const x = W - size - OVERLAY_MARGIN
  const y = OVERLAY_MARGIN
  const r = size / 2

  ctx.save()
  ctx.beginPath()
  ctx.arc(x + r, y + r, r + 10, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()
  ctx.shadowColor = 'rgba(15, 23, 42, 0.18)'
  ctx.shadowBlur = 24
  ctx.beginPath()
  ctx.arc(x + r, y + r, r, 0, Math.PI * 2)
  ctx.fillStyle = '#0f172a'
  ctx.fill()
  ctx.shadowBlur = 0

  ctx.beginPath()
  ctx.arc(x + r, y + r, r, 0, Math.PI * 2)
  ctx.clip()

  const vw = video.videoWidth || size
  const vh = video.videoHeight || size
  const side = Math.min(vw, vh)
  const sx = (vw - side) / 2
  const sy = (vh - side) / 2
  ctx.translate(x + size, y)
  ctx.scale(-1, 1)
  ctx.drawImage(video, sx, sy, side, side, 0, 0, size, size)
  ctx.restore()

  ctx.beginPath()
  ctx.arc(x + r, y + r, r, 0, Math.PI * 2)
  ctx.strokeStyle = 'rgba(249, 115, 22, 0.55)'
  ctx.lineWidth = 8
  ctx.stroke()
  drawNicknameTag(ctx, x + r, size, y, nickname)
  return true
}

function drawAvatarOverlay(
  ctx: CanvasRenderingContext2D,
  W: number,
  avatarImg: HTMLImageElement | null,
  avatar: string,
  nickname?: string,
) {
  const size = OVERLAY_SIZE
  const x = W - size - OVERLAY_MARGIN
  const y = OVERLAY_MARGIN
  const r = size / 2

  ctx.save()
  ctx.beginPath()
  ctx.arc(x + r, y + r, r + 10, 0, Math.PI * 2)
  ctx.fillStyle = '#ffffff'
  ctx.fill()
  ctx.shadowColor = 'rgba(15, 23, 42, 0.18)'
  ctx.shadowBlur = 24
  ctx.beginPath()
  ctx.arc(x + r, y + r, r, 0, Math.PI * 2)
  ctx.fillStyle = '#fff7ed'
  ctx.fill()
  ctx.shadowBlur = 0

  ctx.beginPath()
  ctx.arc(x + r, y + r, r, 0, Math.PI * 2)
  ctx.clip()

  if (avatarImg) {
    const iw = avatarImg.naturalWidth || avatarImg.width
    const ih = avatarImg.naturalHeight || avatarImg.height
    const side = Math.min(iw, ih) || size
    const sx = (iw - side) / 2
    const sy = (ih - side) / 2
    ctx.drawImage(avatarImg, sx, sy, side, side, x, y, size, size)
  } else {
    ctx.fillStyle = '#fff7ed'
    ctx.fillRect(x, y, size, size)
    ctx.font = `${Math.floor(size * 0.55)}px "Segoe UI Emoji", "Apple Color Emoji", sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(avatar || '📖', x + r, y + r + 4)
  }
  ctx.restore()

  ctx.beginPath()
  ctx.arc(x + r, y + r, r, 0, Math.PI * 2)
  ctx.strokeStyle = 'rgba(249, 115, 22, 0.55)'
  ctx.lineWidth = 8
  ctx.stroke()
  drawNicknameTag(ctx, x + r, size, y, nickname)
}

export async function recordPageClip(
  imageUrl: string,
  overlay: RecordOverlay = {},
): Promise<{
  stop: () => Promise<PageClip>
  stream: MediaStream
}> {
  const img = await loadImage(imageUrl)
  const avatar = overlay.avatar || '📖'
  const avatarImg = isAvatarUrl(avatar) ? await loadAvatarImage(avatar) : null
  const camVideo = overlay.cameraStream ? bindCameraVideo(overlay.cameraStream) : null

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
    const live = cameraLive(overlay.cameraStream) && camVideo
    if (live && drawVideoOverlay(ctx, canvas.width, camVideo, overlay.nickname)) return
    drawAvatarOverlay(ctx, canvas.width, avatarImg, avatar, overlay.nickname)
  }
  draw()
  let raf = 0
  const tick = () => {
    draw()
    raf = window.requestAnimationFrame(tick)
  }
  raf = window.requestAnimationFrame(tick)

  const canvasStream = canvas.captureStream(30)
  const mic = await navigator.mediaDevices.getUserMedia({ audio: true })
  mic.getAudioTracks().forEach((track) => canvasStream.addTrack(track))
  const mime = pickVideoRecorderMime()
  const recorder = mime ? new MediaRecorder(canvasStream, { mimeType: mime }) : new MediaRecorder(canvasStream)
  const chunks: Blob[] = []
  recorder.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data)
  }

  const asrChunks: Blob[] = []
  let asrRecorder: MediaRecorder | null = null
  try {
    const audioMime = pickAudioRecorderMime()
    const asrStream = new MediaStream(mic.getAudioTracks())
    asrRecorder = audioMime
      ? new MediaRecorder(asrStream, { mimeType: audioMime })
      : new MediaRecorder(asrStream)
    asrRecorder.ondataavailable = (e) => {
      if (e.data.size) asrChunks.push(e.data)
    }
    asrRecorder.start(400)
  } catch {
    asrRecorder = null
  }

  const started = Date.now()
  recorder.start(250)
  return {
    stream: canvasStream,
    stop: async () => {
      window.cancelAnimationFrame(raf)
      await waitRecorderStop(recorder)
      if (asrRecorder) await waitRecorderStop(asrRecorder)
      mic.getTracks().forEach((track) => track.stop())
      canvasStream.getTracks().forEach((track) => track.stop())
      if (camVideo) {
        camVideo.srcObject = null
        camVideo.remove()
      }
      const blob = new Blob(chunks, { type: recorder.mimeType || 'video/mp4' })
      const asrBlob = asrChunks.length
        ? new Blob(asrChunks, { type: asrRecorder?.mimeType || 'audio/webm' })
        : undefined
      return {
        blob,
        asrBlob,
        durationSec: Math.max(1, Math.round((Date.now() - started) / 1000)),
        score: 0,
      }
    },
  }
}
