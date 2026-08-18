export function computePipSize(
  vw = window.innerWidth,
  vh = window.innerHeight,
  aspectRatio = 4 / 3,
) {
  const ar = Number.isFinite(aspectRatio) && aspectRatio > 0.05 ? aspectRatio : 4 / 3
  const landscape = vw > vh
  let h: number
  if (landscape) {
    h = Math.round(vh * 0.28)
    h = Math.min(150, Math.max(88, h))
  } else {
    h = Math.round(vh * 0.2)
    h = Math.min(240, Math.max(120, h))
  }
  let w = Math.round(h * ar)
  const maxW = Math.round(vw * (landscape ? 0.26 : 0.42))
  if (w > maxW) {
    w = Math.max(96, maxW)
    h = Math.round(w / ar)
  }
  const margin = landscape && vh < 500 ? 8 : 12
  return { width: w, height: h, margin, aspectRatio: ar }
}
