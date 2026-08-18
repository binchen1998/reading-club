const WHOAMI_BASE_URL =
  (import.meta as any).env.VITE_WHOAMI_BASE_URL || 'https://www.coding61.com/server/'

export const TOKEN_ERROR_KEY = 'club_token_error'
export const REALNAME_STORAGE_KEY = 'club-realname'

/** 将 URL 中的 ?token= 换成 ?username=（保留 realname） */
export async function resolveToken(urlParams: URLSearchParams): Promise<boolean> {
  const token = urlParams.get('token')
  if (!token) return false
  try {
    const res = await fetch(`${WHOAMI_BASE_URL}userinfo/whoami/`, {
      headers: { Authorization: `Token ${token}`, 'Content-Type': 'application/json' },
    })
    if (!res.ok) {
      sessionStorage.setItem(TOKEN_ERROR_KEY, '1')
      stripTokenFromUrl(urlParams)
      return false
    }
    const info = await res.json()
    const username = info.owner
    if (!username) {
      sessionStorage.setItem(TOKEN_ERROR_KEY, '1')
      stripTokenFromUrl(urlParams)
      return false
    }
    const newParams = new URLSearchParams(urlParams)
    newParams.delete('token')
    newParams.delete('nickname')
    newParams.set('username', username)
    const qs = newParams.toString()
    window.location.replace(`${window.location.pathname}${qs ? `?${qs}` : ''}${window.location.hash}`)
    return true
  } catch {
    sessionStorage.setItem(TOKEN_ERROR_KEY, '1')
    stripTokenFromUrl(urlParams)
    return false
  }
}

function stripTokenFromUrl(urlParams: URLSearchParams): void {
  if (!urlParams.has('token')) return
  urlParams.delete('token')
  urlParams.delete('nickname')
  const qs = urlParams.toString()
  window.history.replaceState(
    {},
    '',
    `${window.location.pathname}${qs ? `?${qs}` : ''}${window.location.hash}`,
  )
}

export function getStoredRealname(): string {
  try {
    return (localStorage.getItem(REALNAME_STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

export function storeRealname(raw: string): string {
  const name = (raw || '').trim().slice(0, 50)
  if (!name) return getStoredRealname()
  try {
    localStorage.setItem(REALNAME_STORAGE_KEY, name)
  } catch {
    /* ignore */
  }
  return name
}

export function syncRealnameFromUrl(search = window.location.search): string {
  const params = new URLSearchParams(search)
  const q = params.get('realname')
  if (q && q.trim()) return storeRealname(q)
  return getStoredRealname()
}
