import { ref, shallowRef } from 'vue'

/** 朗读页共享摄像头：预览 PiP 与成片叠画共用同一路视频轨。 */
const enabled = ref(false)
const starting = ref(false)
const stream = shallowRef<MediaStream | null>(null)
const error = ref('')
type PipPos = { left: number; top: number }

/** 固定定位：null 表示尚未落到屏幕上 */
const pos = ref<PipPos | null>(null)
/** 当前书内拖动缓存；换书后失效 */
let boundBookKey = ''
let cachedPos: PipPos | null = null

/** 用于取消尚未完成的 getUserMedia（离开页面时） */
let startEpoch = 0

function mediaErrorMessage(err: unknown, fallback: string) {
  const name = err && typeof err === 'object' && 'name' in err ? String((err as { name?: string }).name) : ''
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') return '没有摄像头权限，可继续用头像合成'
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') return '没找到摄像头，将用头像合成'
  if (name === 'NotReadableError') return '摄像头正被占用，将用头像合成'
  if (err instanceof Error && err.message) return err.message
  return fallback
}

export function useUserCamera() {
  async function start() {
    if (stream.value) {
      enabled.value = true
      error.value = ''
      return true
    }
    if (starting.value) return false
    starting.value = true
    error.value = ''
    const epoch = ++startEpoch
    try {
      const s = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: 'user',
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
      })
      if (epoch !== startEpoch) {
        s.getTracks().forEach((t) => t.stop())
        return false
      }
      stream.value = s
      enabled.value = true
      return true
    } catch (e) {
      if (epoch === startEpoch) {
        error.value = mediaErrorMessage(e, '无法访问摄像头，将用头像合成')
        enabled.value = false
        stream.value = null
      }
      return false
    } finally {
      if (epoch === startEpoch) starting.value = false
    }
  }

  function stop() {
    startEpoch += 1
    starting.value = false
    stream.value?.getTracks().forEach((t) => t.stop())
    stream.value = null
    enabled.value = false
    pos.value = null
  }

  function close() {
    stop()
  }

  function bindBook(bookKey: string) {
    const key = bookKey.trim()
    if (key === boundBookKey) return
    boundBookKey = key
    cachedPos = null
    pos.value = null
  }

  function setPos(left: number, top: number, remember = false) {
    const next = { left, top }
    pos.value = next
    if (remember && boundBookKey) cachedPos = next
  }

  function resetPos() {
    pos.value = null
  }

  function takeCachedPos(): PipPos | null {
    return cachedPos ? { ...cachedPos } : null
  }

  function liveVideoTrack(): MediaStreamTrack | null {
    if (!enabled.value || !stream.value) return null
    const track = stream.value.getVideoTracks()[0]
    if (!track || track.readyState !== 'live') return null
    return track
  }

  return {
    enabled,
    starting,
    stream,
    error,
    pos,
    start,
    stop,
    close,
    bindBook,
    setPos,
    resetPos,
    takeCachedPos,
    liveVideoTrack,
  }
}
