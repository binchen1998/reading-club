<script setup lang="ts">
import { ref, watch } from 'vue'

import ModeratingBusy from './ModeratingBusy.vue'
import { useUserStore } from '../stores/user'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const user = useUserStore()
const nickInput = ref('')
const bioInput = ref('')
const nickError = ref('')
const bioError = ref('')
const savingNick = ref(false)
const savingBio = ref(false)
const moderatingText = ref('正在用 AI 审核，请稍等。')

watch(
  () => props.open,
  (open) => {
    if (!open) return
    nickInput.value = user.profile?.hasCustomNickname ? user.profile.nickname : ''
    bioInput.value = user.profile?.bio || ''
    nickError.value = ''
    bioError.value = ''
  },
)

async function saveNickname() {
  const value = nickInput.value.trim()
  if (!value) {
    nickError.value = '请填写昵称'
    return
  }
  savingNick.value = true
  nickError.value = ''
  moderatingText.value = '正在用 AI 审核昵称，请稍等。'
  try {
    await user.setNickname(value)
    emit('saved')
  } catch (e: any) {
    nickError.value = e?.message || '昵称未通过审核或已被使用'
  } finally {
    savingNick.value = false
  }
}

async function saveBio() {
  savingBio.value = true
  bioError.value = ''
  moderatingText.value = '正在用 AI 审核个人介绍，请稍等。'
  try {
    await user.setBio(bioInput.value.trim())
    emit('saved')
  } catch (e: any) {
    bioError.value = e?.message || '个人介绍未通过审核'
  } finally {
    savingBio.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[120] flex items-center justify-center bg-slate-900/40 p-3"
      @click.self="emit('close')"
    >
      <div class="card max-h-[90vh] w-full max-w-md overflow-y-auto">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-extrabold text-brand-700">编辑资料</h2>
          <button type="button" class="btn-ghost px-3 py-1.5 text-sm" @click="emit('close')">关闭</button>
        </div>

        <div class="space-y-2">
          <label class="text-xs font-bold text-brand-600">公开昵称（必须唯一，提交后由 AI 审核）</label>
          <div class="flex gap-2">
            <input
              v-model="nickInput"
              maxlength="50"
              class="min-w-0 flex-1 rounded-2xl border-2 border-brand-200 px-3 py-2 text-sm font-bold outline-none focus:border-brand-400"
              placeholder="给自己起一个独一无二的昵称"
              :disabled="savingNick"
            />
            <button class="btn-primary px-4 text-sm" type="button" :disabled="savingNick" @click="saveNickname">
              {{ savingNick ? '审核中…' : '保存' }}
            </button>
          </div>
          <p v-if="nickError" class="text-sm font-bold text-candy">{{ nickError }}</p>
        </div>

        <div class="mt-4 space-y-2">
          <label class="text-xs font-bold text-brand-600">个人介绍（提交后由 AI 审核）</label>
          <textarea
            v-model="bioInput"
            maxlength="200"
            rows="3"
            class="w-full rounded-2xl border-2 border-brand-200 px-3 py-2 text-sm outline-none focus:border-brand-400"
            placeholder="介绍一下自己"
            :disabled="savingBio"
          />
          <button class="btn-primary w-full text-sm" type="button" :disabled="savingBio" @click="saveBio">
            {{ savingBio ? '审核中…' : '保存介绍' }}
          </button>
          <p v-if="bioError" class="text-sm font-bold text-candy">{{ bioError }}</p>
        </div>
      </div>
    </div>
    <ModeratingBusy :open="user.moderating" :text="moderatingText" />
  </Teleport>
</template>
