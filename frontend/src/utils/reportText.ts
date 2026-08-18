export function quizReportText(done: boolean, retries?: number) {
  if (!done) return '未做'
  const n = Number(retries || 0)
  if (n <= 0) return '一次全对'
  return `重试 ${n} 次才全过`
}

export function recordReportText(done: boolean, score?: number) {
  if (!done) return '未录'
  const n = Number(score || 0)
  return n ? `已录 ${n}分` : '已录'
}
