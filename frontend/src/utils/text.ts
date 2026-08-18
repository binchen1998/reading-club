export type Box = { text: string; left: number; top: number; width: number; height: number; active?: boolean }

const WORD_RE = /[A-Za-z']+/g

function wordCount(text: string): number {
  return (text.match(WORD_RE) || []).length
}

export function mergeShortSegments(segments: string[], minWords = 3): string[] {
  const out: string[] = []
  let i = 0
  while (i < segments.length) {
    let cur = (segments[i] || '').trim()
    while (cur && wordCount(cur) < minWords && i + 1 < segments.length) {
      i += 1
      const next = (segments[i] || '').trim()
      cur = [cur, next].filter(Boolean).join(' ')
    }
    if (cur) out.push(cur)
    i += 1
  }
  return out
}

export function splitSentences(text: string): string[] {
  return (text || '')
    .split(/(?<=[。！？!?])\s*/)
    .map((s) => s.trim())
    .filter((s) => s.length > 1)
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
