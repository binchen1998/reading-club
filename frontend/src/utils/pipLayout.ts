export function computePipSize(
  vw = window.innerWidth,
  vh = window.innerHeight,
  aspectRatio = 4 / 3,
) {
  const ar = Number.isFinite(aspectRatio) && aspectRatio > 0.05 ? aspectRatio : 4 / 3
  const landscape = vw > vh
  let h: number
  if (landscape) {
    h = Math.round(vh * 0.16)
    h = Math.min(96, Math.max(64, h))
  } else {
    h = Math.round(vh * 0.12)
    h = Math.min(120, Math.max(72, h))
  }
  let w = Math.round(h * ar)
  const maxW = Math.round(vw * (landscape ? 0.16 : 0.26))
  if (w > maxW) {
    w = Math.max(72, maxW)
    h = Math.round(w / ar)
  }
  const margin = landscape && vh < 500 ? 8 : 12
  return { width: w, height: h, margin, aspectRatio: ar }
}
