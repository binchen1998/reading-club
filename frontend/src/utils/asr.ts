const DEFAULT_PARAFORMER_BASE = 'https://paraformer.coding61.com'
const POLL_INTERVAL_MS = 500
const MAX_WAIT_MS = 120_000
const REQUEST_TIMEOUT_MS = 30_000

function paraformerBase(): string {
  return (import.meta.env.VITE_PARAFORMER_URL || DEFAULT_PARAFORMER_BASE).replace(/\/+$/, '')
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function createTimeoutSignal(ms: number) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), ms)
  return {
    signal: controller.signal,
    clear: () => window.clearTimeout(timer),
  }
}

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
  const { signal, clear } = createTimeoutSignal(timeoutMs)
  try {
    return await fetch(input, { ...init, signal })
  } finally {
    clear()
  }
}

function wordsFromTimestamp(result: unknown): string {
  if (!result || typeof result !== 'object') return ''
  const ts = (result as Record<string, unknown>).timestamp
  if (!Array.isArray(ts)) return ''
  return ts
    .map((item) => {
      if (typeof item === 'string') return item
      if (Array.isArray(item) && typeof item[0] === 'string') return item[0]
      if (item && typeof item === 'object' && 'text' in item) return String((item as { text?: string }).text || '')
      return ''
    })
    .filter(Boolean)
    .join(' ')
}

function extractRecognizedText(result: unknown): string {
  if (result == null) return ''
  if (typeof result === 'string') {
    const trimmed = result.trim()
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try {
        return extractRecognizedText(JSON.parse(trimmed))
      } catch {
        return trimmed
      }
    }
    return trimmed
  }
  if (Array.isArray(result)) {
    return result.map((item) => extractRecognizedText(item)).filter(Boolean).join(' ')
  }
  if (typeof result === 'object') {
    const obj = result as Record<string, unknown>
    for (const key of ['text', 'result', 'sentence']) {
      if (!(key in obj)) continue
      const text = extractRecognizedText(obj[key]).trim()
      if (text) return text
    }
    return wordsFromTimestamp(obj)
  }
  return String(result)
}

async function pollAsrResult(jobId: string): Promise<string> {
  const base = paraformerBase()
  const deadline = Date.now() + MAX_WAIT_MS
  while (Date.now() < deadline) {
    try {
      const response = await fetchWithTimeout(`${base}/asr/result/${jobId}`)
      if (!response.ok) throw new Error(`语音识别查询失败: HTTP ${response.status}`)
      const payload = await response.json()
      const status = String(payload.status || '')
      if (status === 'completed') return extractRecognizedText(payload.result ?? {}).trim()
      if (status === 'failed' || status === 'error') throw new Error(payload.error || '语音识别失败')
    } catch (err) {
      if (err instanceof Error && /语音识别失败|查询失败/.test(err.message)) throw err
    }
    await sleep(POLL_INTERVAL_MS)
  }
  throw new Error('语音识别超时')
}

export async function recognizeAudio(blob: Blob, lang: 'zh' | 'en' = 'en'): Promise<string> {
  if (blob.size < 1000) throw new Error('音频太短，请重新录制')
  const base = paraformerBase()
  let lastError: Error | null = null
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const body = new FormData()
      body.append('file', blob, 'recording.webm')
      body.append('lang', lang)
      const response = await fetchWithTimeout(`${base}/asr`, { method: 'POST', body })
      if (!response.ok) throw new Error(`语音识别提交失败: HTTP ${response.status}`)
      const job = await response.json()
      if (!job?.job_id) throw new Error('语音识别服务未返回 job_id')
      return await pollAsrResult(String(job.job_id))
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err))
      if (attempt < 2) await sleep(400)
    }
  }
  throw lastError || new Error('语音识别服务不可用')
}
