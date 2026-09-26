<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api.js'

const props = defineProps({ sessionId: { type: String, required: true } })
const emit = defineEmits(['added'])

const concepts = ref([])
const search = ref('')
const busy = ref(false)
const error = ref(null)

const form = reactive({
  concept_code: '',
  value: '',
  assertion_state: 'AFFIRMED',
  source_type: 'PATIENT',
  speaker: 'PATIENT',
})

onMounted(async () => {
  concepts.value = await api.listConcepts()
})

const filteredConcepts = computed(() => {
  if (!search.value) return concepts.value.slice(0, 25)
  const q = search.value.toLowerCase()
  return concepts.value
    .filter(
      (c) =>
        c.concept_id.toLowerCase().includes(q) ||
        c.concept.toLowerCase().includes(q) ||
        c.domain.toLowerCase().includes(q),
    )
    .slice(0, 25)
})

const selectedConcept = computed(() =>
  concepts.value.find((c) => c.concept_id === form.concept_code),
)

async function submit() {
  if (!form.concept_code) return
  busy.value = true
  error.value = null
  try {
    const summary = await api.addAssertion(props.sessionId, {
      concept_code: form.concept_code,
      value: form.value || null,
      assertion_state: form.assertion_state,
      source_type: form.source_type,
      speaker: form.speaker,
    })
    emit('added', summary)
    form.value = ''
  } catch (e) {
    error.value = e.body?.detail ?? e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="card">
    <h2>2. Add an assertion</h2>
    <p class="hint">
      Demo shortcut (see repo README / periop_api docstring): in the real
      system this only ever comes from validated LLM extraction over a
      patient turn, never a direct form. Try adding <em>ALL-003</em> as
      AFFIRMED from PATIENT, then again as NEGATED from EMR, to see a
      safety-critical conflict appear below.
    </p>

    <div class="form-grid">
      <label class="wide">
        Concept
        <input v-model="search" placeholder="search by ID, domain or name…" />
        <select v-model="form.concept_code" size="6">
          <option v-for="c in filteredConcepts" :key="c.concept_id" :value="c.concept_id">
            [{{ c.requirement_class }}] {{ c.concept_id }} — {{ c.domain }} / {{ c.concept }}
          </option>
        </select>
      </label>

      <p v-if="selectedConcept" class="hint wide">
        Patient question: “{{ selectedConcept.patient_question }}”
      </p>

      <label>
        Value / patient's words
        <input v-model="form.value" placeholder="e.g. throat swelling after penicillin" />
      </label>
      <label>
        Assertion state
        <select v-model="form.assertion_state">
          <option value="AFFIRMED">AFFIRMED</option>
          <option value="NEGATED">NEGATED</option>
          <option value="UNCERTAIN">UNCERTAIN</option>
          <option value="UNKNOWN">UNKNOWN</option>
          <option value="DECLINED">DECLINED</option>
        </select>
      </label>
      <label>
        Source type
        <input v-model="form.source_type" placeholder="PATIENT / EMR / PROXY …" />
      </label>
      <label>
        Speaker
        <select v-model="form.speaker">
          <option value="PATIENT">PATIENT</option>
          <option value="PROXY">PROXY</option>
          <option value="CLINICIAN">CLINICIAN</option>
          <option value="SYSTEM">SYSTEM</option>
        </select>
      </label>

      <button :disabled="busy || !form.concept_code" @click="submit">Add assertion</button>
    </div>

    <p v-if="error" class="alert alert-error">{{ error }}</p>
  </section>
</template>

<style scoped>
.form-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: 1fr 1fr;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  gap: 0.25rem;
}
label.wide {
  grid-column: 1 / -1;
}
select[size] {
  font-family: ui-monospace, monospace;
  font-size: 0.75rem;
}
button {
  grid-column: 1 / -1;
  justify-self: start;
}
.hint {
  font-size: 0.8rem;
  color: var(--muted);
}
</style>
