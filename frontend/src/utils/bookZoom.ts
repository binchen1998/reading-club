const STORAGE_KEY = 'club-book-zoom'
export const MIN_BOOK_SCALE = 1
export const MAX_BOOK_SCALE = 3.5

export type BookZoomCache = { book: string; scale: number }

export function clampScale(scale: number) {
  return Math.min(MAX_BOOK_SCALE, Math.max(MIN_BOOK_SCALE, Math.round(scale * 100) / 100))
}

export function loadBookScale(bookKey: string) {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') as BookZoomCache | null
    if (!raw || raw.book !== bookKey) {
      if (raw) localStorage.removeItem(STORAGE_KEY)
      return 1
    }
    if (typeof raw.scale !== 'number' || Number.isNaN(raw.scale)) return 1
    return clampScale(raw.scale)
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return 1
  }
}

export function saveBookScale(bookKey: string, scale: number) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ book: bookKey, scale: clampScale(scale) }))
}

export function clearBookScale() {
  localStorage.removeItem(STORAGE_KEY)
}
