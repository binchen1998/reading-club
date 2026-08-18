import { apiGet, apiPost } from '../api'
import { beginGenerate, endGenerate } from '../stores/generate'

type TtsResult = { url?: string; exists?: boolean; created?: boolean; source?: string }
type OcrResult = { words?: Array<Record<string, unknown>>; exists?: boolean; created?: boolean; source?: string }

export async function ensureTts(text: string, purpose: string): Promise<string> {
  const value = (text || '').trim()
  if (!value) return ''
  const check = (await apiGet(
    `/api/assets/tts?text=${encodeURIComponent(value)}&check=1`,
  )) as TtsResult
  if (check?.exists && check.url) return check.url
  beginGenerate(purpose)
  try {
    const res = (await apiGet(
      `/api/assets/tts?text=${encodeURIComponent(value)}&purpose=${encodeURIComponent(purpose)}`,
    )) as TtsResult
    return res?.url || ''
  } finally {
    endGenerate()
  }
}

export async function ensureOcr(payload: {
  series_id: string
  book_slug: string
  page: number
  text: string
  purpose?: string
}): Promise<Array<Record<string, unknown>>> {
  const purpose = payload.purpose || '这一句的词框'
  const check = (await apiPost('/api/ocr/words', { ...payload, purpose, check: true })) as OcrResult
  if (check?.exists) return check.words || []
  beginGenerate(purpose)
  try {
    const res = (await apiPost('/api/ocr/words', { ...payload, purpose, check: false })) as OcrResult
    return res?.words || []
  } finally {
    endGenerate()
  }
}
