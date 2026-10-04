<script setup>
import { computed, reactive, ref } from 'vue'
import { api, formatApiError } from '../api.js'

const props = defineProps({ summary: { type: Object, required: true } })
const emit = defineEmits(['refresh', 'closed'])

const busy = ref(false)
const error = ref(null)

// ------------------------------------------------------- conflict reviews

const reviewForms = reactive({}) // review_id -> { resolved_value, resolved_by, rationale }

function reviewForm(reviewId) {
  if (!reviewForms[reviewId]) {
    reviewForms[reviewId] = { resolved_value: null, resolved_by: '', rationale: '' }
  }
  return reviewForms[reviewId]
}

function pickSide(reviewId, value) {
  reviewForm(reviewId).resolved_value = value
}

async function resolveReview(reviewId, status) {
  busy.value = true
  error.value = null
  try {
    const form = reviewForm(reviewId)
    await api.resolveConflictReview(props.summary.session.session_id, reviewId, {
      status,
      resolved_by: form.resolved_by,
      rationale: form.rationale,
      resolved_value: status === 'ESCALATED' ? null : form.resolved_value,
    })
    delete reviewForms[reviewId]
    emit('refresh')
  } catch (e) {
    error.value = formatApiError(e)
  } finally {
    busy.value = false
  }
}

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
    error.value = formatApiError(e)
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

    <h3>Conflict reviews ({{ summary.conflict_reviews.length }})</h3>
    <p class="hint">
      Every conflict above gets a durable review record here the moment
      it's first detected &mdash; unlike the Conflict row above it (wiped
      and rebuilt every time this summary is recomputed), a clinician's
      decision on a review is never silently lost. Pick whichever side is
      correct, or escalate if neither is.
    </p>
    <div v-if="summary.conflict_reviews.length" class="review-list">
      <div v-for="r in summary.conflict_reviews" :key="r.review_id" class="review-card">
        <div class="review-head">
          <span class="pill" :class="`review-status-${r.status.toLowerCase()}`">{{ r.status }}</span>
          <span>{{ r.concept.code }} &mdash; {{ r.concept.original_text }}</span>
        </div>
        <ul class="side-list">
          <li v-for="s in r.sides" :key="s.assertion_id">
            <button
              v-if="r.status === 'OPEN'"
              class="side-pick"
              :class="{ picked: reviewForm(r.review_id).resolved_value === s.value }"
              :disabled="busy"
              @click="pickSide(r.review_id, s.value)"
            >
              <strong>{{ s.source_type }}</strong> ({{ s.speaker }}), {{ new Date(s.recorded_at).toLocaleDateString() }}:
              <strong>{{ s.value }}</strong> &mdash; &ldquo;{{ s.original_text }}&rdquo;
            </button>
            <span v-else class="side-readonly">
              <strong>{{ s.source_type }}</strong> ({{ s.speaker }}), {{ new Date(s.recorded_at).toLocaleDateString() }}:
              <strong>{{ s.value }}</strong> &mdash; &ldquo;{{ s.original_text }}&rdquo;
            </span>
          </li>
        </ul>
        <div v-if="r.status === 'OPEN'" class="resolve-form">
          <input v-model="reviewForm(r.review_id).resolved_by" placeholder="your name" />
          <input v-model="reviewForm(r.review_id).rationale" placeholder="why" />
          <button
            :disabled="
              busy ||
              !reviewForm(r.review_id).resolved_by ||
              !reviewForm(r.review_id).rationale ||
              reviewForm(r.review_id).resolved_value === null
            "
            @click="resolveReview(r.review_id, 'RECONCILED')"
          >
            Reconcile with selected value
          </button>
          <button
            :disabled="busy || !reviewForm(r.review_id).resolved_by || !reviewForm(r.review_id).rationale"
            class="secondary"
            @click="resolveReview(r.review_id, 'ESCALATED')"
          >
            Escalate instead
          </button>
        </div>
        <p v-else class="hint resolution-summary">
          Resolved by {{ r.resolution.resolved_by }}: &ldquo;{{ r.resolution.rationale }}&rdquo;
          <span v-if="r.resolution.resolved_value !== null">
            &mdash; chose <strong>{{ r.resolution.resolved_value }}</strong>
          </span>
        </p>
      </div>
    </div>
    <p v-else class="hint">No conflict reviews yet.</p>

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
.state-stale {
  background: #e6e6e6;
  color: #555;
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
.review-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  margin-bottom: 1rem;
}
.review-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
  font-size: 0.85rem;
}
.review-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
  flex-wrap: wrap;
}
.review-status-open {
  background: #fff3cd;
  color: #7a5b00;
}
.review-status-reconciled {
  background: #d1f7d6;
  color: #196a2b;
}
.review-status-escalated {
  background: #fde0e0;
  color: #9a1c1c;
}
.side-list {
  list-style: none;
  padding: 0;
  margin: 0 0 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.side-pick {
  display: block;
  width: 100%;
  text-align: left;
  background: var(--card-bg);
  color: var(--text);
  border: 1px solid var(--border);
  font-weight: 400;
  font-size: 0.82rem;
  padding: 0.4rem 0.6rem;
}
.side-pick.picked {
  border-color: var(--accent);
  background: var(--accent);
  color: white;
}
.side-readonly {
  display: block;
  font-size: 0.82rem;
  padding: 0.4rem 0.6rem;
  color: var(--muted);
}
.resolve-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}
.resolve-form input {
  flex: 1 1 140px;
  min-width: 0;
}
button.secondary {
  background: var(--card-bg);
  color: var(--text);
  border: 1px solid var(--border);
}
.resolution-summary {
  margin: 0;
}
</style>
