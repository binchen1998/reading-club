/** 居中裁成正方形后缩放到不超过 maxSize（默认 200）。 */
export async function resizeImageToMax(file: Blob, maxSize = 200): Promise<Blob> {
  const bitmap = await createImageBitmap(file)
  try {
    const side = Math.min(bitmap.width, bitmap.height)
    const sx = (bitmap.width - side) / 2
    const sy = (bitmap.height - side) / 2
    const out = Math.max(1, Math.min(maxSize, side))
    const canvas = document.createElement('canvas')
    canvas.width = out
    canvas.height = out
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('无法处理图片')
    ctx.drawImage(bitmap, sx, sy, side, side, 0, 0, out, out)
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error('图片压缩失败'))),
        'image/jpeg',
        0.9,
      )
    })
  } finally {
    bitmap.close()
  }
}
