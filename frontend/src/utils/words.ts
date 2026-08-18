export function splitWords(text: string): string[] {
  return text.match(/[A-Za-z']+|[^\sA-Za-z']+/g) || []
}
