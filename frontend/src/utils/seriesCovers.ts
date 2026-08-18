export const SERIES_COVERS_JSON_URL =
  (import.meta.env.VITE_SERIES_COVERS_JSON_URL as string | undefined)?.trim() ||
  'https://static1.cxy61.com/reading-club/assets/covers.json'

export type SeriesCover = {
  id: string
  title?: string
  cover: string
}

export async function loadSeriesCovers(): Promise<Record<string, string>> {
  const res = await fetch(SERIES_COVERS_JSON_URL, { cache: 'no-cache' })
  if (!res.ok) throw new Error(`封面清单读取失败: ${res.status}`)
  const data = await res.json()
  const rows = Array.isArray(data?.series) ? data.series : []
  const map: Record<string, string> = {}
  for (const row of rows as SeriesCover[]) {
    if (row?.id && row.cover) map[row.id] = row.cover
  }
  return map
}
