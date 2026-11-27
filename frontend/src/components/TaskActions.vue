<script setup>
import { ref } from 'vue'
import { api, formatApiError } from '../api.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  item: { type: Object, required: true },
})
const emit = defineEmits(['changed'])

const resolving = ref(false)
const note = ref('')
const busy = ref(false)
const error = ref(null)

async function run(fn) {
  busy.value = true
  error.value = null
  try {
    await fn()
    resolving.value = false
    note.value = ''
    emit('changed')
  } catch (e) {
    error.value = formatApiError(e)
  } finally {
    busy.value = false
  }
}

const acknowledge = () => run(() => api.acknowledgeTask(props.sessionId, props.item.task_id))
const resolve = () => run(() => api.resolveTask(props.sessionId, props.item.task_id, note.value.trim()))
</script>

<template>
  <div class="task-actions">
    <button v-if="!item.owner" class="small" :disabled="busy" @click="acknowledge">Take ownership</button>
    <button v-if="!resolving" class="small secondary" :disabled="busy" @click="resolving = true">Resolve…</button>
    <span v-else class="resolve-row">
      <input v-model="note" placeholder="What was done (required)" @keyup.enter="note.trim() && resolve()" />
      <button class="small" :disabled="busy || !note.trim()" @click="resolve">Resolve</button>
      <button class="small secondary" :disabled="busy" @click="resolving = false">Cancel</button>
    </span>
    <span v-if="error" class="err">{{ error }}</span>
  </div>
</template>

<style scoped>
.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
  margin-top: 0.35rem;
}
.resolve-row {
  display: flex;
  gap: 0.4rem;
  flex: 1;
  min-width: 16rem;
}
.resolve-row input {
  flex: 1;
  min-width: 0;
}
.small {
  padding: 0.2rem 0.6rem;
  font-size: 0.78rem;
}
.secondary {
  background: var(--card-bg);
  color: var(--text);
  border: 1px solid var(--border);
}
.err {
  color: var(--error-fg);
  font-size: 0.8rem;
}
</style>
