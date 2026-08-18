import { nextTick, ref } from 'vue'

export const generateLabel = ref('')

let depth = 0

export function beginGenerate(label: string) {
  depth += 1
  generateLabel.value = label
}

export function endGenerate() {
  depth = Math.max(0, depth - 1)
  if (depth === 0) generateLabel.value = ''
}

export async function waitGenerateShown() {
  await nextTick()
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve())
    })
  })
}
