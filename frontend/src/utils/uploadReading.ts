import { api } from '../api'
import { qiniuUploadWithProgress } from './qiniu'
import type { PageClip } from './recordPage'

export async function uploadReading(input: {
  clip: PageClip
  seriesId: string
  bookSlug: string
  bookTitle: string
  chapterId: string
  page: number
  onProgress?: (text: string) => void
}) {
  input.onProgress?.('准备上传…')
  const prepared = await api('/api/practice/prepare', {
    method: 'POST',
    body: JSON.stringify({
      series_id: input.seriesId,
      book_slug: input.bookSlug,
      book_title: input.bookTitle,
      chapter_id: input.chapterId,
      page: input.page,
      duration_sec: input.clip.durationSec,
      mime_type: input.clip.blob.type || 'video/mp4',
      is_public: true,
    }),
  })
  const file = new File([input.clip.blob], `reading-${prepared.id}.mp4`, {
    type: input.clip.blob.type || 'video/mp4',
  })
  if (prepared.mode === 'local') {
    input.onProgress?.('正在保存录音…')
    const body = new FormData()
    body.append('file', file)
    return api(`/api/practice/${prepared.id}/local`, { method: 'POST', body })
  }
  input.onProgress?.('正在上传七牛…')
  await qiniuUploadWithProgress(
    prepared.video.token,
    prepared.video_key,
    file,
    prepared.upload_host,
    (p) => input.onProgress?.(`正在上传 ${p}%`),
  )
  input.onProgress?.('正在保存…')
  return api(`/api/practice/${prepared.id}/complete`, {
    method: 'POST',
    body: JSON.stringify({
      video_key: prepared.video_key,
      duration_sec: input.clip.durationSec,
      overall_score: input.clip.score,
      is_public: true,
    }),
  })
}
