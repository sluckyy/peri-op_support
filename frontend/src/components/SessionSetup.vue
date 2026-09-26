<script setup>
import { reactive, ref } from 'vue'
import { api } from '../api.js'

const emit = defineEmits(['session-ready'])

const form = reactive({
  subject_ref: 'demo-patient-1',
  age_years: 55,
  age_source: 'booking_feed',
  is_obstetric_procedure: false,
  is_emergency_listing: false,
})

const session = ref(null)
const rejectionReasons = ref(null)
const noticeAcknowledged = ref(false)
const busy = ref(false)
const error = ref(null)

async function createSession() {
  busy.value = true
  error.value = null
  rejectionReasons.value = null
  try {
    session.value = await api.createSession({
      subject_ref: form.subject_ref,
      age_years: form.age_years ? Number(form.age_years) : null,
      age_source: form.age_source,
      is_obstetric_procedure: form.is_obstetric_procedure,
      is_emergency_listing: form.is_emergency_listing,
    })
  } catch (e) {
    if (e.status === 422) {
      rejectionReasons.value = e.body?.detail?.reasons ?? ['Rejected (no reason given)']
    } else {
      error.value = e.message
    }
  } finally {
    busy.value = false
  }
}

async function acknowledgeAndActivate() {
  busy.value = true
  error.value = null
  try {
    await api.acknowledgeNotice(session.value.session_id)
    noticeAcknowledged.value = true
    session.value = await api.activateSession(session.value.session_id)
    emit('session-ready', session.value)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="card">
    <h2>1. Start a session</h2>

    <div v-if="!session" class="form-grid">
      <label>
        Subject reference
        <input v-model="form.subject_ref" type="text" />
      </label>
      <label>
        Age (years)
        <input v-model="form.age_years" type="number" min="0" />
      </label>
      <label class="checkbox">
        <input v-model="form.is_obstetric_procedure" type="checkbox" />
        Obstetric procedure
      </label>
      <label class="checkbox">
        <input v-model="form.is_emergency_listing" type="checkbox" />
        Emergency listing
      </label>
      <button :disabled="busy" @click="createSession">Create session</button>
    </div>

    <div v-if="rejectionReasons" class="alert alert-block">
      <strong>Session rejected (intake eligibility check, addendum item 2):</strong>
      <ul>
        <li v-for="r in rejectionReasons" :key="r">{{ r }}</li>
      </ul>
    </div>

    <div v-if="session && !noticeAcknowledged" class="notice">
      <p>
        <strong>AI-role &amp; data-use notice</strong> (addendum item 1): this
        session is conducted by an automated assistant, not a clinician. Your
        answers are collected for perioperative assessment and reviewed by
        clinical staff before any decision is made. You may ask to speak to a
        person at any time.
      </p>
      <button :disabled="busy" @click="acknowledgeAndActivate">
        Acknowledge &amp; start
      </button>
    </div>

    <div v-if="session && noticeAcknowledged" class="alert alert-ok">
      Session <code>{{ session.session_id.slice(0, 8) }}…</code> is
      <strong>{{ session.status }}</strong>.
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
label.checkbox {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
button {
  grid-column: 1 / -1;
  justify-self: start;
}
.notice {
  margin-top: 1rem;
}
</style>
