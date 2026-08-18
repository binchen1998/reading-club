export function isGuestUsername(username: string): boolean {
  const u = (username || '').trim()
  return !!u && u.startsWith('888-')
}

export const GUEST_OPEN_PROMPT_MESSAGE = '游客账号无法上传朗读或参与互动，请切换到真实账号登录。'
