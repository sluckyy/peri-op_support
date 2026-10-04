<script setup>
import { reactive, ref } from 'vue'
import { api, formatApiError } from '../api.js'

let nextId = 0
function makeRow(label, risk = 0, clinical_value = 0, uncertainty = 0, recency = 0) {
  return { id: nextId++, label, risk, clinical_value, uncertainty, recency }
}

// Pre-filled so the force-inclusion rule is visible without any typing:
// the airway item ranks 3rd on score alone (its risk weight alone isn't
// enough to beat the other two), but risk > 0.85 forces it into the
// working set anyway even though max_size is 2.
const rows = reactive([
  makeRow('Patient’s main surgical worry', 0, 1.0, 1.0, 1.0),
  makeRow('Discharge planning question', 0, 0.9, 0.9, 0.9),
  makeRow('Unconfirmed difficult airway', 0.86, 0, 0, 0),
  makeRow('Unrelated small talk', 0, 0.2, 0, 0),
])
const maxSize = ref(2)

const result = ref(null)
const error = ref(null)
const busy = ref(false)

function addRow() {
  rows.push(makeRow(`item ${rows.length + 1}`))
}

function removeRow(id) {
  const idx = rows.findIndex((r) => r.id === id)
  if (idx !== -1) rows.splice(idx, 1)
}

async function compute() {
  busy.value = true
  error.value = null
  try {
    result.value = await api.attentionWorkingSet({
      max_size: Number(maxSize.value),
      candidates: rows
        .filter((r) => r.label)
        .map((r) => ({
          label: r.label,
          factors: {
            risk: Number(r.risk),
            clinical_value: Number(r.clinical_value),
            uncertainty: Number(r.uncertainty),
            recency: Number(r.recency),
          },
        })),
    })
  } catch (e) {
    error.value = formatApiError(e)
    result.value = null
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="card">
    <h2>Attention / working-memory calculator (§6A.5)</h2>
    <p class="hint">
      Real deterministic scoring (periop_core.attention), not derived
      from any session's stored objects -- mapping real hypotheses or
      obligations onto risk/clinical-value would mean inventing a
      scoring function the spec doesn't define. Set up candidate items
      with their factors (0&ndash;1) and a bounded working-set size, and
      see which ones make the cut &mdash; and which get force-included
      anyway because their risk crosses the threshold (6A.5: "high-risk
      unresolved obligations remain persistent until resolved or handed
      off").
    </p>

    <div class="row-grid header">
      <span>Label</span>
      <span>Risk</span>
      <span>Clinical value</span>
      <span>Uncertainty</span>
      <span>Recency</span>
      <span></span>
    </div>
    <div v-for="r in rows" :key="r.id" class="row-grid">
      <input v-model="r.label" placeholder="what is this item" />
      <input v-model="r.risk" type="number" min="0" max="1" step="0.01" />
      <input v-model="r.clinical_value" type="number" min="0" max="1" step="0.01" />
      <input v-model="r.uncertainty" type="number" min="0" max="1" step="0.01" />
      <input v-model="r.recency" type="number" min="0" max="1" step="0.01" />
      <button class="inline-button" @click="removeRow(r.id)">remove</button>
    </div>
    <div class="form-row">
      <button class="secondary" @click="addRow">+ add candidate</button>
      <label class="max-size-label">
        Working-set size
        <input v-model="maxSize" type="number" min="0" step="1" />
      </label>
      <button :disabled="busy" @click="compute">Compute working set</button>
    </div>

    <div v-if="result" class="alert alert-ok">
      <strong>Working set ({{ result.working_set.length }} of {{ rows.length }}):</strong>
      {{ result.working_set.join(', ') || '(empty)' }}
      <p v-if="result.forced_inclusions.length" class="hint">
        Force-included beyond the working-set size (risk &gt; 0.85): {{ result.forced_inclusions.join(', ') }}
      </p>
      <table>
        <thead>
          <tr>
            <th>Label</th>
            <th>Score</th>
            <th>In working set?</th>
            <th>Forced?</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in result.candidates" :key="c.label">
            <td>{{ c.label }}</td>
            <td>{{ c.score.toFixed(2) }}</td>
            <td>{{ c.in_working_set ? 'yes' : 'no' }}</td>
            <td>{{ c.forced_inclusion ? 'yes' : '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="error" class="alert alert-error">{{ error }}</p>
  </section>
</template>

<style scoped>
.row-grid {
  display: grid;
  grid-template-columns: 2fr 0.8fr 0.8fr 0.8fr 0.8fr auto;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.4rem;
}
.row-grid.header {
  font-size: 0.75rem;
  color: var(--muted);
  font-weight: 600;
}
.form-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin: 0.75rem 0;
  flex-wrap: wrap;
}
.max-size-label {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  gap: 0.25rem;
}
.max-size-label input {
  width: 4rem;
}
button.secondary {
  background: var(--card-bg);
  color: var(--text);
  border: 1px solid var(--border);
}
.inline-button {
  padding: 0.3rem 0.5rem;
  font-size: 0.75rem;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 0.5rem;
  font-size: 0.82rem;
}
th,
td {
  text-align: left;
  padding: 0.3rem 0.4rem;
  border-bottom: 1px solid var(--border);
}
</style>
