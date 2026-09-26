<script setup>
import { ref } from 'vue'
import SessionSetup from './components/SessionSetup.vue'
import AssertionForm from './components/AssertionForm.vue'
import SummaryPanel from './components/SummaryPanel.vue'
import { api } from './api.js'

const session = ref(null)
const summary = ref(null)

async function onSessionReady(activatedSession) {
  session.value = activatedSession
  summary.value = await api.getSummary(activatedSession.session_id)
}

function onAssertionAdded(newSummary) {
  summary.value = newSummary
}

async function refreshSummary() {
  summary.value = await api.getSummary(session.value.session_id)
}

function onClosed(newSummary) {
  summary.value = newSummary
}
</script>

<template>
  <main>
    <header>
      <h1>Perioperative Conversational AI — deterministic core demo</h1>
      <p class="hint">
        Demo UI over the Phase 1 deterministic core (models, reconciliation,
        gap engine, closure gate) — no LLM, orchestrator or FHIR layer yet.
        Not a clinical tool. See the repo README for scope.
      </p>
    </header>

    <SessionSetup @session-ready="onSessionReady" />

    <template v-if="session">
      <AssertionForm :session-id="session.session_id" @added="onAssertionAdded" />
      <SummaryPanel
        v-if="summary"
        :summary="summary"
        @refresh="refreshSummary"
        @closed="onClosed"
      />
    </template>
  </main>
</template>
