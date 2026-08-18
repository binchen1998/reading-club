import { hasCustomNickname } from './nickname'

const PHONE_LIKE_RE = /^1\d{10}$/
const MASKED_PHONE_RE = /^1\d{2}\*{4}\d{4}$/
const MASKED_GUEST_RE = /^888-\*{4}\d{0,8}$/
const ANON_PREFIX = '阅读同学'

export function maskPhone(value: string): string {
  const s = (value || '').trim()
  if (!PHONE_LIKE_RE.test(s)) return s
  return `${s.slice(0, 3)}****${s.slice(-4)}`
}

export function maskGuestId(value: string): string {
  const s = (value || '').trim()
  if (!s.startsWith('888-')) return s
  const rest = s.slice(4)
  if (rest.length <= 4) return '888-****'
  return `888-****${rest.slice(-4)}`
}

export function maskSensitiveId(value?: string | null): string | null {
  const s = (value || '').trim()
  if (!s) return null
  if (MASKED_PHONE_RE.test(s) || MASKED_GUEST_RE.test(s)) return s
  if (PHONE_LIKE_RE.test(s)) return maskPhone(s)
  if (s.startsWith('888-')) return maskGuestId(s)
  return null
}

export function anonymousDisplayName(username = ''): string {
  const masked = maskSensitiveId(username)
  if (masked) return masked
  return ANON_PREFIX
}

export function safeDisplayName(name?: string | null, username?: string | null): string {
  const nick = (name || '').trim()
  const uname = (username || '').trim()
  const nickMasked = maskSensitiveId(nick)
  if (nickMasked) return nickMasked
  if (uname && hasCustomNickname(uname, nick)) return nick
  if (!uname && nick && !maskSensitiveId(nick) && !nick.startsWith(ANON_PREFIX)) return nick
  return anonymousDisplayName(uname)
}
