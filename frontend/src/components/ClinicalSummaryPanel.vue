<script setup>
import { ref } from 'vue'
import { api, formatApiError } from '../api.js'
import TaskActions from './TaskActions.vue'

const props = defineProps({ sessionId: { type: String, required: true } })
const emit = defineEmits(['changed'])

function onTaskChanged() {
  load()
  emit('changed') // closure preview and audit trail elsewhere on the page
}

const summary = ref(null)
const error = ref(null)
const loading = ref(false)
const draft = ref(null)
const drafting = ref(false)

async function load() {
  loading.value = true
  error.value = null
  try {
    summary.value = await api.getClinicalSummary(props.sessionId)
  } catch (e) {
    error.value = formatApiError(e)
  } finally {
    loading.value = false
  }
}

async function makeDraft() {
  drafting.value = true
  draft.value = null
  try {
    draft.value = await api.draftClinicalSummary(props.sessionId)
  } catch (e) {
    draft.value = { available: false, reason: formatApiError(e) }
  } finally {
    drafting.value = false
  }
}

function when(iso) {
  return new Date(iso).toLocaleString()
}

function enteredVia(via) {
  if (!via) return ''
  if (via.startsWith('LLM-001')) return ' · AI interview'
  if (via.startsWith('demo API')) return ' · manual entry'
  return ` · ${via}`
}

function sourceLine(s) {
  const who = s.speaker === 'PATIENT' ? 'Patient' : s.source_type
  return `${who}, ${when(s.recorded_at)}${enteredVia(s.entered_via)}`
}

// Patients are quoted verbatim; a record or system source has no words of
// its own (its original_text is just the concept label), so show what it recorded.
function sourceText(s) {
  if (s.speaker === 'PATIENT') return `“${s.said}” — ${s.answer}${s.value ? ` (${s.value})` : ''}`
  return `Recorded: ${s.answer}${s.value ? ` (${s.value})` : ''}`
}

defineExpose({ load })
load()
</script>

<template>
  <section class="card clinical">
    <div class="title-row">
      <h2>Pre-op summary</h2>
      <button class="secondary" :disabled="loading" @click="load">Refresh</button>
    </div>

    <p v-if="error" class="alert alert-error">{{ error }}</p>

    <template v-if="summary">
      <p class="alert alert-block banner">
        <strong>Not reviewed by a clinician.</strong> Gathered by an AI interviewer; findings are
        patient-reported unless marked otherwise. Generated {{ when(summary.generated_at) }} ·
        closure {{ summary.closure_outcome.replaceAll('_', ' ').toLowerCase() }}.
      </p>
      <p class="counts">
        {{ summary.counts.answered }} answered · {{ summary.counts.positives }} positive ·
        {{ summary.counts.negatives }} denied · {{ summary.counts.unsure }} unsure ·
        {{ summary.counts.conflicting }} conflicting · {{ summary.counts.not_applicable }} not applicable ·
        {{ summary.counts.unanswered_mandatory }} mandatory still unanswered
      </p>

      <h3>Needs attention</h3>
      <p v-if="!summary.attention.length" class="hint">Nothing flagged.</p>
      <ul v-else class="attention">
        <li v-for="(a, i) in summary.attention" :key="i" :class="a.severity.toLowerCase()">
          <span class="chip">{{ a.severity }}</span>
          <strong>{{ a.title }}</strong>
          <div class="detail">{{ a.detail }}</div>
          <ul v-if="a.sources.length" class="sources">
            <li v-for="s in a.sources" :key="s.assertion_id">
              {{ sourceText(s) }}
              <span class="muted">· {{ sourceLine(s) }}</span>
            </li>
          </ul>
          <TaskActions v-if="a.task_id" :session-id="sessionId" :item="a" @changed="onTaskChanged" />
        </li>
      </ul>

      <template v-if="summary.review_flags.length">
        <h3>Flagged for review ({{ summary.review_flags.length }})</h3>
        <ul class="attention">
          <li v-for="f in summary.review_flags" :key="f.task_id" class="moderate">
            <strong>{{ f.title }}</strong>
            <div class="detail">{{ f.detail }}</div>
            <TaskActions :session-id="sessionId" :item="f" @changed="onTaskChanged" />
          </li>
        </ul>
      </template>

      <h3>Safety-critical findings</h3>
      <p v-if="!summary.safety_findings.length" class="hint">None reported.</p>
      <ul v-else class="findings">
        <li v-for="f in summary.safety_findings" :key="f.concept_id">
          <strong>{{ f.concept }}:</strong> {{ f.answer }}
          <span class="muted">({{ f.verification }})</span>
        </li>
      </ul>

      <h3>By system</h3>
      <p v-if="!summary.domains.length" class="hint">No answers yet.</p>
      <div v-for="d in summary.domains" :key="d.domain" class="domain">
        <h4>{{ d.domain }}</h4>
        <ul class="findings">
          <li v-for="f in [...d.conflicting, ...d.positives, ...d.unsure]" :key="f.concept_id">
            <details>
              <summary>
                <strong>{{ f.concept }}:</strong> {{ f.answer }}
                <span v-if="f.detail">— {{ f.detail }}</span>
                <span class="muted">({{ f.verification }})</span>
              </summary>
              <ul class="sources">
                <li v-for="s in f.sources" :key="s.assertion_id">
                  {{ sourceText(s) }} <span class="muted">· {{ sourceLine(s) }}</span>
                </li>
              </ul>
            </details>
          </li>
        </ul>
        <p v-if="d.negatives.length" class="denies">
          <span class="muted">Denies:</span> {{ d.negatives.map((f) => f.concept).join(', ') }}
        </p>
      </div>

      <details v-if="summary.unanswered_mandatory.length" class="collapsible">
        <summary>Mandatory questions still unanswered ({{ summary.unanswered_mandatory.length }})</summary>
        <p class="hint">{{ summary.unanswered_mandatory.map((u) => u.concept).join(', ') }}</p>
      </details>
      <details v-if="summary.not_applicable.length" class="collapsible">
        <summary>Not applicable — skipped by the approved skip map ({{ summary.not_applicable.length }})</summary>
        <ul class="findings">
          <li v-for="n in summary.not_applicable" :key="n.concept_id">
            {{ n.concept }} <span class="muted">— because {{ n.because.join('; ') }}</span>
          </li>
        </ul>
      </details>

      <h3>Handover note</h3>
      <button :disabled="drafting" @click="makeDraft">
        {{ drafting ? 'Drafting…' : 'Draft handover note with AI' }}
      </button>
      <div v-if="draft" class="draft">
        <template v-if="draft.available">
          <p class="draft-label">{{ draft.label }} · {{ draft.model }}</p>
          <p v-for="(para, i) in draft.narrative.split(/\n+/)" :key="i">{{ para }}</p>
        </template>
        <p v-else class="hint">
          Draft not available: {{ draft.reason }}. The structured summary above is the record.
        </p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.banner {
  font-size: 0.85rem;
}
.counts {
  font-size: 0.85rem;
  color: var(--muted);
}
h3 {
  margin: 1.1rem 0 0.4rem;
  font-size: 1rem;
}
h4 {
  margin: 0.7rem 0 0.2rem;
  font-size: 0.9rem;
  color: var(--text-h);
}
ul {
  margin: 0;
  padding-left: 1.1rem;
}
.attention {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.attention > li {
  border-left: 4px solid var(--border);
  padding: 0.4rem 0.6rem;
  background: var(--bg);
}
.attention > li.critical {
  border-left-color: var(--error-fg);
  background: var(--error-bg);
}
.attention > li.high {
  border-left-color: var(--block-fg);
  background: var(--block-bg);
}
.attention > li.moderate {
  border-left-color: var(--accent);
}
.chip {
  font-size: 0.7rem;
  font-weight: 700;
  margin-right: 0.4rem;
}
.detail {
  font-size: 0.85rem;
  margin-top: 0.2rem;
}
.sources {
  font-size: 0.8rem;
  margin-top: 0.25rem;
}
.findings li {
  margin: 0.15rem 0;
}
.findings summary {
  cursor: pointer;
}
.muted {
  color: var(--muted);
  font-size: 0.8rem;
}
.denies {
  font-size: 0.85rem;
  margin: 0.25rem 0 0;
}
.collapsible {
  margin-top: 0.8rem;
}
.collapsible > summary {
  cursor: pointer;
  font-weight: 600;
}
.draft {
  margin-top: 0.6rem;
  padding: 0.6rem 0.8rem;
  border: 1px dashed var(--accent);
  border-radius: 0.5rem;
}
.draft-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--accent);
  margin: 0 0 0.3rem;
}
.secondary {
  background: var(--card-bg);
  color: var(--text);
  border: 1px solid var(--border);
}
</style>
