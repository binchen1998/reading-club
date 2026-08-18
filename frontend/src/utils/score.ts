const WORD_RE = /[A-Za-z']+/g

const CONTRACTIONS: Record<string, string[]> = {
  "i'm": ['i', 'am'],
  "you're": ['you', 'are'],
  "we're": ['we', 'are'],
  "they're": ['they', 'are'],
  "he's": ['he', 'is'],
  "she's": ['she', 'is'],
  "it's": ['it', 'is'],
  "that's": ['that', 'is'],
  "what's": ['what', 'is'],
  "who's": ['who', 'is'],
  "there's": ['there', 'is'],
  "here's": ['here', 'is'],
  "don't": ['do', 'not'],
  "doesn't": ['does', 'not'],
  "didn't": ['did', 'not'],
  "can't": ['can', 'not'],
  "won't": ['will', 'not'],
  "isn't": ['is', 'not'],
  "aren't": ['are', 'not'],
  "wasn't": ['was', 'not'],
  "weren't": ['were', 'not'],
  "haven't": ['have', 'not'],
  "hasn't": ['has', 'not'],
  "hadn't": ['had', 'not'],
  "let's": ['let', 'us'],
  "i've": ['i', 'have'],
  "you've": ['you', 'have'],
  "we've": ['we', 'have'],
  "they've": ['they', 'have'],
  "i'll": ['i', 'will'],
  "you'll": ['you', 'will'],
  "we'll": ['we', 'will'],
  "they'll": ['they', 'will'],
}

function words(text: string): string[] {
  const raw = text.match(WORD_RE) || []
  const out: string[] = []
  for (const item of raw) {
    const lower = item.toLowerCase()
    const expanded = CONTRACTIONS[lower]
    if (expanded) out.push(...expanded)
    else out.push(lower)
  }
  return out
}

function ratio(a: string, b: string): number {
  if (a === b) return 1
  const len = Math.max(a.length, b.length)
  if (!len) return 1
  let hits = 0
  for (let i = 0; i < Math.min(a.length, b.length); i += 1) {
    if (a[i] === b[i]) hits += 1
  }
  return hits / len
}

function similar(a: string, b: string): boolean {
  return ratio(a, b) >= 0.8
}

function lcs(ref: string[], hyp: string[]): number {
  const n = ref.length
  const m = hyp.length
  const prev = new Array(m + 1).fill(0)
  const curr = new Array(m + 1).fill(0)
  for (let i = 1; i <= n; i += 1) {
    for (let j = 1; j <= m; j += 1) {
      curr[j] = similar(ref[i - 1], hyp[j - 1]) ? prev[j - 1] + 1 : Math.max(prev[j], curr[j - 1])
    }
    for (let j = 0; j <= m; j += 1) prev[j] = curr[j]
  }
  return prev[m]
}

export function scoreEnglish(refText: string, heard: string): { score: number; heard: string } {
  const ref = words(refText)
  const hyp = words(heard)
  if (!ref.length || !hyp.length) return { score: 0, heard }
  const ok = lcs(ref, hyp)
  return { score: Math.round((ok / ref.length) * 100), heard }
}
