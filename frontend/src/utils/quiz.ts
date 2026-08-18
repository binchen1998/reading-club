export type QuizItem = { en: string; zh: string }

export type ChoiceQuestion = {
  en: string
  options: { label: string; text: string }[]
  correct: string
}

const LETTERS = ['A', 'B', 'C']

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

export function buildEnToZh(items: QuizItem[]): ChoiceQuestion[] {
  const pool = [...new Set(items.map((i) => i.zh).filter(Boolean))]
  const extras = ['侦探', '书包', '厨房', '怪物', '故事', '同学', '秘密', '脚印']
  const distractors = [...new Set([...pool, ...extras])]
  return items
    .filter((i) => i.en && i.zh)
    .map((item) => {
      const others = shuffle(distractors.filter((t) => t !== item.zh)).slice(0, 2)
      const texts = shuffle([item.zh, ...others])
      const options = texts.map((text, i) => ({ label: LETTERS[i], text }))
      return {
        en: item.en,
        options,
        correct: options.find((o) => o.text === item.zh)?.label || 'A',
      }
    })
}
