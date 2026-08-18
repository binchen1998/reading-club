import { readUsername } from './utils/username'

export function username() {
  return readUsername()
}

export async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  const user = username()
  if (user) headers.set('X-Username', encodeURIComponent(user))
  if (init.body && !headers.has('Content-Type') && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(path, { ...init, headers })
  if (!res.ok) {
    const text = await res.text()
    let message = text || res.statusText
    try {
      const data = JSON.parse(text)
      const detail = data.detail ?? data.message
      message = Array.isArray(detail) ? detail.map((item: any) => item.msg || item).join('；') : String(detail || message)
    } catch {
      /* keep text */
    }
    throw new Error(message)
  }
  const type = res.headers.get('content-type') || ''
  if (type.includes('application/json')) return res.json()
  return res
}

export const apiGet = (path: string) => api(path)
export const apiPost = (path: string, body?: unknown) =>
  api(path, { method: 'POST', body: body == null ? undefined : JSON.stringify(body) })
export const apiDelete = (path: string) => api(path, { method: 'DELETE' })

export const ADMIN_TOKEN_KEY = 'club_admin_token'

export async function adminApi(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  const token = localStorage.getItem(ADMIN_TOKEN_KEY) || ''
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !headers.has('Content-Type') && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(path, { ...init, headers })
  if (!res.ok) {
    const text = await res.text()
    let message = text || res.statusText
    try {
      const data = JSON.parse(text)
      message = data.detail || data.message || message
    } catch {
      /* keep text */
    }
    throw new Error(message)
  }
  const type = res.headers.get('content-type') || ''
  if (type.includes('application/json')) return res.json()
  return res
}
