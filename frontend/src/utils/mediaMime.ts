const MP4_VIDEO_CANDIDATES = [
  'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
  'video/mp4;codecs=avc1.4D401E,mp4a.40.2',
  'video/mp4;codecs=avc1,mp4a',
  'video/mp4',
]

const WEBM_VIDEO_CANDIDATES = [
  'video/webm;codecs=vp8,opus',
  'video/webm;codecs=vp9,opus',
  'video/webm',
]

export function isAppleWebKit(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  if (/iPhone|iPad|iPod/i.test(ua)) return true
  if ((navigator as Navigator & { maxTouchPoints?: number }).maxTouchPoints > 1 && /Macintosh/i.test(ua)) return true
  return /Safari/i.test(ua) && !/Chrome|Chromium|Edg|OPR|CriOS|FxiOS/i.test(ua)
}

function firstSupported(candidates: string[]): string | undefined {
  if (typeof MediaRecorder === 'undefined' || !MediaRecorder.isTypeSupported) return undefined
  for (const mime of candidates) {
    if (MediaRecorder.isTypeSupported(mime)) return mime
  }
  return undefined
}

export function pickVideoRecorderMime(): string | undefined {
  const mp4 = firstSupported(MP4_VIDEO_CANDIDATES)
  if (mp4) return mp4
  if (isAppleWebKit()) return undefined
  return firstSupported(WEBM_VIDEO_CANDIDATES)
}

const AUDIO_CANDIDATES = ['audio/mp4', 'audio/aac', 'audio/webm;codecs=opus', 'audio/webm']

export function pickAudioRecorderMime(): string | undefined {
  return firstSupported(AUDIO_CANDIDATES)
}

export function blobContainerMime(mimeOrType: string | undefined): string {
  const t = (mimeOrType || '').toLowerCase()
  if (t.includes('mp4') || t.includes('avc1') || t.includes('mp4a')) return 'video/mp4'
  if (t.includes('webm')) return 'video/webm'
  return t.split(';')[0] || 'video/mp4'
}

export function recordingFileExt(mimeOrType: string | undefined): string {
  return blobContainerMime(mimeOrType).includes('mp4') ? 'mp4' : 'webm'
}
