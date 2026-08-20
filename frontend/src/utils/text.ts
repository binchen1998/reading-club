export type Box = { text: string; left: number; top: number; width: number; height: number; active?: boolean }

const WORD_RE = /[A-Za-z']+/g
const ABBREV_RE = /(?:^|[\s"'“‘(\[])(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|U\.S|U\.K|a\.m|p\.m)\.$/i
const SENTENCE_END_RE = /[.!?。！？]["'”’)]*$/
const OPEN_QUOTE = /[“「『]/
const CLOSE_QUOTE = /[”」』]/
const TRAIL_CLOSE = /["”’」』)]/

function wordCount(text: string): number {
  return (text.match(WORD_RE) || []).length
}

function compact(text: string): string {
  return (text || '').replace(/\s+/g, ' ').trim()
}

function isAbbrev(text: string): boolean {
  return ABBREV_RE.test((text || '').trim())
}

export function endsWithSentencePunct(text: string): boolean {
  const value = (text || '').trim()
  if (!value || isAbbrev(value)) return false
  return SENTENCE_END_RE.test(value)
}

export function startsWithLowercase(text: string): boolean {
  const value = (text || '').trim().replace(/^["'“‘(\[]+/, '')
  return /^[a-z]/.test(value)
}

function shouldMergeNext(cur: string, next: string, minWords: number): boolean {
  if (!next) return true
  if (startsWithLowercase(next)) return true
  if (/^[”’」』]/.test(next.trim())) return true
  if (!endsWithSentencePunct(cur)) return true
  const words = wordCount(cur)
  if (!words) return false
  return words === 1 && words < minWords
}

export function mergeShortSegments(segments: string[], minWords = 3): string[] {
  const items = (segments || []).map((item) => compact(item)).filter(Boolean)
  const out: string[] = []
  let i = 0
  while (i < items.length) {
    let cur = items[i]
    while (i + 1 < items.length && shouldMergeNext(cur, items[i + 1], minWords)) {
      i += 1
      cur = compact(`${cur} ${items[i]}`)
    }
    if (cur) out.push(cur)
    i += 1
  }
  return out
}

function glueSentenceParts(parts: string[]): string[] {
  return mergeShortSegments(parts, 1)
}

export function splitSentences(text: string): string[] {
  const src = String(text || '').replace(/\r\n?/g, '\n')
  const raw: string[] = []
  let buf = ''
  let asciiDbl = false
  let curly = 0

  const inQuote = () => asciiDbl || curly > 0

  const applyQuote = (ch: string) => {
    if (ch === '"') asciiDbl = !asciiDbl
    else if (OPEN_QUOTE.test(ch)) curly += 1
    else if (CLOSE_QUOTE.test(ch)) curly = Math.max(0, curly - 1)
  }

  const pushBuf = () => {
    const piece = compact(buf)
    buf = ''
    if (piece) raw.push(piece)
  }

  for (let i = 0; i < src.length; i += 1) {
    const ch = src[i]
    if (ch === '\n') {
      if (!inQuote() && endsWithSentencePunct(buf)) pushBuf()
      else if (buf && !buf.endsWith(' ')) buf += ' '
      continue
    }

    applyQuote(ch)
    buf += ch

    const chineseEnd = ch === '。' || ch === '！' || ch === '？'
    const englishEnd = (ch === '.' || ch === '!' || ch === '?') && !inQuote() && !isAbbrev(buf)
    if (!chineseEnd && !englishEnd) continue

    while (i + 1 < src.length && TRAIL_CLOSE.test(src[i + 1])) {
      i += 1
      applyQuote(src[i])
      buf += src[i]
    }
    const next = src[i + 1]
    if (chineseEnd || next === undefined || /\s/.test(next)) pushBuf()
  }
  pushBuf()
  return glueSentenceParts(raw)
}

export function normalize(text: string): string {
  return (text || '')
    .toLowerCase()
    .replace(/[“”"'\-–,.;:!?()]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function needlesOf(sentence: string, words: { en: string }[], phrases: { en: string }[]): string[] {
  const found: string[] = []
  const quote = /[“"']([^”"']{2,})[”"']/g
  let match: RegExpExecArray | null
  while ((match = quote.exec(sentence))) found.push(match[1])
  const latin = sentence.match(/[A-Za-z][A-Za-z0-9' ,.-]{1,}/g) || []
  for (const chunk of latin) {
    const clean = chunk.replace(/[.,]+$/g, '').trim()
    if (clean.length >= 3) found.push(clean)
  }
  for (const item of [...phrases, ...words]) {
    if (sentence.toLowerCase().includes(item.en.toLowerCase())) found.push(item.en)
  }
  return [...new Set(found)]
}

export function inflateBox(box: Box, padX = 0.45, padY = 0.4): Box {
  return {
    ...box,
    left: Math.max(0, box.left - padX),
    top: Math.max(0, box.top - padY),
    width: box.width + padX * 2,
    height: box.height + padY * 2,
  }
}

export function boxesFor(needles: string[], ocr: Box[]): Box[] {
  if (!needles.length || !ocr?.length) return []
  const keys = needles.map(normalize).filter(Boolean)
  return ocr.filter((region) => {
    const text = normalize(region.text)
    return keys.some((key) => text.includes(key) || key.includes(text))
  })
}

export function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}
