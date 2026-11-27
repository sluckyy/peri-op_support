<script setup>
import { ref } from 'vue'
import SessionSetup from './components/SessionSetup.vue'
import AssertionForm from './components/AssertionForm.vue'
import VoiceInterview from './components/VoiceInterview.vue'
import SummaryPanel from './components/SummaryPanel.vue'
import ModelLayerPanel from './components/ModelLayerPanel.vue'
import CausalEcdCalculator from './components/CausalEcdCalculator.vue'
import AttentionWorkingSetCalculator from './components/AttentionWorkingSetCalculator.vue'
import AuditTrailPanel from './components/AuditTrailPanel.vue'
import StaffAuthPanel from './components/StaffAuthPanel.vue'
import { api, clearAuthToken } from './api.js'

const session = ref(null)
const summary = ref(null)
const auditPanel = ref(null)
const staffUsername = ref(null) // non-null once signed in -- see require_auth
const manualOpen = ref(false)

async function onSessionReady(activatedSession) {
  session.value = activatedSession
  summary.value = null
  if (staffUsername.value) {
    summary.value = await api.getSummary(activatedSession.session_id)
    auditPanel.value?.load()
  }
}

async function onAssertionAdded() {
  // add_assertion_endpoint is patient-facing/unauthenticated and
  // deliberately no longer returns the clinical summary in its
  // response (see AssertionRecordedResponse) -- only fetch it if
  // staff is actually signed in to view it.
  if (staffUsername.value && session.value) {
    summary.value = await api.getSummary(session.value.session_id)
    auditPanel.value?.load()
  }
}

async function refreshSummary() {
  summary.value = await api.getSummary(session.value.session_id)
  auditPanel.value?.load()
}

function onClosed(newSummary) {
  summary.value = newSummary
  auditPanel.value?.load()
}

async function onAuthenticated({ username }) {
  staffUsername.value = username
  if (session.value) {
    summary.value = await api.getSummary(session.value.session_id)
    auditPanel.value?.load()
  }
}

async function signOut() {
  try {
    await api.logout()
  } catch (e) {
    // Token already invalid/expired -- signing out locally still proceeds.
  }
  clearAuthToken()
  staffUsername.value = null
  summary.value = null
}
</script>

<template>
  <main>
    <header>
      <h1>Perioperative Conversational AI — deterministic core demo</h1>
      <p class="hint">
        Demo UI over the Phase 1 deterministic core (models, reconciliation,
        gap engine, closure gate) plus the v1.1 Model Layer (§6A), with a
        voice interviewer whose LLM only proposes candidate answers that a
        deterministic validator checks before anything is recorded. Not a
        clinical tool. See the repo README for scope.
      </p>
    </header>

    <SessionSetup @session-ready="onSessionReady" />

    <template v-if="session">
      <VoiceInterview
        :key="session.session_id"
        :session-id="session.session_id"
        @answered="onAssertionAdded"
        @unavailable="manualOpen = true"
      />
      <details class="manual" :open="manualOpen" @toggle="manualOpen = $event.target.open">
        <summary>Manual entry (fallback form)</summary>
        <AssertionForm :session-id="session.session_id" @added="onAssertionAdded" />
      </details>
    </template>

    <StaffAuthPanel v-if="!staffUsername" @authenticated="onAuthenticated" />
    <template v-else>
      <div class="staff-bar">
        Signed in as <strong>{{ staffUsername }}</strong>
        <button class="inline-button" @click="signOut">sign out</button>
      </div>
      <template v-if="session">
        <SummaryPanel
          v-if="summary"
          :summary="summary"
          @refresh="refreshSummary"
          @closed="onClosed"
        />
        <ModelLayerPanel
          v-if="summary"
          :session-id="session.session_id"
          :summary="summary"
          @refresh="refreshSummary"
        />
        <AuditTrailPanel ref="auditPanel" :session-id="session.session_id" />
      </template>
      <p v-else class="hint">Start a patient session above to view its data here.</p>
    </template>

    <CausalEcdCalculator />
    <AttentionWorkingSetCalculator />
  </main>
</template>

<style scoped>
.staff-bar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 0.75rem;
}
.manual {
  margin-bottom: 1rem;
}
.manual > summary {
  cursor: pointer;
  color: var(--muted);
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}
.inline-button {
  padding: 0.25rem 0.6rem;
  font-size: 0.75rem;
}
</style>
