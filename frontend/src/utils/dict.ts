import { normalize } from './text'

export type DictItem = { en: string; zh: string }

const WORD_RE = /[A-Za-z]/
const PUNCT_ONLY_RE = /^[^\w]+$/
const localCache = new Map<string, string>()

export function isWordToken(token: string): boolean {
  return WORD_RE.test(token) && !PUNCT_ONLY_RE.test(token)
}

export function splitTokens(text: string): string[] {
  return (text || '')
    .replace(/([^\w\s])/g, ' $1 ')
    .replace(/\s+/g, ' ')
    .trim()
    .split(' ')
    .filter(Boolean)
}

export function cleanWord(token: string): string {
  return (token || '').replace(/^[^A-Za-z']+|[^A-Za-z']+$/g, '')
}

function stems(word: string): string[] {
  const lower = word.toLowerCase()
  const out = [lower]
  if (lower.endsWith("'s")) out.push(lower.slice(0, -2))
  if (lower.endsWith('ies') && lower.length > 4) out.push(`${lower.slice(0, -3)}y`)
  if (lower.endsWith('es') && lower.length > 3) out.push(lower.slice(0, -2))
  if (lower.endsWith('s') && !lower.endsWith('ss') && lower.length > 3) out.push(lower.slice(0, -1))
  if (lower.endsWith('ing') && lower.length > 5) {
    out.push(lower.slice(0, -3))
    out.push(`${lower.slice(0, -3)}e`)
  }
  if (lower.endsWith('ed') && lower.length > 4) {
    out.push(lower.slice(0, -2))
    out.push(`${lower.slice(0, -1)}`)
    out.push(`${lower.slice(0, -2)}e`)
  }
  return [...new Set(out)]
}

function lookupBanks(word: string, banks: DictItem[]): string {
  const keys = stems(word)
  for (const key of keys) {
    const hit = banks.find((item) => item.en.toLowerCase() === key)
    if (hit?.zh) return hit.zh
  }
  const phrase = banks.find((item) => {
    const parts = item.en.toLowerCase().split(/\s+/)
    return keys.some((key) => parts.includes(key))
  })
  return phrase?.zh || ''
}

export async function lookupWord(token: string, banks: DictItem[]): Promise<string> {
  const word = cleanWord(token)
  if (!word) return ''
  const cached = localCache.get(word.toLowerCase())
  if (cached) return cached
  const local = lookupBanks(word, banks)
  if (local) {
    localCache.set(word.toLowerCase(), local)
    return local
  }
  try {
    const res = await fetch(`/api/dict?word=${encodeURIComponent(word)}`)
    if (!res.ok) return ''
    const data = (await res.json()) as { zh?: string }
    const zh = (data.zh || '').trim()
    if (zh) localCache.set(word.toLowerCase(), zh)
    return zh
  } catch {
    return ''
  }
}

function splitParts(text: string): string[] {
  return (text || '')
    .split(/\n+|(?<=[.!?。！？])\s+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

export function matchTranslate(line: string, english: string, translate: string): string {
  const n = normalize(line)
  if (!translate) return ''
  if (!n) return translate
  const enParts = splitParts(english)
  const zhParts = splitParts(translate)
  let best = -1
  let bestScore = 0
  enParts.forEach((part, i) => {
    const pn = normalize(part)
    if (!pn) return
    if (pn.includes(n) || n.includes(pn)) {
      const score = Math.min(n.length, pn.length) / Math.max(n.length, pn.length)
      if (score > bestScore) {
        bestScore = score
        best = i
      }
    }
  })
  if (best >= 0 && zhParts[best]) return zhParts[best]
  return translate
}
