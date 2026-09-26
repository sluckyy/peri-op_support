<script setup>
import { computed, reactive, ref } from 'vue'
import { api, formatApiError } from '../api.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  summary: { type: Object, required: true },
})
const emit = defineEmits(['refresh'])

const busy = ref(false)
const error = ref(null)

async function guarded(fn) {
  busy.value = true
  error.value = null
  try {
    await fn()
    emit('refresh')
  } catch (e) {
    error.value = formatApiError(e)
  } finally {
    busy.value = false
  }
}

// ---------------------------------------------------------------- hypotheses

const hypForm = reactive({ content: '', epistemic_level: 'L2_PRAGMATIC_INTERPRETATION', confidence: '' })
const promoteForms = reactive({}) // hypothesis_id -> { grounding_evidence, target_level, has_clinician_adjudication }

function addHypothesis() {
  guarded(async () => {
    if (!hypForm.content) return
    await api.createHypothesis(props.sessionId, {
      content: hypForm.content,
      epistemic_level: hypForm.epistemic_level,
      confidence: hypForm.confidence === '' ? null : Number(hypForm.confidence),
    })
    hypForm.content = ''
  })
}

function promoteForm(hypId) {
  if (!promoteForms[hypId]) {
    promoteForms[hypId] = {
      grounding_evidence: '',
      target_level: 'L4_PATIENT_GROUNDED',
      has_clinician_adjudication: false,
    }
  }
  return promoteForms[hypId]
}

function promote(hypId) {
  guarded(async () => {
    const form = promoteForm(hypId)
    const evidence = form.grounding_evidence
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
    await api.promoteHypothesis(props.sessionId, hypId, {
      target_level: form.target_level,
      grounding_evidence: evidence,
      has_clinician_adjudication: form.has_clinician_adjudication,
    })
  })
}

// -------------------------------------------------------------------- repairs

const repairForm = reactive({
  repair_type: 'CONTRADICTION',
  description: '',
  materiality: 'MODERATE',
  status: 'OPEN',
  ai_self_repair: false,
  deferred_reason: '',
  obligation_content: '',
  obligation_priority: 'MODERATE',
  obligation_risk: 'MODERATE',
})

function addRepair() {
  guarded(async () => {
    if (!repairForm.description) return
    const payload = {
      repair_type: repairForm.repair_type,
      description: repairForm.description,
      materiality: repairForm.materiality,
      status: repairForm.status,
      ai_self_repair: repairForm.ai_self_repair,
    }
    if (repairForm.status === 'DEFERRED') {
      payload.deferred_reason = repairForm.deferred_reason
      payload.create_obligation = {
        content: repairForm.obligation_content || `Follow up: ${repairForm.description}`,
        source: 'demo-ui',
        priority: repairForm.obligation_priority,
        risk: repairForm.obligation_risk,
      }
    }
    await api.createRepair(props.sessionId, payload)
    repairForm.description = ''
    repairForm.deferred_reason = ''
    repairForm.obligation_content = ''
  })
}

function resolveRepair(repairId) {
  guarded(() => api.resolveRepair(props.sessionId, repairId))
}

// ---------------------------------------------------- psychological safety

const PS_SIGNALS = [
  ['patient_corrected_system_without_hesitation', '+ corrected system calmly'],
  ['patient_disclosed_sensitive_information', '+ disclosed sensitive info'],
  ['patient_asked_a_question', '+ asked a question'],
  ['patient_admitted_uncertainty_or_nonadherence', '+ admitted uncertainty'],
  ['system_acknowledged_its_own_error', '+ system acknowledged its error'],
  ['patient_showed_distress_when_correcting_system', '− distress when correcting'],
  ['patient_gave_minimal_deflecting_answers', '− minimal/deflecting answers'],
  ['system_error_went_unacknowledged', '− system error unacknowledged'],
]

function applySignal(name) {
  guarded(() => api.applyPsychSafetySignal(props.sessionId, [name]))
}

const psEstimate = computed(() => props.summary.psychological_safety?.estimate ?? 0.5)

// ------------------------------------------------------------------ humour

const humourForm = reactive({
  feature_enabled: false,
  proposed_target: 'self',
  receptivity_known: false,
  high_distress: false,
  conflict_present: false,
})
const humourResult = ref(null)

function checkHumour() {
  guarded(async () => {
    humourResult.value = await api.checkHumour(props.sessionId, { ...humourForm })
  })
}
</script>

<template>
  <section class="card">
    <h2>v1.1 Model Layer (§6A)</h2>
    <p class="hint">
      Conversational cognition layer: none of this is clinical truth on
      its own, and nothing here is wired to an Orchestrator yet (there
      isn't one built) &mdash; this exercises the real underlying logic
      directly.
    </p>

    <h3>Conversational hypotheses → grounded propositions</h3>
    <p class="hint">
      A hypothesis below L4 cannot be treated as fact. Promoting to
      L4+ requires grounding evidence; promoting to L6 also requires
      ticking clinician adjudication.
    </p>
    <div class="form-row">
      <input v-model="hypForm.content" placeholder="e.g. possible pulmonary embolism" />
      <select v-model="hypForm.epistemic_level">
        <option value="L0_RAW_UTTERANCE">L0 raw utterance</option>
        <option value="L1_LITERAL_INTERPRETATION">L1 literal</option>
        <option value="L2_PRAGMATIC_INTERPRETATION">L2 pragmatic</option>
        <option value="L3_CLINICAL_HYPOTHESIS">L3 clinical hypothesis</option>
      </select>
      <button :disabled="busy || !hypForm.content" @click="addHypothesis">Add hypothesis</button>
    </div>

    <ul class="stack">
      <li v-for="h in summary.hypotheses" :key="h.hypothesis_id" class="entry">
        <div class="entry-head">
          <span class="pill" :class="`hstatus-${h.status.toLowerCase()}`">{{ h.status }}</span>
          <span class="pill">{{ h.epistemic_level.split('_')[0] }}</span>
          <span>{{ h.content }}</span>
        </div>
        <div v-if="h.status === 'ACTIVE'" class="promote-form">
          <textarea
            v-model="promoteForm(h.hypothesis_id).grounding_evidence"
            rows="2"
            placeholder="grounding evidence, one per line"
          ></textarea>
          <select v-model="promoteForm(h.hypothesis_id).target_level">
            <option value="L4_PATIENT_GROUNDED">→ L4 patient-grounded</option>
            <option value="L5_EXTERNALLY_VERIFIED">→ L5 externally verified</option>
            <option value="L6_CLINICALLY_ADJUDICATED">→ L6 clinically adjudicated</option>
          </select>
          <label class="checkbox">
            <input type="checkbox" v-model="promoteForm(h.hypothesis_id).has_clinician_adjudication" />
            clinician adjudication given
          </label>
          <button :disabled="busy" @click="promote(h.hypothesis_id)">Promote</button>
        </div>
      </li>
    </ul>

    <h3>Grounded propositions ({{ summary.propositions.length }})</h3>
    <ul class="stack">
      <li v-for="p in summary.propositions" :key="p.proposition_id" class="entry">
        <span class="pill hstatus-promoted">{{ p.epistemic_level.split('_')[0] }}</span>
        {{ p.content }}
        <span class="hint">&mdash; {{ p.grounding_evidence.join('; ') }}</span>
      </li>
    </ul>

    <h3>Repair requirements</h3>
    <p class="hint">
      Deferring a repair without a linked obligation is rejected by the
      API (422) &mdash; the obligation is created inline here. An OPEN
      CRITICAL repair blocks session closure the same way an unowned
      critical task does.
    </p>
    <div class="form-grid">
      <select v-model="repairForm.repair_type">
        <option v-for="t in ['RECOGNITION','REFERENCE','SEMANTICS','TEMPORALITY','FACTUAL_ACCURACY','INTERPRETATION','CONTRADICTION','SCOPE','PRAGMATICS','INTERRUPTION','EMOTIONAL_MISATTUNEMENT']" :key="t" :value="t">{{ t }}</option>
      </select>
      <select v-model="repairForm.materiality">
        <option value="LOW">LOW</option>
        <option value="MODERATE">MODERATE</option>
        <option value="HIGH">HIGH</option>
        <option value="CRITICAL">CRITICAL</option>
      </select>
      <input v-model="repairForm.description" placeholder="what went wrong" class="wide" />
      <select v-model="repairForm.status">
        <option value="OPEN">OPEN</option>
        <option value="DEFERRED">DEFERRED (needs obligation)</option>
        <option value="HANDED_OFF">HANDED_OFF</option>
      </select>
      <label class="checkbox">
        <input type="checkbox" v-model="repairForm.ai_self_repair" /> AI self-repair
      </label>

      <template v-if="repairForm.status === 'DEFERRED'">
        <input v-model="repairForm.deferred_reason" placeholder="reason for deferring" class="wide" />
        <input v-model="repairForm.obligation_content" placeholder="obligation: what to come back to" class="wide" />
        <select v-model="repairForm.obligation_priority">
          <option value="LOW">priority: LOW</option>
          <option value="MODERATE">priority: MODERATE</option>
          <option value="HIGH">priority: HIGH</option>
          <option value="CRITICAL">priority: CRITICAL</option>
        </select>
        <select v-model="repairForm.obligation_risk">
          <option value="LOW">risk: LOW</option>
          <option value="MODERATE">risk: MODERATE</option>
          <option value="HIGH">risk: HIGH</option>
          <option value="CRITICAL">risk: CRITICAL</option>
        </select>
      </template>

      <button :disabled="busy || !repairForm.description" @click="addRepair">Log repair</button>
    </div>

    <ul class="stack">
      <li v-for="r in summary.repairs" :key="r.repair_id" class="entry">
        <span class="pill" :class="`materiality-${r.materiality.toLowerCase()}`">{{ r.materiality }}</span>
        <span class="pill">{{ r.status }}</span>
        {{ r.description }}
        <button v-if="r.status === 'OPEN'" class="inline-button" @click="resolveRepair(r.repair_id)">
          mark repaired
        </button>
      </li>
    </ul>

    <h3>Prospective obligations ({{ summary.obligations.length }})</h3>
    <ul class="stack">
      <li v-for="o in summary.obligations" :key="o.obligation_id" class="entry">
        <span class="pill">{{ o.status }}</span>
        {{ o.content }}
        <span class="hint">&mdash; priority {{ o.priority }}, risk {{ o.risk }}</span>
      </li>
    </ul>

    <h3>Psychological safety (PSt)</h3>
    <p class="hint">
      A bounded heuristic, not a validated measure &mdash; see
      periop_core.psychological_safety's docstring.
    </p>
    <div class="ps-gauge">
      <div class="ps-gauge-fill" :style="{ width: `${psEstimate * 100}%` }"></div>
    </div>
    <p>{{ (psEstimate * 100).toFixed(0) }}%</p>
    <div class="signal-buttons">
      <button v-for="[name, label] in PS_SIGNALS" :key="name" class="signal-button" :disabled="busy" @click="applySignal(name)">
        {{ label }}
      </button>
    </div>

    <h3>Humour policy check (§6A.8)</h3>
    <div class="form-row">
      <label class="checkbox"><input type="checkbox" v-model="humourForm.feature_enabled" /> feature enabled</label>
      <select v-model="humourForm.proposed_target">
        <option value="self">target: self</option>
        <option value="situation">target: situation</option>
        <option value="patient">target: patient</option>
      </select>
      <label class="checkbox"><input type="checkbox" v-model="humourForm.receptivity_known" /> receptivity known</label>
      <label class="checkbox"><input type="checkbox" v-model="humourForm.high_distress" /> high distress</label>
      <button :disabled="busy" @click="checkHumour">Check</button>
    </div>
    <div v-if="humourResult" class="alert" :class="humourResult.permitted ? 'alert-ok' : 'alert-block'">
      <strong>{{ humourResult.permitted ? 'Permitted' : 'Not permitted' }}</strong>
      <ul>
        <li v-for="r in humourResult.reasons" :key="r">{{ r }}</li>
      </ul>
    </div>

    <p v-if="error" class="alert alert-error">{{ error }}</p>
  </section>
</template>

<style scoped>
.form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.75rem;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.wide {
  grid-column: 1 / -1;
}
.stack {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem;
}
.entry {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
}
.entry-head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.promote-form {
  margin-top: 0.5rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}
.promote-form textarea {
  flex: 1 1 100%;
}
.pill {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  background: var(--border);
}
.hstatus-active {
  background: #fff3cd;
  color: #7a5b00;
}
.hstatus-promoted {
  background: #d1f7d6;
  color: #196a2b;
}
.materiality-critical,
.materiality-high {
  background: #fde0e0;
  color: #9a1c1c;
}
.materiality-moderate {
  background: #fff3cd;
  color: #7a5b00;
}
.materiality-low {
  background: #e6f0ff;
  color: #17469b;
}
.inline-button {
  margin-left: 0.5rem;
  padding: 0.15rem 0.6rem;
  font-size: 0.75rem;
}
.checkbox {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.85rem;
}
.ps-gauge {
  height: 10px;
  background: var(--border);
  border-radius: 999px;
  overflow: hidden;
  max-width: 300px;
}
.ps-gauge-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s;
}
.signal-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.5rem;
}
.signal-button {
  font-size: 0.75rem;
  padding: 0.3rem 0.6rem;
  background: var(--border);
  color: var(--text-h);
}
</style>
