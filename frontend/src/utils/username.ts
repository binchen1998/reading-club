import { getStoredRealname } from '../auth/resolveToken'

export const USERNAME_KEY = 'club-username'

export function readUsername(): string {
  const stored =
    localStorage.getItem(USERNAME_KEY) ||
    localStorage.getItem('club-user') ||
    localStorage.getItem('rc_username') ||
    ''
  return stored.trim().slice(0, 50)
}

export function writeUsername(raw: string): string {
  const name = (raw || '').trim().slice(0, 50)
  if (!name) return readUsername()
  localStorage.setItem(USERNAME_KEY, name)
  localStorage.setItem('club-user', name)
  localStorage.setItem('rc_username', name)
  return name
}

export function syncUsernameFromUrl(search = window.location.search): string {
  const params = new URLSearchParams(search)
  const q = params.get('username')
  if (q && q.trim()) return writeUsername(q)
  return readUsername()
}

export function urlUsername(search = window.location.search): string {
  return (new URLSearchParams(search).get('username') || '').trim()
}

export function clubLink(path: string, username = ''): string {
  const name = username || urlUsername() || readUsername()
  const [base, hash = ''] = path.split('#')
  const url = new URL(base, 'http://local.test')
  if (name) url.searchParams.set('username', name)
  const realname = getStoredRealname()
  if (realname) url.searchParams.set('realname', realname)
  return `${url.pathname}${url.search}${hash ? `#${hash}` : ''}`
}

export const withUsernameQuery = clubLink
