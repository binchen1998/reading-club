let skewMs = 0

export function syncServerTime(iso?: string) {
  if (!iso) return
  const server = Date.parse(iso)
  if (!Number.isFinite(server)) return
  skewMs = server - Date.now()
}

export function serverNow(): Date {
  return new Date(Date.now() + skewMs)
}

export function serverTodayIso(): string {
  return serverNow().toLocaleDateString('en-CA', { timeZone: 'Asia/Shanghai' })
}
