const QINIU_UPLOAD_TIMEOUT_MS = 120_000

export function qiniuUploadWithProgress(
  token: string,
  key: string,
  file: Blob,
  uploadHost = 'https://up-z0.qiniup.com',
  onProgress?: (percent: number) => void,
  timeoutMs = QINIU_UPLOAD_TIMEOUT_MS,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('token', token)
    form.append('key', key)
    form.append('file', file)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', uploadHost)
    xhr.timeout = timeoutMs
    xhr.upload.onprogress = (ev) => {
      if (!ev.lengthComputable || !onProgress) return
      onProgress(Math.min(100, Math.round((ev.loaded / ev.total) * 100)))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText)
          resolve(data.key || key)
        } catch {
          resolve(key)
        }
        return
      }
      reject(new Error((xhr.responseText || '七牛上传失败').slice(0, 200)))
    }
    xhr.onerror = () => reject(new Error('七牛上传网络错误'))
    xhr.ontimeout = () => reject(new Error('七牛上传超时，请稍后重试'))
    xhr.send(form)
  })
}
