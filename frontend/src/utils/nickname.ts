const PHONE_LIKE_RE = /^1\d{10}$/

export function hasCustomNickname(username: string, nickname?: string | null): boolean {
  const uname = (username || '').trim()
  const nick = (nickname || '').trim()
  if (!nick || nick === uname) return false
  if (nick.startsWith('888-')) return false
  if (PHONE_LIKE_RE.test(nick)) return false
  if (nick.startsWith('阅读同学') || nick.startsWith('袋鼠同学')) return false
  if (nick.startsWith('阅读达人_') || nick.startsWith('练习达人_')) return false
  if (nick.startsWith('阅读用户') || nick.startsWith('练习用户')) return false
  if (/^1\d{2}\*{4}\d{4}$/.test(nick)) return false
  if (/^888-\*{4}/.test(nick)) return false
  return true
}
