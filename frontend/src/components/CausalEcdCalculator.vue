<script setup>
import { reactive, ref } from 'vue'
import { api, formatApiError } from '../api.js'

const form = reactive({
  hypA: 'PE',
  priorA: 0.5,
  hypB: 'MI',
  priorB: 0.5,
  pYesGivenA: 0.9,
  pYesGivenB: 0.3,
})

const result = ref(null)
const error = ref(null)
const busy = ref(false)

async function compute() {
  busy.value = true
  error.value = null
  try {
    const prior = { [form.hypA]: Number(form.priorA), [form.hypB]: Number(form.priorB) }
    const pYesA = Number(form.pYesGivenA)
    const pYesB = Number(form.pYesGivenB)
    const likelihoods = {
      yes: { [form.hypA]: pYesA, [form.hypB]: pYesB },
      no: { [form.hypA]: 1 - pYesA, [form.hypB]: 1 - pYesB },
    }
    result.value = await api.causalEcd({ prior, likelihoods })
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
    <h2>Causal hypothesis discrimination calculator (§6A.10)</h2>
    <p class="hint">
      Real Shannon-entropy machinery (periop_core.causal_reasoning), not a
      demo shortcut. Set up two candidate causes and a hypothetical
      yes/no question's likelihood of a "yes" answer under each, and see
      how much asking it would actually be expected to discriminate
      between them (in bits).
    </p>
    <div class="form-grid">
      <label>
        Hypothesis A
        <input v-model="form.hypA" />
      </label>
      <label>
        Prior P(A)
        <input v-model="form.priorA" type="number" step="0.05" min="0" max="1" />
      </label>
      <label>
        Hypothesis B
        <input v-model="form.hypB" />
      </label>
      <label>
        Prior P(B) (should be 1 - P(A) for two hypotheses)
        <input v-model="form.priorB" type="number" step="0.05" min="0" max="1" />
      </label>
      <label>
        P(yes | A)
        <input v-model="form.pYesGivenA" type="number" step="0.05" min="0" max="1" />
      </label>
      <label>
        P(yes | B)
        <input v-model="form.pYesGivenB" type="number" step="0.05" min="0" max="1" />
      </label>
      <button :disabled="busy" @click="compute">Compute ECD</button>
    </div>

    <div v-if="result" class="alert alert-ok">
      <strong>Expected clinical discrimination: {{ result.ecd.toFixed(3) }} bits</strong>
      <p>Prior entropy: {{ result.prior_entropy.toFixed(3) }} bits</p>
      <p>Expected posterior entropy: {{ result.expected_posterior_entropy.toFixed(3) }} bits</p>
      <p class="hint">
        ECD = 0 means the question tells you nothing; ECD = prior entropy
        means it perfectly discriminates between the hypotheses.
      </p>
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
button {
  grid-column: 1 / -1;
  justify-self: start;
}
</style>
