import { ADMIN_TOKEN_KEY } from '../api'

export type WorkerJob = {
  job_id?: string
  kind?: string
  key?: string
  status?: string
  preview?: string
}

export type WorkerStatus = {
  background?: {
    queued?: string[]
    active?: string[]
    queued_count?: number
    active_count?: number
  }
  interactive?: WorkerJob[]
}

export type WorkerLogLine = {
  id?: number
  iso?: string
  level?: string
  logger?: string
  message?: string
}

export type WorkerEvent = {
  type?: string
  status?: WorkerStatus
  logs?: WorkerLogLine[]
  line?: WorkerLogLine
}

export function parseSseChunk(chunk: string): WorkerEvent | null {
  const line = chunk
    .split('\n')
    .map((item) => item.trimEnd())
    .find((item) => item.startsWith('data:'))
  if (!line) return null
  try {
    return JSON.parse(line.slice(5).trim()) as WorkerEvent
  } catch {
    return null
  }
}

export async function streamAdminWorkerLogs(
  onEvent: (event: WorkerEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY) || ''
  const headers = new Headers()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch('/api/admin/worker/events', { headers, signal })
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '')
    throw new Error(text || '无法连接 worker 日志')
  }
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
      const event = parseSseChunk(chunk)
      if (event) onEvent(event)
    }
  }
}
