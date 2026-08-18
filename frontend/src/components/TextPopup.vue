<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { isWordToken, lookupWord, matchTranslate, splitTokens, type DictItem } from '../utils/dict'
import { speakText, stopSpeak } from '../utils/speak'

const props = defineProps<{
  open: boolean
  text: string
  english: string
  translate: string
  banks: DictItem[]
}>()

const emit = defineEmits<{ close: [] }>()

const tokens = computed(() => splitTokens(props.text))
const sentenceZh = computed(() => matchTranslate(props.text, props.english, props.translate))
const speaking = ref('')
const activeWord = ref('')
const wordZh = ref('')
const showSentenceZh = ref(false)
const looking = ref(false)

watch(
  () => [props.open, props.text] as const,
  () => {
    speaking.value = ''
    activeWord.value = ''
    wordZh.value = ''
    showSentenceZh.value = false
    looking.value = false
    if (!props.open) stopSpeak()
  },
)

async function onTokenClick(token: string) {
  if (!isWordToken(token)) return
  activeWord.value = token
  speaking.value = token
  looking.value = true
  try {
    wordZh.value = await lookupWord(token, props.banks)
    await speakText(token, '单词发音')
  } catch {
    /* 发音失败仍显示释义 */
  } finally {
    looking.value = false
    if (speaking.value === token) speaking.value = ''
  }
}

async function playSentence() {
  speaking.value = props.text
  try {
    await speakText(props.text, '句子朗读')
  } finally {
    if (speaking.value === props.text) speaking.value = ''
  }
}

function close() {
  stopSpeak()
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[80] flex items-center justify-center bg-slate-900/45 p-2 sm:p-4"
        @click.self="close"
      >
        <div class="card relative w-full max-w-xl animate-pop-in px-3 py-4 sm:px-5 sm:py-6">
          <button class="game-result-close" type="button" aria-label="关闭" @click="close">×</button>
          <div class="flex flex-wrap items-center justify-center gap-2 pr-6">
            <button
              v-for="(token, idx) in tokens"
              :key="`${idx}-${token}`"
              type="button"
              class="sentence-token"
              :class="{
                'sentence-token-speaking': speaking === token,
                'sentence-token-active': activeWord === token && speaking !== token,
                'sentence-token-punct': !isWordToken(token),
              }"
              :disabled="!isWordToken(token)"
              @click="onTokenClick(token)"
            >
              {{ token }}
            </button>
          </div>
          <p class="mt-4 min-h-7 text-center text-lg font-extrabold text-brand-700">
            <span v-if="looking && !wordZh">查词中…</span>
            <span v-else-if="activeWord">{{ wordZh || '暂无释义' }}</span>
            <span v-else class="text-sm font-bold text-brand-600/60">点一个单词，听发音、看中文</span>
          </p>
          <p v-if="showSentenceZh && sentenceZh" class="mt-1 text-center text-base font-bold leading-7 text-brand-600">
            {{ sentenceZh }}
          </p>
          <div class="mt-5 flex flex-wrap items-center justify-center gap-2">
            <button class="btn-primary px-4 py-2 text-sm" type="button" @click="playSentence">
              {{ speaking === text ? '朗读中…' : '朗读' }}
            </button>
            <button
              class="px-4 py-2 text-sm"
              :class="showSentenceZh ? 'btn-candy' : 'btn-ghost'"
              type="button"
              @click="showSentenceZh = !showSentenceZh"
            >
              {{ showSentenceZh ? '隐藏翻译' : '翻译' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
.sentence-token {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.3rem 0.7rem;
  border-radius: 0.7rem;
  background: #fff4e5;
  font-size: 1.1rem;
  font-weight: 800;
  color: #9a3412;
  transition:
    transform 0.12s ease,
    background-color 0.12s ease;
}
.sentence-token:not(:disabled):hover {
  background: #fbbf24;
  transform: scale(1.05);
}
.sentence-token-speaking,
.sentence-token-active {
  background: #fb923c;
  color: #fff;
  transform: scale(1.08);
}
.sentence-token-punct {
  background: transparent;
  color: #c4b5a5;
  cursor: default;
  padding-inline: 0.15rem;
}
</style>
