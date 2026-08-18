const PLAUSIBLE_EVENT_URL = 'https://plausible.coding61.com/api/event'
const PLAUSIBLE_ACTIVE_DOMAIN = 'OKmath-app'
const PLAUSIBLE_ACTIVE_NAME = 'english-reading-club'
const PLAUSIBLE_ACTIVE_CATEGORY = 'english-reading-club'

function resolvePhoneNumber(username: string): string {
  const phoneNumber = String(username || '').trim()
  if (!phoneNumber) {
    throw new Error('缺少手机号 phoneNumber，已阻止 plausible 埋点上报')
  }
  return phoneNumber
}

/** 上报首页活跃事件（对齐 new337）。 */
export async function reportHomeActive(username: string): Promise<void> {
  const phoneNumber = resolvePhoneNumber(username)
  const payload = {
    domain: PLAUSIBLE_ACTIVE_DOMAIN,
    name: PLAUSIBLE_ACTIVE_NAME,
    category: PLAUSIBLE_ACTIVE_CATEGORY,
    props: {
      user_id: phoneNumber,
    },
  }
  const res = await fetch(PLAUSIBLE_EVENT_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`plausible 上报失败: ${res.status}`)
  }
}

export function scheduleHomeActiveReport(username: string): void {
  window.setTimeout(() => {
    reportHomeActive(username).catch((err) => {
      console.error('[plausible] 上报首页活跃事件失败', err)
    })
  }, 0)
}
