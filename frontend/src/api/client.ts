export async function api(path: string, init: RequestInit = {}) {
  const username = localStorage.getItem('rc_username') || 'guest'
  const headers = new Headers(init.headers || {})
  headers.set('X-Username', username)
  if (init.body && !headers.has('Content-Type') && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(path, { ...init, headers })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  const type = res.headers.get('content-type') || ''
  if (type.includes('application/json')) return res.json()
  return res
}
