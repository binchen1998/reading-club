import { api } from '../api'
import { qiniuUploadWithProgress } from './qiniu'
import type { PageClip } from './recordPage'

export type ReadingRecord = {
  id: number
  canCloud?: boolean
  isPublic?: boolean
  videoUrl?: string
}

function clipFile(clip: PageClip, id: number) {
  return new File([clip.blob], `reading-${id}.mp4`, {
    type: clip.blob.type || 'video/mp4',
  })
}

export async function saveReadingLocal(input: {
  clip: PageClip
  seriesId: string
  bookSlug: string
  bookTitle: string
  chapterId: string
  page: number
  onProgress?: (text: string) => void
}): Promise<ReadingRecord> {
  input.onProgress?.('正在保存到本地…')
  const prepared = (await api('/api/practice/prepare', {
    method: 'POST',
    body: JSON.stringify({
      series_id: input.seriesId,
      book_slug: input.bookSlug,
      book_title: input.bookTitle,
      chapter_id: input.chapterId,
      page: input.page,
      duration_sec: input.clip.durationSec,
      mime_type: input.clip.blob.type || 'video/mp4',
      is_public: false,
      storage: 'local',
    }),
  })) as ReadingRecord
  const body = new FormData()
  body.append('file', clipFile(input.clip, prepared.id))
  body.append('overall_score', String(input.clip.score || 0))
  return api(`/api/practice/${prepared.id}/local`, { method: 'POST', body }) as Promise<ReadingRecord>
}

export async function uploadReadingCloud(input: {
  id: number
  clip: PageClip
  isPublic?: boolean
  onProgress?: (text: string) => void
}): Promise<ReadingRecord> {
  input.onProgress?.('准备上传…')
  const prepared = (await api(`/api/practice/${input.id}/cloud-token`, {
    method: 'POST',
  })) as ReadingRecord & {
    video?: { token: string }
    video_key?: string
    upload_host?: string
  }
  if (!prepared.video?.token || !prepared.video_key) {
    throw new Error('无法获取上传凭证')
  }
  await qiniuUploadWithProgress(
    prepared.video.token,
    prepared.video_key,
    clipFile(input.clip, input.id),
    prepared.upload_host,
    (p) => input.onProgress?.(`正在上传 ${p}%`),
  )
  input.onProgress?.('正在保存…')
  return api(`/api/practice/${input.id}/cloud`, {
    method: 'POST',
    body: JSON.stringify({ video_key: prepared.video_key, is_public: Boolean(input.isPublic) }),
  }) as Promise<ReadingRecord>
}

export async function setReadingPublic(id: number, isPublic: boolean): Promise<ReadingRecord> {
  return api(`/api/practice/${id}/visibility`, {
    method: 'PATCH',
    body: JSON.stringify({ is_public: isPublic }),
  }) as Promise<ReadingRecord>
}
