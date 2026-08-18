import { ref } from 'vue'

export const generateLabel = ref('')

export function beginGenerate(label: string) {
  generateLabel.value = label
}

export function endGenerate() {
  generateLabel.value = ''
}
