<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    total: number
    page: number
    pageSize: number
  }>(),
  { pageSize: 12 },
)
const emit = defineEmits<{ change: [page: number] }>()

const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const numbers = computed(() => {
  const start = Math.max(1, Math.min(props.page - 2, pages.value - 4))
  const end = Math.min(pages.value, start + 4)
  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
})

function go(target: number) {
  if (target >= 1 && target <= pages.value && target !== props.page) emit('change', target)
}
</script>

<template>
  <nav v-if="total > pageSize" class="flex items-center justify-center gap-1 pt-3" aria-label="分页">
    <button class="btn-ghost px-3 py-1.5 text-sm disabled:opacity-40" :disabled="page <= 1" @click="go(page - 1)">
      上一页
    </button>
    <button
      v-for="n in numbers"
      :key="n"
      class="grid h-8 min-w-8 place-items-center rounded-lg px-2 text-sm font-bold"
      :class="n === page ? 'bg-brand-500 text-white' : 'bg-white text-brand-600 hover:bg-brand-50'"
      @click="go(n)"
    >
      {{ n }}
    </button>
    <button class="btn-ghost px-3 py-1.5 text-sm disabled:opacity-40" :disabled="page >= pages" @click="go(page + 1)">
      下一页
    </button>
  </nav>
</template>
