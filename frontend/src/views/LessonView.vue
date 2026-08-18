<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, apiPost } from '../api'
import AiAskListenFab from '../components/AiAskListenFab.vue'
import AssistantLive2dPip from '../components/AssistantLive2dPip.vue'
import BookStage from '../components/BookStage.vue'
import ClubDialog from '../components/ClubDialog.vue'
import TextPopup from '../components/TextPopup.vue'
import { recognizeAudio } from '../utils/asr'
import { speakAssistantText, stopAssistantSpeak } from '../utils/assistantTts'
import { concatClips } from '../utils/concatClips'
import type { DictItem } from '../utils/dict'
import { recordPageClip, type PageClip } from '../utils/recordPage'
import { scoreEnglish } from '../utils/score'
import { ensureOcr, ensureTts } from '../utils/ensureAsset'
import { stopSpeak } from '../utils/speak'
import { boxesFor, inflateBox, mergeShortSegments, needlesOf, sleep, splitSentences, type Box } from '../utils/text'
import { uploadReading } from '../utils/uploadReading'

type Item = { en: string; zh: string }
type Choice = { key: string; text: string; ok: boolean }

const route = useRoute()
const router = useRouter()
const data = ref<any>(null)
const beatIndex = ref(0)
const step = ref<'explain' | 'vocab' | 'phrase' | 'record'>('explain')
const PASS_SCORE = 60
let live: HTMLAudioElement | null = null
const answers = ref<Record<number, string>>({})
const submitted = ref(false)
const quizCursor = ref(0)
const quizRevealed = ref(false)
const celebrating = ref(false)
const wrongKeys = ref<Record<number, string[]>>({})
const flowPaused = ref(false)
const focusItem = ref<Item | null>(null)
const segIndex = ref(0)
const sentIndex = ref(-1)
const overlay = ref<Box[]>([])
const karaokeWords = ref<Box[]>([])
const recording = ref(false)
const recordedUrl = ref('')
const busy = ref(false)
const lastScore = ref<number | null>(null)
const lastHeard = ref('')
const scoreError = ref('')
const passed = ref(false)
const gapSec = ref(Number(localStorage.getItem('club-tts-gap') || '1'))
const SEC_PER_WORD = 3
const recordLeft = ref(0)
const recordTotal = ref(0)
const uploadHint = ref('')
const pageClips = ref<PageClip[]>([])
let pageRecorder: { stop: () => Promise<PageClip> } | null = null
let quizTimer: number | null = null
let passTimer: number | null = null
let recordTimer: number | null = null
let playGen = 0

const lesson = computed(() => data.value?.lesson)
const beat = computed(() => lesson.value?.beats?.[beatIndex.value])
const firstBeat = computed(() => beatIndex.value <= 0)
const lastBeat = computed(() => beatIndex.value >= (lesson.value?.beats?.length || 1) - 1)
const sentences = computed(() => splitSentences(beat.value?.explain || ''))
const vocabQs = computed(() => makeQuiz(beat.value?.word_items || [], lesson.value?.word_bank || []))
const phraseQs = computed(() => makeQuiz(beat.value?.phrase_items || [], lesson.value?.phrase_bank || []))
const currentQuiz = computed(() => (step.value === 'vocab' ? vocabQs.value : phraseQs.value))
const currentQuestion = computed(() => currentQuiz.value[quizCursor.value])
const pageSegments = computed(() => mergeShortSegments(beat.value?.segments || []))
const currentSeg = computed(() => pageSegments.value[segIndex.value] || '')
const recordWords = computed(() => (currentSeg.value.match(/[A-Za-z']+/g) || []).length)
const lastSegment = computed(() => segIndex.value >= (pageSegments.value.length || 1) - 1)
const dialogOpen = computed(() => step.value !== 'explain' && !flowPaused.value)
const quizDialogOpen = computed(() => dialogOpen.value && (step.value === 'vocab' || step.value === 'phrase'))
const recordDialogOpen = computed(() => dialogOpen.value && step.value === 'record')
const segmentMode = computed(() => step.value === 'record' && karaokeWords.value.length > 0)
const displayBoxes = computed(() => {
  const raw = segmentMode.value
    ? karaokeWords.value.map((box) => ({ ...box, active: true }))
    : overlay.value.map((box) => ({ ...box, active: false }))
  return raw.map((box) => inflateBox(box))
})
const bookKey = computed(() => `${route.params.seriesId}/${route.params.bookSlug}`)
const pageHotspots = computed(() => (beat.value?.ocr || []) as Box[])
const dictBanks = computed<DictItem[]>(() => [
  ...(lesson.value?.word_bank || []),
  ...(lesson.value?.phrase_bank || []),
  ...(beat.value?.word_items || []),
  ...(beat.value?.phrase_items || []),
])
const textPopup = ref('')
const askListening = ref(false)
const askStream = ref<MediaStream | null>(null)
const askBusy = ref(false)
const askError = ref('')
const chatHistory = ref<{ role: 'user' | 'assistant'; content: string }[]>([])
let askRecorder: MediaRecorder | null = null
let askChunks: Blob[] = []
const stepLabel = computed(() => {
  const labels = {
    explain: '讲解',
    vocab: '词汇复习',
    phrase: '短语复习',
    record: '朗读评分',
  }
  return labels[step.value]
})

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

function makeQuiz(items: Item[], bank: Item[]) {
  return items.map((item) => {
    const pool = bank.filter((b) => b.zh !== item.zh).map((b) => b.zh)
    const extras = ['小狗', '椅子', '窗户', '明天', '红色'].filter((z) => z !== item.zh)
    const distractors = shuffle([...pool, ...extras]).slice(0, 2)
    const options: Choice[] = shuffle([item.zh, ...distractors]).map((text, i) => ({
      key: 'ABC'[i],
      text,
      ok: text === item.zh,
    }))
    return { item, options }
  })
}

function markNeedles(needles: string[]) {
  overlay.value = boxesFor(needles, beat.value?.ocr || [])
}

function markSentence(text: string) {
  markNeedles(needlesOf(text, beat.value?.word_items || [], beat.value?.phrase_items || []))
}

function stopAskStream() {
  askRecorder = null
  askChunks = []
  askStream.value?.getTracks().forEach((track) => track.stop())
  askStream.value = null
  askListening.value = false
}

async function startAsk() {
  if (askBusy.value || askListening.value) return
  stopAudio()
  stopAssistantSpeak()
  askError.value = ''
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  askStream.value = stream
  askChunks = []
  const recorder = new MediaRecorder(stream)
  askRecorder = recorder
  recorder.ondataavailable = (ev) => {
    if (ev.data.size) askChunks.push(ev.data)
  }
  recorder.start()
  askListening.value = true
}

async function finishAsk() {
  if (!askRecorder) return
  askBusy.value = true
  const recorder = askRecorder
  const blob = await new Promise<Blob>((resolve) => {
    recorder.onstop = () => resolve(new Blob(askChunks, { type: recorder.mimeType || 'audio/webm' }))
    if (recorder.state !== 'inactive') recorder.stop()
    else resolve(new Blob(askChunks, { type: 'audio/webm' }))
  })
  stopAskStream()
  try {
    const heard = await recognizeAudio(blob, 'zh')
    if (!heard) throw new Error('没听清，再说一次')
    const res = await apiPost('/api/teaching/chat', {
      book_title: lesson.value?.title || '',
      current_page_number: beat.value?.page,
      current_english: beat.value?.english || '',
      current_script: beat.value?.explain || '',
      student_text: heard,
      messages: chatHistory.value,
    })
    chatHistory.value = [
      ...chatHistory.value,
      { role: 'user', content: heard },
      { role: 'assistant', content: res.reply },
    ].slice(-20)
    await speakAssistantText(res.reply)
  } catch (e: any) {
    askError.value = e?.message || '助教暂时没听清'
  } finally {
    askBusy.value = false
  }
}

function stopAudio() {
  playGen += 1
  stopSpeak()
  stopAssistantSpeak()
  if (live) {
    live.pause()
    live.src = ''
    live = null
  }
}

function openTextPopup(box: Box) {
  const text = (box.text || '').trim()
  if (!text) return
  stopAudio()
  textPopup.value = text
}

function closeTextPopup() {
  textPopup.value = ''
}

async function playOne(text: string, purpose?: string): Promise<void> {
  if (!text) return
  const gen = playGen
  const label =
    purpose ||
    (step.value === 'phrase' ? '短语发音' : step.value === 'vocab' ? '单词发音' : '讲解音频')
  const url = await ensureTts(text, label)
  if (!url || gen !== playGen) return
  await new Promise<void>((resolve) => {
    const audio = new Audio(url)
    live = audio
    const done = () => {
      audio.onended = null
      audio.onerror = null
      if (live === audio) live = null
      resolve()
    }
    audio.onended = done
    audio.onerror = done
    audio.play().catch(done)
  })
}

async function playExplain() {
  stopAudio()
  const gen = playGen
  const list = sentences.value
  for (let i = 0; i < list.length; i++) {
    if (gen !== playGen) return
    sentIndex.value = i
    markSentence(list[i])
    nextTick(() => document.getElementById(`sent-${i}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
    await playOne(list[i])
    if (gen !== playGen) return
    if (i < list.length - 1) await sleep(Math.max(0, gapSec.value) * 1000)
  }
}

async function loadWordBoxes(text: string) {
  karaokeWords.value = []
  if (!text || !beat.value) return
  try {
    karaokeWords.value = (await ensureOcr({
      series_id: String(route.params.seriesId),
      book_slug: String(route.params.bookSlug),
      page: beat.value.page,
      text,
      purpose: '这一句的词框',
    })) as Box[]
  } catch {
    karaokeWords.value = []
  }
}

function revealReadBoxes() {
  nextTick(() => {
    document.getElementById('read-box-0')?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  })
}

async function highlightSegment() {
  lastScore.value = null
  lastHeard.value = ''
  scoreError.value = ''
  passed.value = false
  recordedUrl.value = ''
  await loadWordBoxes(currentSeg.value)
  if (!karaokeWords.value.length) markNeedles([currentSeg.value])
  revealReadBoxes()
}

function clearQuizTimer() {
  if (quizTimer) {
    window.clearTimeout(quizTimer)
    quizTimer = null
  }
}

function clearRecordTimer() {
  if (recordTimer) {
    window.clearInterval(recordTimer)
    recordTimer = null
  }
}

function startStep() {
  answers.value = {}
  submitted.value = false
  quizCursor.value = 0
  quizRevealed.value = false
  celebrating.value = false
  wrongKeys.value = {}
  clearQuizTimer()
  clearRecordTimer()
  recordLeft.value = 0
  recordTotal.value = 0
  flowPaused.value = false
  segIndex.value = 0
  sentIndex.value = -1
  overlay.value = []
  karaokeWords.value = []
  recordedUrl.value = ''
  lastScore.value = null
  lastHeard.value = ''
  scoreError.value = ''
  passed.value = false
  if (step.value === 'explain') nextTick(playExplain)
  if (step.value === 'record') nextTick(highlightSegment)
}

function startActivity(next: 'vocab' | 'phrase' | 'record') {
  if (next === 'vocab' && !vocabQs.value.length) return
  if (next === 'phrase' && !phraseQs.value.length) return
  stopAudio()
  step.value = next
  startStep()
}

function closeActivity() {
  clearQuizTimer()
  clearPassTimer()
  if (recording.value) stopRecord()
  stopAudio()
  step.value = 'explain'
  flowPaused.value = false
}

function pickOption(key: string) {
  if (celebrating.value || submitted.value) return
  const tried = wrongKeys.value[quizCursor.value] || []
  if (tried.includes(key)) return
  const opt = currentQuestion.value?.options.find((item) => item.key === key)
  answers.value = { ...answers.value, [quizCursor.value]: key }
  const item = currentQuestion.value?.item
  if (!opt?.ok) {
    wrongKeys.value = { ...wrongKeys.value, [quizCursor.value]: [...tried, key] }
    if (item) {
      apiPost('/api/wrongbook/add', {
        kind: step.value === 'phrase' ? 'phrase' : 'vocab',
        en: item.en,
        zh: item.zh,
        ...pageMeta(),
      }).catch(() => undefined)
    }
    return
  }
  if (item) {
    apiPost('/api/wrongbook/resolve', {
      kind: step.value === 'phrase' ? 'phrase' : 'vocab',
      en: item.en,
      zh: item.zh,
      ...pageMeta(),
    }).catch(() => undefined)
  }
  celebrating.value = true
  quizRevealed.value = true
  clearQuizTimer()
  quizTimer = window.setTimeout(() => {
    celebrating.value = false
    nextQuizItem()
  }, 2000)
}

function nextQuizItem() {
  clearQuizTimer()
  celebrating.value = false
  quizRevealed.value = false
  if (quizCursor.value < currentQuiz.value.length - 1) {
    quizCursor.value += 1
    return
  }
  nextAfterQuiz()
}

function optionClass(opt: Choice) {
  const tried = wrongKeys.value[quizCursor.value] || []
  if (celebrating.value && opt.ok) return 'bg-mint text-white shadow-pop'
  if (tried.includes(opt.key)) return 'bg-candy text-white shadow-pop opacity-70'
  return 'bg-white/80 text-brand-700 hover:bg-white'
}

const lastWrong = computed(() => {
  const tried = wrongKeys.value[quizCursor.value] || []
  return !celebrating.value && tried.length > 0
})

function pageMeta() {
  return {
    series_id: String(route.params.seriesId || ''),
    book_slug: String(route.params.bookSlug || ''),
    book_title: String(lesson.value?.title_zh || lesson.value?.title || ''),
    chapter_id: String(route.params.chapterId || ''),
    page: Number(beat.value?.page || 0),
  }
}

function saveProgress(extra: Record<string, unknown>) {
  apiPost('/api/progress', { ...pageMeta(), ...extra }).catch(() => undefined)
}

function nextAfterQuiz() {
  saveProgress(step.value === 'phrase' ? { phrase_done: true } : { vocab_done: true })
  closeActivity()
}

function clearPassTimer() {
  if (passTimer) {
    window.clearTimeout(passTimer)
    passTimer = null
  }
}

async function advanceSegment() {
  clearPassTimer()
  stopAudio()
  if (!lastSegment.value) {
    segIndex.value += 1
    nextTick(highlightSegment)
    return
  }
  if (pageClips.value.length) await flushPageRecording()
  if (lastBeat.value) return
  nextPage()
}

async function startRecord() {
  stopAudio()
  lastScore.value = null
  lastHeard.value = ''
  scoreError.value = ''
  passed.value = false
  uploadHint.value = ''
  clearPassTimer()
  pageRecorder = await recordPageClip(beat.value.image)
  recording.value = true
  const total = Math.max(SEC_PER_WORD, recordWords.value * SEC_PER_WORD)
  const deadline = Date.now() + total * 1000
  clearRecordTimer()
  recordTotal.value = total
  recordLeft.value = total
  recordTimer = window.setInterval(() => {
    const left = Math.max(0, (deadline - Date.now()) / 1000)
    recordLeft.value = left
    if (left <= 0) stopRecord()
  }, 100)
}

async function stopRecord() {
  clearRecordTimer()
  recordLeft.value = 0
  recording.value = false
  const rec = pageRecorder
  pageRecorder = null
  if (!rec) return
  const clip = await rec.stop()
  recordedUrl.value = URL.createObjectURL(clip.blob)
  await scoreBlob(clip)
}

async function scoreBlob(clip: PageClip) {
  busy.value = true
  scoreError.value = ''
  try {
    const heard = await recognizeAudio(clip.blob, 'en')
    const result = scoreEnglish(currentSeg.value, heard)
    lastScore.value = result.score
    lastHeard.value = result.heard
    passed.value = result.score >= PASS_SCORE
    if (passed.value) {
      pageClips.value = [...pageClips.value, { ...clip, score: result.score }]
      clearPassTimer()
      if (lastSegment.value) await flushPageRecording()
      passTimer = window.setTimeout(advanceSegment, lastSegment.value ? 800 : 1600)
    }
  } catch (err) {
    scoreError.value = err instanceof Error ? err.message : '评分失败'
  } finally {
    busy.value = false
  }
}

async function flushPageRecording() {
  if (!pageClips.value.length || !beat.value) return
  try {
    uploadHint.value = '正在合并本页朗读…'
    const merged = await concatClips(pageClips.value)
    merged.score = Math.round(pageClips.value.reduce((sum, item) => sum + item.score, 0) / pageClips.value.length)
    await uploadReading({
      clip: merged,
      seriesId: String(route.params.seriesId),
      bookSlug: String(route.params.bookSlug),
      bookTitle: String(lesson.value?.title_zh || lesson.value?.title || ''),
      chapterId: String(route.params.chapterId),
      page: beat.value.page,
      onProgress: (text) => {
        uploadHint.value = text
      },
    })
    uploadHint.value = '本页朗读已上传'
    pageClips.value = []
  } catch (err) {
    uploadHint.value = err instanceof Error ? err.message : '上传失败'
  }
}

function goBack() {
  router.back()
}

function goToBeat(index: number) {
  const max = (lesson.value?.beats?.length || 1) - 1
  if (index < 0 || index > max || index === beatIndex.value) return
  clearQuizTimer()
  clearPassTimer()
  if (recording.value) stopRecord()
  if (pageClips.value.length) flushPageRecording()
  stopAudio()
  closeTextPopup()
  celebrating.value = false
  focusItem.value = null
  beatIndex.value = index
  step.value = 'explain'
  startStep()
}

function prevPage() {
  goToBeat(beatIndex.value - 1)
}

function nextPage() {
  goToBeat(beatIndex.value + 1)
}

function clickSentence(i: number) {
  if (step.value !== 'explain') return
  playFrom(i)
}

async function playFrom(start: number) {
  stopAudio()
  const gen = playGen
  const list = sentences.value
  for (let i = start; i < list.length; i++) {
    if (gen !== playGen) return
    sentIndex.value = i
    markSentence(list[i])
    nextTick(() => document.getElementById(`sent-${i}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
    await playOne(list[i])
    if (gen !== playGen) return
    if (i < list.length - 1) await sleep(Math.max(0, gapSec.value) * 1000)
  }
}

function pauseFlow() {
  closeActivity()
}

function resumeFlow() {
  flowPaused.value = false
  if (step.value === 'record') nextTick(highlightSegment)
}

function openFocus(item: Item) {
  focusItem.value = item
  markNeedles([item.en])
  playOne(item.en)
}

watch(gapSec, (value) => localStorage.setItem('club-tts-gap', String(value)))

watch(beatIndex, () => closeTextPopup())

watch(
  () => [step.value, quizCursor.value, segIndex.value] as const,
  () => {
    if (step.value === 'vocab' || step.value === 'phrase') {
      const item = currentQuiz.value[quizCursor.value]?.item
      if (item) {
        markNeedles([item.en])
        playOne(item.en)
      }
    }
    if (step.value === 'record') markNeedles([currentSeg.value])
  },
)

onMounted(async () => {
  data.value = await api(`/api/lessons/${route.params.seriesId}/${route.params.bookSlug}/${route.params.chapterId}`)
  startStep()
})

onUnmounted(() => {
  clearQuizTimer()
  clearPassTimer()
  clearRecordTimer()
  if (recording.value) stopRecord()
  stopAskStream()
  stopAudio()
})
</script>

<template>
  <div v-if="lesson && beat" class="flex h-full min-h-0 flex-col">
    <div class="fixed left-1/2 top-2 z-[90] flex -translate-x-1/2 items-center gap-2">
      <button
        class="rounded-full bg-white/90 px-4 py-2 text-sm font-extrabold text-brand-700 shadow-pop"
        type="button"
        @click="goBack"
      >
        ← 返回
      </button>
      <button
        class="rounded-full bg-white/90 px-4 py-2 text-sm font-extrabold text-brand-700 shadow-pop disabled:opacity-40"
        type="button"
        :disabled="firstBeat"
        @click="prevPage"
      >
        上一页
      </button>
      <button
        class="rounded-full bg-white/90 px-4 py-2 text-sm font-extrabold text-brand-700 shadow-pop disabled:opacity-40"
        type="button"
        :disabled="lastBeat"
        @click="nextPage"
      >
        下一页
      </button>
    </div>
    <div class="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
    <section class="relative min-h-[58dvh] min-w-0 flex-1 lg:min-h-0">
      <div class="h-full overflow-hidden rounded-2xl border border-brand-200/60 bg-brand-50">
        <BookStage
          :src="beat.image"
          :boxes="displayBoxes"
          :hotspots="pageHotspots"
          :active-text="textPopup"
          :book-key="bookKey"
          @select="openTextPopup"
        />
      </div>
      <button
        v-if="flowPaused && step !== 'explain'"
        class="btn-candy absolute bottom-3 left-3 right-3 z-10"
        type="button"
        @click="resumeFlow"
      >
        继续{{ stepLabel }}
      </button>
    </section>

    <aside class="max-h-[40vh] space-y-3 overflow-y-auto lg:max-h-none lg:h-full lg:w-[360px] lg:shrink-0">
        <p class="font-extrabold text-brand-700">
          {{ lesson.title_zh }} · 第 {{ beat.page }} 页 · {{ beatIndex + 1 }}/{{ lesson.beats.length }}
        </p>
        <section class="card space-y-3">
          <div class="flex items-center justify-between gap-2">
            <p class="text-xs font-extrabold uppercase tracking-wide text-brand-600">讲解</p>
            <label class="flex items-center gap-1 text-xs font-bold text-brand-600/70">
              句间停
              <input
                v-model.number="gapSec"
                class="w-14 rounded-xl border border-brand-200 bg-white px-2 py-1 font-bold text-brand-700"
                type="number"
                min="0"
                max="5"
                step="0.5"
              />
              秒
            </label>
          </div>
          <div class="max-h-[42vh] space-y-2 overflow-y-auto pr-1">
            <button
              v-for="(sent, i) in sentences"
              :id="`sent-${i}`"
              :key="i"
              type="button"
              class="block w-full rounded-2xl px-3 py-2 text-left leading-7"
              :class="i === sentIndex ? 'bg-sunny/80 font-bold text-brand-700' : 'font-bold text-brand-700/80 hover:bg-brand-50'"
              @click="clickSentence(i)"
            >
              {{ sent }}
            </button>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button class="btn-ghost w-full" type="button" @click="playExplain">再听一遍</button>
            <button
              class="btn-primary w-full"
              type="button"
              :disabled="!vocabQs.length"
              @click="startActivity('vocab')"
            >
              复习单词
            </button>
            <button
              class="btn-primary w-full"
              type="button"
              :disabled="!phraseQs.length"
              @click="startActivity('phrase')"
            >
              复习短语
            </button>
            <button class="btn-candy w-full" type="button" @click="startActivity('record')">开始录制</button>
          </div>
        </section>

        <section class="card space-y-3">
          <p class="font-extrabold text-brand-700">这一页重点</p>
          <div>
            <p class="mb-2 text-xs font-extrabold text-brand-500">词</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="w in beat.word_items"
                :key="w.en"
                type="button"
                class="chip bg-brand-100 text-brand-700 transition hover:bg-brand-200"
                @click="openFocus(w)"
              >
                {{ w.en }}
              </button>
            </div>
          </div>
          <div>
            <p class="mb-2 text-xs font-extrabold text-brand-500">短语</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="p in beat.phrase_items"
                :key="p.en"
                type="button"
                class="chip bg-sky/15 text-brand-700 transition hover:bg-sky/25"
                @click="openFocus(p)"
              >
                {{ p.en }}
              </button>
            </div>
          </div>
        </section>
      </aside>
    </div>

    <ClubDialog
      :open="quizDialogOpen"
      :title="step === 'vocab' ? '复习词汇 · 英翻中' : '复习短语 · 英翻中'"
      :emoji="step === 'vocab' ? '🔤' : '💬'"
      dock="side"
      fixed
      @close="pauseFlow"
    >
      <template v-if="currentQuestion">
        <div class="mb-4 flex items-center justify-between">
          <span class="chip bg-brand-100 text-brand-700">第 {{ quizCursor + 1 }} / {{ currentQuiz.length }} 题</span>
          <button class="text-sm font-bold text-brand-600" type="button" @click="playOne(currentQuestion.item.en)">
            🔊 听单词
          </button>
        </div>
        <p class="mb-4 text-center text-3xl font-extrabold text-brand-700">{{ currentQuestion.item.en }}</p>
        <div class="flex flex-col gap-2">
          <button
            v-for="opt in currentQuestion.options"
            :key="opt.key"
            type="button"
            class="flex items-center gap-3 rounded-2xl px-4 py-3 text-left text-lg font-bold transition active:scale-95"
            :class="optionClass(opt)"
            :disabled="celebrating || (wrongKeys[quizCursor] || []).includes(opt.key)"
            @click="pickOption(opt.key)"
          >
            <span
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-base font-extrabold"
              :class="(celebrating && opt.ok) || (wrongKeys[quizCursor] || []).includes(opt.key) ? 'bg-white/25' : 'bg-brand-100 text-brand-700'"
            >{{ opt.key }}</span>
            <span>{{ opt.text }}</span>
          </button>
        </div>
        <p class="mt-auto h-5 text-center text-xs font-bold leading-5 text-candy">
          <span :class="lastWrong ? '' : 'invisible'">不对，再选一次</span>
        </p>
      </template>
    </ClubDialog>

    <Teleport to="body">
      <transition name="fade">
        <div
          v-if="celebrating"
          class="pointer-events-none fixed inset-0 z-[70] flex items-center justify-center"
        >
          <div class="card animate-pop-in px-10 py-8 text-center shadow-pop">
            <p class="text-6xl">🎉</p>
            <p class="mt-3 text-2xl font-extrabold text-mint">答对了！</p>
          </div>
        </div>
      </transition>
    </Teleport>

    <ClubDialog :open="recordDialogOpen" title="读这一段" emoji="📖" dock="bottom" @close="pauseFlow">
      <p class="mb-2 chip bg-brand-100 text-brand-700">第 {{ segIndex + 1 }} / {{ pageSegments.length }} 段</p>
      <p class="mb-3 font-bold text-brand-600">书上黄框就是要读的。每个词最多 3 秒，读完可点停，时间到会自动停。</p>
      <div v-if="recording" class="mb-3 text-center">
        <p class="text-5xl font-extrabold tabular-nums" :class="recordLeft <= 3 ? 'text-candy' : 'text-brand-700'">
          {{ Math.ceil(recordLeft) }}
        </p>
        <p class="mt-1 text-sm font-bold text-brand-600/70">
          秒后自动停 · {{ recordWords }} 词 × 3 秒
        </p>
        <div class="mx-auto mt-2 h-2 max-w-xs overflow-hidden rounded-full bg-brand-100">
          <div
            class="h-full rounded-full"
            :class="recordLeft <= 3 ? 'bg-candy' : 'bg-sunny'"
            :style="{ width: recordTotal ? `${(recordLeft / recordTotal) * 100}%` : '0%' }"
          />
        </div>
      </div>
      <div class="flex flex-wrap gap-2">
        <button v-if="!recording && !busy" class="btn-candy flex-1" type="button" @click="startRecord">
          {{ lastScore != null && !passed ? '再读一次' : '开始录音' }}
        </button>
        <button v-else-if="recording" class="btn-ghost flex-1" type="button" @click="stopRecord">停</button>
      </div>
      <p v-if="uploadHint" class="mt-3 font-bold text-brand-600">{{ uploadHint }}</p>
      <p v-if="busy" class="mt-3 font-bold text-brand-600/70">正在评分…</p>
      <p v-else-if="scoreError" class="mt-3 font-bold text-candy">{{ scoreError }}</p>
      <div v-else-if="lastScore != null" class="mt-3 text-center">
        <p class="text-3xl font-extrabold" :class="passed ? 'text-mint' : 'text-candy'">{{ lastScore }} 分</p>
        <p class="mt-1 font-extrabold" :class="passed ? 'text-mint' : 'text-candy'">
          {{ passed ? (lastSegment && lastBeat ? '第一章先到这里。' : lastSegment ? '过了，去下一页' : '过了！') : '还没到 60 分，再读一次' }}
        </p>
        <p v-if="lastHeard" class="mt-2 text-xs font-bold text-brand-600/60">听到了：{{ lastHeard }}</p>
      </div>
      <button
        v-if="!recording && !busy && !passed"
        class="mt-3 w-full text-center text-lg font-extrabold text-brand-600/70"
        type="button"
        @click="advanceSegment"
      >
        先跳过这句
      </button>
    </ClubDialog>

    <ClubDialog :open="!!focusItem" :title="focusItem?.en || ''" emoji="⭐" @close="focusItem = null">
      <p class="text-2xl font-extrabold text-brand-700">{{ focusItem?.zh }}</p>
      <button class="btn-primary mt-5 w-full" type="button" @click="focusItem && playOne(focusItem.en)">
        再听一遍
      </button>
    </ClubDialog>

    <TextPopup
      :open="!!textPopup"
      :text="textPopup"
      :english="beat.english || ''"
      :translate="beat.translate || ''"
      :banks="dictBanks"
      @close="closeTextPopup"
    />

    <AssistantLive2dPip :visible="true" />
    <AiAskListenFab
      :visible="true"
      :listening="askListening"
      :stream="askStream"
      :disabled="askBusy || recording"
      @ask="startAsk"
      @finish="finishAsk"
    />
    <p
      v-if="askError || askBusy"
      class="pointer-events-none fixed bottom-24 left-1/2 z-[93] -translate-x-1/2 rounded-full bg-white/95 px-4 py-1.5 text-xs font-extrabold text-candy shadow-pop"
    >
      {{ askBusy ? '助教正在想…' : askError }}
    </p>
  </div>
</template>
