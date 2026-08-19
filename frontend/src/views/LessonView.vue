<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, apiPost } from '../api'
import AiAskListenFab from '../components/AiAskListenFab.vue'
import AssistantLive2dPip from '../components/AssistantLive2dPip.vue'
import BookStage from '../components/BookStage.vue'
import ClubDialog from '../components/ClubDialog.vue'
import RecordBar from '../components/RecordBar.vue'
import TextPopup from '../components/TextPopup.vue'
import UserCameraPip from '../components/UserCameraPip.vue'
import { setAssistantExtraBottom } from '../composables/useAssistantPipFrame'
import { useUserCamera } from '../composables/useUserCamera'
import { useUserStore } from '../stores/user'
import { recognizeAudio } from '../utils/asr'
import { speakAssistantText, stopAssistantSpeak } from '../utils/assistantTts'
import { concatClips } from '../utils/concatClips'
import type { DictItem } from '../utils/dict'
import { recordPageClip, type PageClip } from '../utils/recordPage'
import { scoreEnglish } from '../utils/score'
import { ensureOcr, ensureTts, hasCachedTts, prefetchPageAssets } from '../utils/ensureAsset'
import { waitJobResult } from '../utils/jobSse'
import { stopSpeak } from '../utils/speak'
import { boxesFor, inflateBox, mergeShortSegments, needlesOf, sleep, splitSentences, type Box } from '../utils/text'
import { sound } from '../utils/sound'
import { saveReadingLocal, uploadReadingCloud } from '../utils/uploadReading'

type Item = { en: string; zh: string }
type Choice = { key: string; text: string; ok: boolean }

const route = useRoute()
const router = useRouter()
const user = useUserStore()
const camera = useUserCamera()
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
const quizHadWrong = ref(false)
const quizNeedRetry = ref(false)
const quizSeed = ref(0)
const vocabDone = ref(false)
const phraseDone = ref(false)
const recordDone = ref(false)
const vocabRetries = ref(0)
const phraseRetries = ref(0)
const explainBusy = ref(false)
const explainBusyError = ref('')
const explainWaitingTts = ref(false)
const wrongKeys = ref<Record<number, string[]>>({})
const flowPaused = ref(false)
const focusItem = ref<Item | null>(null)
const segIndex = ref(0)
const sentIndex = ref(-1)
const overlay = ref<Box[]>([])
const pageOcr = ref<Box[]>([])
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
const mergeOpen = ref(false)
const mergeTitle = ref('正在合成视频')
const mergeHint = ref('')
const mergePercent = ref(0)
const mergeFailed = ref(false)
const mergePhase = ref<'working' | 'ask-upload' | 'ask-discard' | 'uploading' | 'failed'>('working')
const sharePublic = ref(false)
const pageClips = ref<PageClip[]>([])
let flushingPage = false
let mergeChoice: ((value: 'skip' | 'upload') => void) | null = null
let pageRecorder: { stop: () => Promise<PageClip> } | null = null
let quizTimer: number | null = null
let passTimer: number | null = null
let recordTimer: number | null = null
let playGen = 0
let pagePrepGen = 0
const pageOcrCache = new Map<string, Box[]>()
const explainPlaying = ref(false)
const explainPaused = ref(false)

const lesson = computed(() => data.value?.lesson)
const beat = computed(() => lesson.value?.beats?.[beatIndex.value])
const firstBeat = computed(() => beatIndex.value <= 0)
const lastBeat = computed(() => beatIndex.value >= (lesson.value?.beats?.length || 1) - 1)
const sentences = computed(() => splitSentences(beat.value?.explain || ''))
const pageHasStoryText = computed(
  () => !!String(beat.value?.english || '').trim() || sentences.value.length > 0,
)
const explainHint = computed(() => {
  if (explainBusy.value) return ''
  if (!pageHasStoryText.value) return '这一页没有文字，看看图就好。'
  if (explainBusyError.value) return '讲解还没准备好，过一会儿再听。'
  return ''
})
const vocabQs = computed(() => {
  void quizSeed.value
  return makeQuiz(beat.value?.word_items || [], lesson.value?.word_bank || [])
})
const phraseQs = computed(() => {
  void quizSeed.value
  return makeQuiz(beat.value?.phrase_items || [], lesson.value?.phrase_bank || [])
})
const needVocab = computed(() => (beat.value?.word_items || []).length > 0)
const needPhrase = computed(() => (beat.value?.phrase_items || []).length > 0)
const needRecord = computed(() => mergeShortSegments(beat.value?.segments || []).length > 0)
const pageTasksReady = computed(() => {
  if (needVocab.value && !vocabDone.value) return false
  if (needPhrase.value && !phraseDone.value) return false
  if (needRecord.value && !recordDone.value) return false
  return true
})
const currentQuiz = computed(() => (step.value === 'vocab' ? vocabQs.value : phraseQs.value))
const currentQuestion = computed(() => currentQuiz.value[quizCursor.value])
const pageSegments = computed(() => mergeShortSegments(beat.value?.segments || []))
const currentSeg = computed(() => pageSegments.value[segIndex.value] || '')
const recordWords = computed(() => (currentSeg.value.match(/[A-Za-z']+/g) || []).length)
const lastSegment = computed(() => segIndex.value >= (pageSegments.value.length || 1) - 1)
const dialogOpen = computed(() => step.value !== 'explain' && !flowPaused.value)
const quizDialogOpen = computed(() => dialogOpen.value && (step.value === 'vocab' || step.value === 'phrase'))
const recordBarOpen = computed(() => dialogOpen.value && step.value === 'record')
const cameraEnabled = computed(() => !!camera.enabled.value)
const cameraStarting = computed(() => !!camera.starting.value)
const cameraErrorText = computed(() => camera.error.value || '')
const recordPassText = computed(() => {
  if (lastScore.value == null) return ''
  if (!passed.value) return '还没到 60 分，再读一次'
  if (lastSegment.value && lastBeat.value && pageTasksReady.value) return '第一章先到这里'
  if (lastSegment.value && pageTasksReady.value) return '过了，可以翻页'
  return '过了'
})
const segmentMode = computed(() => step.value === 'record' && karaokeWords.value.length > 0)
const displayBoxes = computed(() => {
  const raw = segmentMode.value
    ? karaokeWords.value.map((box) => ({ ...box, active: true }))
    : overlay.value.map((box) => ({ ...box, active: false }))
  return raw.map((box) => inflateBox(box))
})
const bookKey = computed(() => `${route.params.seriesId}/${route.params.bookSlug}`)
const showAssistant = computed(() => {
  const raw = route.query.assistant
  const value = Array.isArray(raw) ? raw[0] : raw
  return String(value || '').toLowerCase() === 'yes'
})
const pageHotspots = computed(() => pageOcr.value)
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
  overlay.value = boxesFor(needles, pageOcr.value)
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
    const job = (await apiPost('/api/teaching/chat', {
      book_title: lesson.value?.title || '',
      current_page_number: beat.value?.page,
      current_english: beat.value?.english || '',
      current_script: beat.value?.explain || '',
      student_text: heard,
      messages: chatHistory.value,
    })) as { job_id?: string; result?: { reply?: string } }
    const reply =
      job.result?.reply ||
      (job.job_id ? (await waitJobResult<{ reply?: string }>(job.job_id)).reply : '') ||
      ''
    if (!reply) throw new Error('助教暂时没听清')
    chatHistory.value = [
      ...chatHistory.value,
      { role: 'user', content: heard },
      { role: 'assistant', content: reply },
    ].slice(-20)
    await speakAssistantText(reply)
  } catch (e: any) {
    askError.value = e?.message || '助教暂时没听清'
  } finally {
    askBusy.value = false
  }
}

function stopAudio() {
  playGen += 1
  explainPlaying.value = false
  explainPaused.value = false
  explainWaitingTts.value = false
  stopSpeak()
  stopAssistantSpeak()
  if (live) {
    live.pause()
    live.src = ''
    live = null
  }
}

function pauseExplain() {
  if (!explainPlaying.value) return
  explainPaused.value = true
  live?.pause()
}

function resumeExplain() {
  if (explainPlaying.value && explainPaused.value) {
    explainPaused.value = false
    live?.play().catch(() => undefined)
    return
  }
  void playExplain(Math.max(0, sentIndex.value))
}

function toggleExplainPlay() {
  if (explainPlaying.value && !explainPaused.value) pauseExplain()
  else resumeExplain()
}

function restartExplain() {
  void playExplain(0)
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
  const silent = step.value === 'explain'
  if (silent && !hasCachedTts(text)) explainWaitingTts.value = true
  let url = ''
  try {
    url = await ensureTts(text, label, silent ? { silent: true } : undefined)
  } catch {
    url = ''
  } finally {
    if (gen === playGen) explainWaitingTts.value = false
  }
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

async function waitIfExplainPaused(gen: number) {
  while (explainPaused.value && gen === playGen) {
    await sleep(80)
  }
}

async function playExplain(from = 0) {
  stopAudio()
  explainPlaying.value = true
  explainPaused.value = false
  const gen = playGen
  const list = sentences.value
  const start = Math.min(Math.max(0, from), Math.max(0, list.length - 1))
  for (let i = start; i < list.length; i++) {
    if (gen !== playGen) return
    await waitIfExplainPaused(gen)
    if (gen !== playGen) return
    sentIndex.value = i
    markSentence(list[i])
    nextTick(() => document.getElementById(`sent-${i}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
    await playOne(list[i])
    if (gen !== playGen) return
    await waitIfExplainPaused(gen)
    if (gen !== playGen) return
    if (i < list.length - 1) await sleep(Math.max(0, gapSec.value) * 1000)
  }
  if (gen === playGen) {
    explainPlaying.value = false
    explainPaused.value = false
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

function prefetchCurrentBeat() {
  const current = beat.value
  if (!current) return
  prefetchPageAssets({
    texts: [
      ...sentences.value,
      ...(current.word_items || []).map((item: Item) => item.en),
      ...(current.phrase_items || []).map((item: Item) => item.en),
      ...pageSegments.value,
      current.english || '',
    ],
    ocrItems: pageSegments.value.map((text) => ({
      series_id: String(route.params.seriesId),
      book_slug: String(route.params.bookSlug),
      page: Number(current.page || 0),
      text,
    })),
  })
}

function startStep() {
  answers.value = {}
  submitted.value = false
  quizCursor.value = 0
  quizRevealed.value = false
  celebrating.value = false
  quizHadWrong.value = false
  quizNeedRetry.value = false
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
  prefetchCurrentBeat()
  if (step.value === 'explain') nextTick(playExplain)
  if (step.value === 'record') nextTick(highlightSegment)
}

function startActivity(next: 'vocab' | 'phrase' | 'record') {
  if (next === 'vocab' && !vocabQs.value.length) return
  if (next === 'phrase' && !phraseQs.value.length) return
  if (next === 'record' && !needRecord.value) return
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
    sound.fail()
    quizHadWrong.value = true
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
  celebrating.value = true
  const lastItem = quizCursor.value >= currentQuiz.value.length - 1
  const alreadyDone = step.value === 'phrase' ? phraseDone.value : vocabDone.value
  quizNeedRetry.value = lastItem && quizHadWrong.value && !alreadyDone
  if (quizNeedRetry.value) sound.fail()
  else sound.celebrate()
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

function saveCursor() {
  const meta = pageMeta()
  if (!meta.page || !meta.chapter_id) return
  apiPost('/api/progress/cursor', {
    series_id: meta.series_id,
    book_slug: meta.book_slug,
    chapter_id: meta.chapter_id,
    page: meta.page,
  }).catch(() => undefined)
}

function applyResumePage() {
  const page = Number(route.query.page || 0)
  if (!page || !lesson.value?.beats?.length) return
  const idx = lesson.value.beats.findIndex((item: { page?: number }) => Number(item.page) === page)
  if (idx >= 0) beatIndex.value = idx
}

function nextAfterQuiz() {
  const isPhrase = step.value === 'phrase'
  const alreadyDone = isPhrase ? phraseDone.value : vocabDone.value
  if (quizHadWrong.value && !alreadyDone) {
    if (isPhrase) phraseRetries.value += 1
    else vocabRetries.value += 1
    quizSeed.value += 1
    startStep()
    return
  }
  if (!alreadyDone) {
    if (isPhrase) {
      phraseDone.value = true
      saveProgress({ phrase_done: true, phrase_retries: phraseRetries.value })
    } else {
      vocabDone.value = true
      saveProgress({ vocab_done: true, vocab_retries: vocabRetries.value })
    }
  }
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
  if (needRecord.value && !recordDone.value) {
    if (!/失败/.test(uploadHint.value)) {
      uploadHint.value = '跳过不计入完成度，但至少要录成功一段才能翻页'
    }
    return
  }
  closeActivity()
  if (pageTasksReady.value && !lastBeat.value) nextPage()
}

async function startRecord() {
  stopAudio()
  lastScore.value = null
  lastHeard.value = ''
  scoreError.value = ''
  passed.value = false
  uploadHint.value = ''
  clearPassTimer()
  sound.recStart()
  pageRecorder = await recordPageClip(beat.value.image, {
    cameraStream: camera.liveVideoTrack() ? camera.stream.value : null,
    avatar: user.avatar,
    nickname: user.nickname,
  })
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
    const asrSource = clip.asrBlob && clip.asrBlob.size > 1000 ? clip.asrBlob : clip.blob
    const heard = await Promise.race([
      recognizeAudio(asrSource, 'en'),
      new Promise<string>((_, reject) => {
        window.setTimeout(() => reject(new Error('评分超时，请再读一次')), 45000)
      }),
    ])
    const result = scoreEnglish(currentSeg.value, heard)
    lastScore.value = result.score
    lastHeard.value = result.heard
    passed.value = result.score >= PASS_SCORE
    busy.value = false
    if (passed.value) {
      if (lastSegment.value && lastBeat.value) sound.bigCelebrate()
      else sound.celebrate()
      pageClips.value = [...pageClips.value, { ...clip, score: result.score }]
      clearPassTimer()
      if (lastSegment.value) await flushPageRecording()
      passTimer = window.setTimeout(advanceSegment, lastSegment.value ? 800 : 1600)
    } else {
      sound.fail()
    }
  } catch (err) {
    sound.fail()
    scoreError.value = err instanceof Error ? err.message : '评分失败'
  } finally {
    busy.value = false
  }
}

function waitMergeChoice() {
  return new Promise<'skip' | 'upload'>((resolve) => {
    mergeChoice = resolve
  })
}

function pickMerge(value: 'skip' | 'upload') {
  const resolve = mergeChoice
  mergeChoice = null
  resolve?.(value)
}

function showAskUpload() {
  mergePhase.value = 'ask-upload'
  mergeTitle.value = '本页朗读已保存在本地'
  mergeHint.value = '要上传到云端吗？勾选后会同时公开到广场，之后也可在视频详情页更改。'
}

function askDiscardVideo() {
  mergePhase.value = 'ask-discard'
  mergeTitle.value = '确定舍弃这段视频？'
  mergeHint.value = '舍弃后不会上传到云端，本页朗读进度仍会保留。'
}

function closeMergeDialog() {
  if (mergePhase.value === 'ask-discard') {
    showAskUpload()
    return
  }
  if (mergeChoice) pickMerge('skip')
  mergeOpen.value = false
  mergeFailed.value = false
  mergePhase.value = 'working'
}

async function flushPageRecording() {
  if (!pageClips.value.length || !beat.value || flushingPage) return
  flushingPage = true
  mergeFailed.value = false
  mergePhase.value = 'working'
  mergeOpen.value = true
  mergeTitle.value = '正在合成视频'
  mergeHint.value = '多段朗读合成成片需要一点时间，请稍候'
  mergePercent.value = 0
  try {
    uploadHint.value = '正在合并本页朗读…'
    const merged = await concatClips(pageClips.value, ({ percent, text }) => {
      mergeTitle.value = '正在合成视频'
      mergeHint.value = text
      mergePercent.value = percent
    })
    merged.score = Math.round(pageClips.value.reduce((sum, item) => sum + item.score, 0) / pageClips.value.length)
    pageClips.value = []
    recordDone.value = true
    saveProgress({ record_done: true, record_score: merged.score })
    if (user.isGuest) {
      uploadHint.value = '本页朗读已保存在本地'
      mergeTitle.value = '合成完成'
      mergeHint.value = '本页朗读已保存在本地'
      mergePercent.value = 100
      await sleep(400)
      return
    }
    const saved = await saveReadingLocal({
      clip: merged,
      seriesId: String(route.params.seriesId),
      bookSlug: String(route.params.bookSlug),
      bookTitle: String(lesson.value?.title_zh || lesson.value?.title || ''),
      chapterId: String(route.params.chapterId),
      page: beat.value.page,
      onProgress: (text) => {
        uploadHint.value = text
        mergeTitle.value = '正在保存'
        mergeHint.value = text
        mergePercent.value = Math.max(mergePercent.value, 92)
      },
    })
    uploadHint.value = '本页朗读已保存在本地'
    mergePercent.value = 100
    if (!saved.canCloud) {
      mergeTitle.value = '合成完成'
      mergeHint.value = '本页朗读已保存在本地'
      await sleep(400)
      return
    }
    sharePublic.value = false
    showAskUpload()
    const uploadPick = await waitMergeChoice()
    if (uploadPick !== 'upload') {
      uploadHint.value = '本页朗读已保存在本地'
      return
    }
    mergePhase.value = 'uploading'
    mergeTitle.value = '正在上传'
    mergeHint.value = '正在上传到云端…'
    const uploaded = await uploadReadingCloud({
      id: saved.id,
      clip: merged,
      isPublic: sharePublic.value,
      onProgress: (text) => {
        uploadHint.value = text
        mergeTitle.value = '正在上传'
        mergeHint.value = text
        const m = text.match(/(\d+)\s*%/)
        mergePercent.value = m ? Number(m[1]) : Math.max(mergePercent.value, 92)
      },
    })
    mergePercent.value = 100
    uploadHint.value = uploaded.isPublic ? '已公开到广场' : '已上传，仅自己可见'
  } catch (err) {
    sound.fail()
    const msg = err instanceof Error ? err.message : '保存失败'
    uploadHint.value = msg
    mergeTitle.value = mergePhase.value === 'uploading' ? '上传失败' : '合成失败'
    mergeHint.value = msg
    mergeFailed.value = true
    mergePhase.value = 'failed'
  } finally {
    flushingPage = false
    if (!mergeFailed.value) {
      mergeOpen.value = false
      mergePhase.value = 'working'
    }
  }
}

function goBack() {
  router.back()
}

function lessonApiPath() {
  return `/api/lessons/${route.params.seriesId}/${route.params.bookSlug}/${route.params.chapterId}`
}

function cdnPageImage(page: number) {
  return `/media/cdn/${route.params.seriesId}/${route.params.bookSlug}/${page}.jpg`
}

function emptyBeat(page: number) {
  return {
    page,
    image: cdnPageImage(page),
    english: '',
    translate: '',
    explain: '',
    generated: false,
    words: [],
    phrases: [],
    segments: [],
    word_items: [],
    phrase_items: [],
    ocr: [],
  }
}

function showStubPage(page: number) {
  data.value = {
    lesson: {
      chapter: 1,
      title: '',
      title_zh: '',
      beats: [emptyBeat(page)],
      word_bank: [],
      phrase_bank: [],
    },
  }
  beatIndex.value = 0
}

function beatNeedsLesson(row: { english?: string; generated?: boolean; explain?: string } | null | undefined) {
  if (!row) return false
  if (!String(row.english || '').trim()) return false
  if (row.generated) return false
  if (String(row.explain || '').trim()) return false
  return true
}

async function requestPageLesson(page: number, gen: number) {
  const path = lessonApiPath()
  explainBusy.value = true
  explainBusyError.value = ''
  try {
    const job = (await apiPost(`${path}/generate?page=${page}`)) as { exists?: boolean; job_id?: string }
    if (job?.job_id && !job.exists) await waitJobResult(job.job_id)
  } catch (err) {
    if (gen === pagePrepGen) {
      explainBusyError.value = pageHasStoryText.value
        ? '讲解还没准备好，过一会儿再听。'
        : '这一页没有文字，看看图就好。'
    }
    throw err
  } finally {
    if (gen === pagePrepGen) explainBusy.value = false
  }
}

async function refreshLesson() {
  const page = Number(beat.value?.page ?? route.query.page)
  data.value = await api(lessonApiPath())
  if (Number.isFinite(page)) {
    const idx = (data.value?.lesson?.beats || []).findIndex(
      (item: { page?: number }) => Number(item.page) === page,
    )
    if (idx >= 0) beatIndex.value = idx
  }
}

async function requestNextPageLesson() {
  const next = lesson.value?.beats?.[beatIndex.value + 1]
  if (!next || !beatNeedsLesson(next)) return
  const page = Number(next.page)
  if (!Number.isFinite(page)) return
  try {
    await apiPost(`${lessonApiPath()}/generate?page=${page}`)
  } catch {
    /* 下一页预生成失败不影响本页 */
  }
}

async function prepareOpenedPage() {
  const gen = ++pagePrepGen
  explainBusy.value = false
  explainBusyError.value = ''
  await nextTick()
  if (gen !== pagePrepGen) return
  const current = beat.value
  if (!current) return
  if (beatNeedsLesson(current)) {
    try {
      await requestPageLesson(Number(current.page), gen)
    } catch {
      /* 没有文字或讲解未就绪时仍展示本页 */
    }
    if (gen !== pagePrepGen) return
    await refreshLesson()
    if (gen !== pagePrepGen) return
  }
  await Promise.all([loadPageOcr(), loadPageProgress()])
  if (gen !== pagePrepGen) return
  startStep()
  saveCursor()
  void requestNextPageLesson()
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
  pageOcr.value = []
  overlay.value = []
  beatIndex.value = index
  step.value = 'explain'
  void prepareOpenedPage()
}

async function loadPageOcr() {
  const current = beat.value
  const page = Number(current?.page || 0)
  if (!current || !Number.isFinite(page)) {
    pageOcr.value = []
    return
  }
  const key = `${route.params.seriesId}/${route.params.bookSlug}/${page}`
  const fromBeat = (current.ocr || []) as Box[]
  if (fromBeat.length) {
    pageOcrCache.set(key, fromBeat)
    pageOcr.value = fromBeat
    return
  }
  const cached = pageOcrCache.get(key)
  if (cached?.length) {
    pageOcr.value = cached
    return
  }
  try {
    const q = new URLSearchParams({
      series_id: String(route.params.seriesId || ''),
      book_slug: String(route.params.bookSlug || ''),
      page: String(page),
    })
    const row = await api(`/api/ocr/page?${q}`)
    const boxes = (row?.ocr || []) as Box[]
    if (boxes.length) pageOcrCache.set(key, boxes)
    pageOcr.value = boxes
  } catch {
    pageOcr.value = []
  }
}

async function loadPageProgress() {
  const page = Number(beat.value?.page || 0)
  if (!page) {
    vocabDone.value = false
    phraseDone.value = false
    recordDone.value = false
    vocabRetries.value = 0
    phraseRetries.value = 0
    return
  }
  try {
    const q = new URLSearchParams({
      series_id: String(route.params.seriesId || ''),
      book_slug: String(route.params.bookSlug || ''),
      chapter_id: String(route.params.chapterId || ''),
      page: String(page),
    })
    const row = await api(`/api/progress/page?${q}`)
    vocabDone.value = !!row?.vocabDone
    phraseDone.value = !!row?.phraseDone
    recordDone.value = !!row?.recordDone
    vocabRetries.value = Number(row?.vocabRetries || 0)
    phraseRetries.value = Number(row?.phraseRetries || 0)
  } catch {
    vocabDone.value = false
    phraseDone.value = false
    recordDone.value = false
    vocabRetries.value = 0
    phraseRetries.value = 0
  }
}

function prevPage() {
  goToBeat(beatIndex.value - 1)
}

function nextPage() {
  goToBeat(beatIndex.value + 1)
}

function clickSentence(i: number) {
  if (step.value !== 'explain') return
  void playExplain(i)
}

function pauseFlow() {
  sound.dismiss()
  closeActivity()
}

async function toggleCamera() {
  if (camera.enabled.value || camera.starting.value) {
    camera.close()
    return
  }
  await camera.start()
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

watch(recordBarOpen, (open) => {
  setAssistantExtraBottom(open ? 96 : 0)
  if (open) void camera.start()
  else camera.stop()
})

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
  const initialPage = Number(route.query.page || 1) || 1
  showStubPage(initialPage)
  await nextTick()
  data.value = await api(lessonApiPath())
  applyResumePage()
  await prepareOpenedPage()
})

onUnmounted(() => {
  clearQuizTimer()
  clearPassTimer()
  clearRecordTimer()
  if (recording.value) stopRecord()
  if (mergeChoice) pickMerge('skip')
  camera.stop()
  setAssistantExtraBottom(0)
  stopAskStream()
  stopAudio()
})
</script>

<template>
  <div
    v-if="lesson && beat"
    class="flex h-full min-h-0 flex-col overflow-hidden"
    :class="recordBarOpen ? 'pb-24' : 'pb-[env(safe-area-inset-bottom)]'"
  >
    <div class="fixed left-1/2 top-1.5 z-[90] flex -translate-x-1/2 items-center gap-1.5 lg:top-2 lg:gap-2">
      <button
        class="rounded-full bg-white/90 px-2.5 py-1.5 text-xs font-extrabold text-brand-700 shadow-pop lg:px-4 lg:py-2 lg:text-sm"
        type="button"
        @click="goBack"
      >
        返回
      </button>
      <button
        class="rounded-full bg-white/90 px-2.5 py-1.5 text-xs font-extrabold text-brand-700 shadow-pop disabled:opacity-40 lg:px-4 lg:py-2 lg:text-sm"
        type="button"
        :disabled="firstBeat"
        @click="prevPage"
      >
        上一页
      </button>
      <button
        class="rounded-full bg-white/90 px-2.5 py-1.5 text-xs font-extrabold text-brand-700 shadow-pop disabled:opacity-40 lg:px-4 lg:py-2 lg:text-sm"
        type="button"
        :disabled="lastBeat"
        @click="nextPage"
      >
        下一页
      </button>
    </div>
    <div class="flex min-h-0 flex-1 flex-row gap-2 overflow-hidden lg:gap-3">
    <section class="relative min-h-0 min-w-0 flex-1">
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
        class="btn-candy absolute bottom-2 left-2 right-2 z-10 max-lg:py-2 max-lg:text-sm"
        type="button"
        @click="resumeFlow"
      >
        继续{{ stepLabel }}
      </button>
    </section>

    <aside class="flex h-full min-h-0 w-[min(22.5rem,40vw)] shrink-0 flex-col space-y-2 overflow-y-auto overscroll-contain [-webkit-overflow-scrolling:touch] lg:w-[360px] lg:space-y-3">
        <p class="truncate text-base font-extrabold text-brand-700">
          {{ lesson.title_zh }} · 第 {{ beat.page }} 页 · {{ beatIndex + 1 }}/{{ lesson.beats.length }}
        </p>
        <section class="card space-y-2 p-3 lg:space-y-3 lg:p-5">
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-1.5">
              <p class="text-[11px] font-extrabold uppercase tracking-wide text-brand-600 lg:text-xs">讲解</p>
              <button
                class="grid h-7 w-7 place-items-center rounded-full bg-brand-100 text-sm font-black text-brand-700 shadow-sm"
                type="button"
                :title="explainPlaying && !explainPaused ? '暂停' : '播放'"
                @click="toggleExplainPlay"
              >
                {{ explainPlaying && !explainPaused ? '⏸' : '▶' }}
              </button>
              <button
                class="grid h-7 w-7 place-items-center rounded-full bg-white text-sm font-black text-brand-600 shadow-sm"
                type="button"
                title="重新开始"
                @click="restartExplain"
              >
                ↻
              </button>
            </div>
            <label class="flex items-center gap-1 text-[11px] font-bold text-brand-600/70 lg:text-xs">
              句间停
              <input
                v-model.number="gapSec"
                class="w-11 rounded-xl border border-brand-200 bg-white px-1.5 py-0.5 font-bold text-brand-700 lg:w-14 lg:px-2 lg:py-1"
                type="number"
                min="0"
                max="5"
                step="0.5"
              />
              秒
            </label>
          </div>
          <p v-if="explainWaitingTts" class="text-[11px] font-bold text-brand-600/70 lg:text-xs">
            正在等待朗读...
          </p>
          <div class="space-y-2 pr-1 max-lg:max-h-none lg:max-h-[42vh] lg:overflow-y-auto">
            <div
              v-if="explainBusy"
              class="rounded-2xl bg-sunny/80 px-3 py-2 font-bold leading-7 text-brand-700"
            >
              你是第一个读这页的人，正在生成讲解，请稍等。
              <p class="mt-1 text-sm font-bold text-brand-600/70">生成后会保存，后面的人不用再等。</p>
            </div>
            <p
              v-else-if="explainHint"
              class="rounded-2xl bg-brand-50 px-3 py-2 text-sm font-bold leading-7 text-brand-600/80"
            >
              {{ explainHint }}
            </p>
            <template v-else>
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
            </template>
          </div>
          <div class="grid grid-cols-2 gap-1.5 lg:gap-2">
            <button class="btn-ghost w-full max-lg:px-2 max-lg:py-2 max-lg:text-xs" type="button" @click="restartExplain">再听一遍</button>
            <button
              class="btn-primary w-full max-lg:px-2 max-lg:py-2 max-lg:text-xs"
              type="button"
              :disabled="!vocabQs.length"
              @click="startActivity('vocab')"
            >
              {{ vocabDone ? '单词已过 ✓' : '复习单词' }}
            </button>
            <button
              class="btn-primary w-full max-lg:px-2 max-lg:py-2 max-lg:text-xs disabled:cursor-not-allowed"
              type="button"
              :disabled="!phraseQs.length"
              @click="startActivity('phrase')"
            >
              {{ phraseDone ? '短语已过 ✓' : '复习短语' }}
            </button>
            <button
              class="btn-candy w-full max-lg:px-2 max-lg:py-2 max-lg:text-xs disabled:cursor-not-allowed"
              type="button"
              :disabled="!needRecord"
              @click="startActivity('record')"
            >
              {{ recordDone ? '朗读已录 ✓' : '自主朗读' }}
            </button>
          </div>
        </section>

        <section class="card space-y-2 p-3 lg:space-y-3 lg:p-5">
          <p class="text-sm font-extrabold text-brand-700 lg:text-base">这一页重点</p>
          <div>
            <p class="mb-1 text-[11px] font-extrabold text-brand-500 lg:mb-2 lg:text-xs">词</p>
            <div class="flex flex-wrap gap-1 lg:gap-2">
              <button
                v-for="w in beat.word_items"
                :key="w.en"
                type="button"
                class="chip bg-brand-100 text-brand-700 transition hover:bg-brand-200 max-lg:px-2 max-lg:py-0.5 max-lg:text-xs"
                @click="openFocus(w)"
              >
                {{ w.en }}
              </button>
            </div>
          </div>
          <div>
            <p class="mb-1 text-[11px] font-extrabold text-brand-500 lg:mb-2 lg:text-xs">短语</p>
            <div class="flex flex-wrap gap-1 lg:gap-2">
              <button
                v-for="p in beat.phrase_items"
                :key="p.en"
                type="button"
                class="chip bg-sky/15 text-brand-700 transition hover:bg-sky/25 max-lg:px-2 max-lg:py-0.5 max-lg:text-xs"
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
      draggable
      @close="pauseFlow"
    >
      <template v-if="currentQuestion">
        <div class="mb-2 flex items-center justify-between lg:mb-4">
          <span class="chip bg-brand-100 text-brand-700 max-lg:px-2 max-lg:py-0.5 max-lg:text-xs">第 {{ quizCursor + 1 }} / {{ currentQuiz.length }} 题</span>
          <button class="text-xs font-bold text-brand-600 lg:text-sm" type="button" @click="playOne(currentQuestion.item.en)">
            🔊 听单词
          </button>
        </div>
        <p class="mb-0.5 text-center text-[11px] font-bold text-brand-600/70 lg:mb-1 lg:text-xs">
          有错要整轮重来，全对才算过
          <span v-if="(step === 'phrase' ? phraseRetries : vocabRetries) > 0">
            · 已重试 {{ step === 'phrase' ? phraseRetries : vocabRetries }} 次
          </span>
        </p>
        <p class="mb-2 text-center text-lg font-extrabold leading-snug text-brand-700 lg:mb-4 lg:text-3xl">{{ currentQuestion.item.en }}</p>
        <div class="flex flex-col gap-1.5 lg:gap-2">
          <button
            v-for="opt in currentQuestion.options"
            :key="opt.key"
            type="button"
            class="flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-left text-sm font-bold transition active:scale-95 lg:gap-3 lg:rounded-2xl lg:px-4 lg:py-3 lg:text-lg"
            :class="optionClass(opt)"
            :disabled="celebrating || (wrongKeys[quizCursor] || []).includes(opt.key)"
            @click="pickOption(opt.key)"
          >
            <span
              class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-extrabold lg:h-8 lg:w-8 lg:text-base"
              :class="(celebrating && opt.ok) || (wrongKeys[quizCursor] || []).includes(opt.key) ? 'bg-white/25' : 'bg-brand-100 text-brand-700'"
            >{{ opt.key }}</span>
            <span>{{ opt.text }}</span>
          </button>
        </div>
        <p class="mt-2 h-4 text-center text-[11px] font-bold leading-4 text-candy lg:mt-auto lg:h-5 lg:text-xs lg:leading-5">
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
          <div class="card animate-pop-in px-6 py-5 text-center shadow-pop sm:px-10 sm:py-8">
            <p class="text-5xl sm:text-6xl">{{ quizNeedRetry ? '🔁' : '🎉' }}</p>
            <p class="mt-2 text-xl font-extrabold sm:mt-3 sm:text-2xl" :class="quizNeedRetry ? 'text-candy' : 'text-mint'">
              {{ quizNeedRetry ? '这轮有错，再来一遍' : '答对了！' }}
            </p>
          </div>
        </div>
      </transition>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="mergeOpen"
        class="fixed inset-0 z-[90] flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm"
      >
        <div class="card w-full max-w-md px-6 py-6 shadow-pop" role="dialog" aria-modal="true" aria-live="polite">
          <p class="text-center text-4xl">{{ mergeFailed ? '😵' : mergePhase === 'ask-discard' ? '🗑️' : mergePhase === 'ask-upload' ? '☁️' : '🎬' }}</p>
          <h2 class="mt-3 text-center text-xl font-extrabold text-brand-700">{{ mergeTitle }}</h2>
          <p class="mt-2 text-center text-sm font-bold text-brand-700/70">{{ mergeHint }}</p>
          <div v-if="mergePhase === 'working' || mergePhase === 'uploading' || mergeFailed" class="mt-5 h-3 overflow-hidden rounded-full bg-brand-100">
            <div
              class="h-full rounded-full transition-all duration-300"
              :class="mergeFailed ? 'bg-candy' : 'bg-sunny'"
              :style="{ width: `${mergePercent}%` }"
            />
          </div>
          <p
            v-if="mergePhase === 'working' || mergePhase === 'uploading' || mergeFailed"
            class="mt-2 text-center text-lg font-black tabular-nums text-brand-700"
          >
            {{ mergePercent }}%
          </p>
          <button
            v-if="mergeFailed"
            class="btn-primary mt-5 w-full"
            type="button"
            @click="closeMergeDialog"
          >
            知道了
          </button>
          <div v-else-if="mergePhase === 'ask-upload'" class="mt-5 flex flex-col gap-2">
            <label class="flex items-center gap-2 rounded-2xl bg-brand-50 px-3 py-2 text-sm font-bold text-brand-700">
              <input v-model="sharePublic" class="h-4 w-4 accent-brand-500" type="checkbox" />
              上传后公开到广场
            </label>
            <button class="btn-primary w-full" type="button" @click="pickMerge('upload')">上传到云端</button>
            <button class="btn-ghost w-full" type="button" @click="askDiscardVideo">舍弃视频</button>
          </div>
          <div v-else-if="mergePhase === 'ask-discard'" class="mt-5 flex flex-col gap-2">
            <button class="btn-candy w-full" type="button" @click="pickMerge('skip')">确定舍弃</button>
            <button class="btn-ghost w-full" type="button" @click="showAskUpload">再想想</button>
          </div>
        </div>
      </div>
    </Teleport>

    <RecordBar
      :open="recordBarOpen"
      :recording="recording"
      :busy="busy"
      :passed="passed"
      :last-score="lastScore"
      :last-heard="lastHeard"
      :score-error="scoreError"
      :upload-hint="uploadHint"
      :record-left="recordLeft"
      :record-total="recordTotal"
      :record-words="recordWords"
      :seg-index="segIndex"
      :seg-count="pageSegments.length"
      :camera-enabled="cameraEnabled"
      :camera-starting="cameraStarting"
      :camera-error="cameraErrorText"
      :pass-text="recordPassText"
      @start="startRecord"
      @stop="stopRecord"
      @skip="advanceSegment"
      @close="pauseFlow"
      @toggle-camera="toggleCamera"
    />

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

    <UserCameraPip :book-key="bookKey" />
    <AssistantLive2dPip :visible="showAssistant" />
    <AiAskListenFab
      :visible="showAssistant"
      :listening="askListening"
      :stream="askStream"
      :disabled="askBusy || recording"
      @ask="startAsk"
      @finish="finishAsk"
    />
    <p
      v-if="showAssistant && (askError || askBusy)"
      class="pointer-events-none fixed bottom-24 left-1/2 z-[93] -translate-x-1/2 rounded-full bg-white/95 px-4 py-1.5 text-xs font-extrabold text-candy shadow-pop"
    >
      {{ askBusy ? '助教正在想…' : askError }}
    </p>
  </div>
</template>
