<script setup>
import { computed, ref } from 'vue'
import { api } from '../api.js'

const props = defineProps({ summary: { type: Object, required: true } })
const emit = defineEmits(['refresh', 'closed'])

const busy = ref(false)
const error = ref(null)

const closureClass = computed(() => {
  const outcome = props.summary.closure_preview.outcome
  if (outcome === 'BLOCKED') return 'alert-error'
  if (outcome === 'COMPLETE_WITH_OPEN_ACTIONS') return 'alert-block'
  return 'alert-ok'
})

async function attemptClose() {
  busy.value = true
  error.value = null
  try {
    const updated = await api.closeSession(props.summary.session.session_id)
    emit('closed', updated)
  } catch (e) {
    error.value = e.body?.detail?.message ?? e.message
    emit('refresh')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="card">
    <h2>3. Live clinical state</h2>

    <h3>Working facts ({{ summary.working_facts.length }})</h3>
    <table v-if="summary.working_facts.length">
      <thead>
        <tr>
          <th>Concept</th>
          <th>Value</th>
          <th>Verification state</th>
          <th>Supporting</th>
          <th>Dissenting</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="f in summary.working_facts" :key="f.fact_id">
          <td>{{ f.concept.code }} — {{ f.concept.original_text }}</td>
          <td>{{ f.value ?? '—' }}</td>
          <td>
            <span class="pill" :class="`state-${f.verification_state.toLowerCase()}`">{{
              f.verification_state
            }}</span>
          </td>
          <td>{{ f.supporting_assertion_ids.length }}</td>
          <td>{{ f.dissenting_assertion_ids.length }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="hint">No facts yet.</p>

    <h3>Conflicts ({{ summary.conflicts.length }})</h3>
    <table v-if="summary.conflicts.length">
      <thead>
        <tr>
          <th>Type</th>
          <th>Materiality</th>
          <th>Status</th>
          <th>Auto-resolvable?</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in summary.conflicts" :key="c.conflict_id">
          <td>{{ c.type }}</td>
          <td>
            <span class="pill" :class="`materiality-${c.materiality.toLowerCase()}`">{{
              c.materiality
            }}</span>
          </td>
          <td>{{ c.status }}</td>
          <td>{{ ['LOW', 'MODERATE'].includes(c.materiality) ? 'Yes' : 'No' }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="hint">No conflicts.</p>

    <h3>Open gaps ({{ summary.gaps.filter((g) => g.gap.status === 'OPEN').length }})</h3>
    <table v-if="summary.gaps.length">
      <thead>
        <tr>
          <th>Priority</th>
          <th>Concept</th>
          <th>Gap type</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="g in summary.gaps.slice(0, 15)" :key="g.gap.gap_id">
          <td>{{ g.gap.priority_score.toFixed(2) }}</td>
          <td>{{ g.requirement_id }} — {{ g.concept }}</td>
          <td>{{ g.gap.gap_type }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="summary.gaps.length > 15" class="hint">
      + {{ summary.gaps.length - 15 }} more (showing highest priority first)
    </p>

    <h3>4. Attempt closure</h3>
    <div class="alert" :class="closureClass">
      <strong>{{ summary.closure_preview.outcome }}</strong>
      <ul v-if="summary.closure_preview.blocking_reasons.length">
        <li v-for="r in summary.closure_preview.blocking_reasons" :key="r">{{ r }}</li>
      </ul>
      <ul v-if="summary.closure_preview.open_action_reasons.length">
        <li v-for="r in summary.closure_preview.open_action_reasons" :key="r">{{ r }}</li>
      </ul>
    </div>
    <button :disabled="busy || summary.session.status === 'COMPLETE'" @click="attemptClose">
      {{ summary.session.status === 'COMPLETE' ? 'Session complete' : 'Close session' }}
    </button>
    <p v-if="error" class="alert alert-error">{{ error }}</p>
  </section>
</template>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
  font-size: 0.85rem;
}
th,
td {
  text-align: left;
  padding: 0.35rem 0.5rem;
  border-bottom: 1px solid var(--border);
}
.pill {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}
.state-confirmed {
  background: #d1f7d6;
  color: #196a2b;
}
.state-unconfirmed {
  background: #fff3cd;
  color: #7a5b00;
}
.state-conflicted {
  background: #fde0e0;
  color: #9a1c1c;
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
</style>
