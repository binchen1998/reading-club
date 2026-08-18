import { username } from '../api'

type JobEvent<T = Record<string, unknown>> = {
  job_id?: string
  status?: string
  result?: T
  error?: string
}

export async function waitJobResult<T = Record<string, unknown>>(jobId: string): Promise<T> {
  const id = (jobId || '').trim()
  if (!id) throw new Error('缺少生成任务')
  const user = username()
  const headers = new Headers()
  if (user) headers.set('X-Username', encodeURIComponent(user))
  let res: Response
  try {
    res = await fetch(`/api/jobs/${id}/events`, { headers })
  } catch {
    throw new Error('等待生成失败')
  }
  if (!res.ok || !res.body) throw new Error('等待生成失败')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const chunks = buf.split('\n\n')
    buf = chunks.pop() || ''
    for (const chunk of chunks) {
      const event = parseSseData<T>(chunk)
      if (!event) continue
      if (event.status === 'done') return (event.result || {}) as T
      if (event.status === 'error') throw new Error(event.error || '生成失败')
    }
  }
  throw new Error('生成中断')
}

function parseSseData<T>(chunk: string): JobEvent<T> | null {
  const line = chunk
    .split('\n')
    .map((item) => item.trimEnd())
    .find((item) => item.startsWith('data:'))
  if (!line) return null
  try {
    return JSON.parse(line.slice(5).trim()) as JobEvent<T>
  } catch {
    return null
  }
}
