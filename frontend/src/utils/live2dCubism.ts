type CubismWindow = Window & {
  Live2DCubismCore?: unknown
}

let loading: Promise<void> | null = null

function publicAsset(path: string) {
  return `/${path.replace(/^\//, '')}`
}

function hasCubismCore() {
  return !!(window as CubismWindow).Live2DCubismCore
}

export function ensureCubismCore(): Promise<void> {
  if (hasCubismCore()) return Promise.resolve()
  if (loading) return loading

  loading = new Promise<void>((resolve, reject) => {
    const finishOk = () => {
      if (hasCubismCore()) resolve()
      else reject(new Error('Cubism Core 未正确初始化'))
    }

    const existing = document.querySelector<HTMLScriptElement>('script[data-cubism-core]')
    if (existing) {
      if (hasCubismCore()) {
        resolve()
        return
      }
      existing.addEventListener('load', finishOk, { once: true })
      existing.addEventListener(
        'error',
        () => reject(new Error('Cubism Core 加载失败')),
        { once: true },
      )
      return
    }

    const script = document.createElement('script')
    script.src = publicAsset('live2d/cubism/live2dcubismcore.min.js')
    script.async = false
    script.dataset.cubismCore = '1'
    script.onload = finishOk
    script.onerror = () => reject(new Error(`Cubism Core 加载失败: ${script.src}`))
    document.head.appendChild(script)
  }).catch((err) => {
    loading = null
    throw err
  })

  return loading
}
