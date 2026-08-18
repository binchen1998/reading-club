export function isAvatarUrl(value: string | null | undefined): boolean {
  if (!value) return false
  return /^https?:\/\//i.test(value) || value.startsWith('/')
}
