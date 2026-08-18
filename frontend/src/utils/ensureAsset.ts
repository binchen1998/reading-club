import { apiGet, apiPost } from '../api'
import { beginGenerate, endGenerate, waitGenerateShown } from '../stores/generate'
import { waitJobResult } from './jobSse'

type TtsResult = { url?: string; exists?: boolean; created?: boolean; source?: string }
type OcrResult = { words?: Array<Record<string, unknown>>; exists?: boolean; created?: boolean; source?: string }
type OcrPayload = {
  series_id: string
  book_slug: string
  page: number
  text: string
  purpose?: string
}
type EnsureOpts = { silent?: boolean }

type AssetJob<T> = {
  promise: Promise<T>
  checked: Promise<void>
  needsGenerate: boolean
  done: boolean
  releaseGenerate: () => void
}

const TTS_PREFETCH_CONCURRENCY = 4
const ttsCache = new Map<string, string>()
const ttsJobs = new Map<string, AssetJob<string>>()
const ocrCache = new Map<string, Array<Record<string, unknown>>>()
const ocrJobs = new Map<string, AssetJob<Array<Record<string, unknown>>>>()

function uniqueTexts(texts: string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const raw of texts) {
    const text = (raw || '').trim()
    if (!text || seen.has(text)) continue
    seen.add(text)
    out.push(text)
  }
  return out
}

function ocrCacheKey(payload: OcrPayload): string {
  return `${payload.series_id}/${payload.book_slug}/${payload.page}:${(payload.text || '').trim()}`
}

async function waitForAsset<T>(
  job: AssetJob<T>,
  purpose: string,
  silent?: boolean,
  fallback?: T,
): Promise<T> {
  if (silent) {
    job.releaseGenerate()
    try {
      return await job.promise
    } catch {
      return fallback as T
    }
  }
  await job.checked
  if (job.done || !job.needsGenerate) {
    job.releaseGenerate()
    try {
      return await job.promise
    } catch {
      return fallback as T
    }
  }
  beginGenerate(purpose)
  await waitGenerateShown()
  job.releaseGenerate()
  try {
    return await job.promise
  } finally {
    endGenerate()
  }
}

function startJob<T>(
  run: (job: AssetJob<T>, markChecked: () => void, waitGenerate: () => Promise<void>) => Promise<T>,
): AssetJob<T> {
  let settled = false
  let resolveChecked: () => void = () => undefined
  let resolveGenerate: () => void = () => undefined
  const generateGate = new Promise<void>((resolve) => {
    resolveGenerate = resolve
  })
  const job: AssetJob<T> = {
    promise: Promise.resolve() as Promise<T>,
    checked: new Promise<void>((resolve) => {
      resolveChecked = resolve
    }),
    needsGenerate: false,
    done: false,
    releaseGenerate: resolveGenerate,
  }
  const markChecked = () => {
    if (settled) return
    settled = true
    resolveChecked()
  }
  job.promise = (async () => {
    try {
      return await run(job, markChecked, () => generateGate)
    } finally {
      job.done = true
      markChecked()
      resolveGenerate()
    }
  })()
  return job
}

async function runPool<T>(items: T[], limit: number, fn: (item: T) => Promise<unknown>) {
  let index = 0
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (index < items.length) {
      const current = items[index]
      index += 1
      await fn(current)
    }
  })
  await Promise.all(workers)
}

function startTtsJob(value: string, purpose: string): AssetJob<string> {
  const existing = ttsJobs.get(value)
  if (existing) return existing
  const job = startJob<string>(async (state, markChecked, waitGenerate) => {
    const cached = ttsCache.get(value)
    if (cached) return cached
    const check = (await apiGet(
      `/api/assets/tts?text=${encodeURIComponent(value)}&check=1`,
    )) as TtsResult
    if (check?.exists && check.url) {
      ttsCache.set(value, check.url)
      return check.url
    }
    state.needsGenerate = true
    markChecked()
    await waitGenerate()
    const started = (await apiPost('/api/assets/tts/generate', { text: value, purpose })) as {
      exists?: boolean
      status?: string
      job_id?: string
      url?: string
      result?: TtsResult
    }
    const ready = started?.result?.url || started?.url || ''
    if (ready && (started.exists || started.status === 'done' || !started.job_id)) {
      ttsCache.set(value, ready)
      return ready
    }
    let res: TtsResult
    try {
      res = await waitJobResult<TtsResult>(started.job_id || '')
    } catch {
      return ''
    }
    const url = res?.url || ''
    if (url) ttsCache.set(value, url)
    return url
  })
  job.promise.finally(() => {
    if (ttsJobs.get(value) === job) ttsJobs.delete(value)
  })
  ttsJobs.set(value, job)
  return job
}

function startOcrJob(payload: OcrPayload): AssetJob<Array<Record<string, unknown>>> {
  const key = ocrCacheKey(payload)
  const existing = ocrJobs.get(key)
  if (existing) return existing
  const purpose = payload.purpose || '这一句的词框'
  const job = startJob<Array<Record<string, unknown>>>(async (state, markChecked, waitGenerate) => {
    const cached = ocrCache.get(key)
    if (cached) return cached
    const check = (await apiPost('/api/ocr/words', { ...payload, purpose, check: true })) as OcrResult
    if (check?.exists) {
      const words = check.words || []
      ocrCache.set(key, words)
      return words
    }
    state.needsGenerate = true
    markChecked()
    await waitGenerate()
    const started = (await apiPost('/api/ocr/words/generate', { ...payload, purpose })) as {
      exists?: boolean
      status?: string
      job_id?: string
      words?: Array<Record<string, unknown>>
      result?: OcrResult
    }
    const ready = started?.result?.words || started?.words
    if (ready && (started.exists || started.status === 'done' || !started.job_id)) {
      ocrCache.set(key, ready)
      return ready
    }
    let res: OcrResult
    try {
      res = await waitJobResult<OcrResult>(started.job_id || '')
    } catch {
      return []
    }
    const words = res?.words || []
    ocrCache.set(key, words)
    return words
  })
  job.promise.finally(() => {
    if (ocrJobs.get(key) === job) ocrJobs.delete(key)
  })
  ocrJobs.set(key, job)
  return job
}

export function hasCachedTts(text: string): boolean {
  const value = (text || '').trim()
  return !!value && ttsCache.has(value)
}

export async function ensureTts(text: string, purpose: string, opts?: EnsureOpts): Promise<string> {
  const value = (text || '').trim()
  if (!value) return ''
  const cached = ttsCache.get(value)
  if (cached) return cached
  return waitForAsset(startTtsJob(value, purpose), purpose, opts?.silent, '')
}

export async function ensureOcr(
  payload: OcrPayload,
  opts?: EnsureOpts,
): Promise<Array<Record<string, unknown>>> {
  const text = (payload.text || '').trim()
  if (!text) return []
  const key = ocrCacheKey({ ...payload, text })
  const cached = ocrCache.get(key)
  if (cached) return cached
  return waitForAsset(startOcrJob({ ...payload, text }), payload.purpose || '这一句的词框', opts?.silent, [])
}

export function prefetchPageAssets(input: {
  texts: string[]
  ocrItems: Array<Omit<OcrPayload, 'purpose'>>
}) {
  const texts = uniqueTexts(input.texts)
  void runPool(texts, TTS_PREFETCH_CONCURRENCY, (text) =>
    ensureTts(text, '讲解音频', { silent: true }),
  ).catch(() => undefined)
  const ocrItems = input.ocrItems.filter((item) => (item.text || '').trim() && item.page)
  void (async () => {
    for (const item of ocrItems) {
      try {
        await ensureOcr({ ...item, purpose: '这一句的词框' }, { silent: true })
      } catch {
        /* 预取词框失败不影响阅读 */
      }
    }
  })()
}
