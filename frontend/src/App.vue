<script setup>
import { ref } from 'vue'
import SessionSetup from './components/SessionSetup.vue'
import AssertionForm from './components/AssertionForm.vue'
import SummaryPanel from './components/SummaryPanel.vue'
import ModelLayerPanel from './components/ModelLayerPanel.vue'
import CausalEcdCalculator from './components/CausalEcdCalculator.vue'
import AttentionWorkingSetCalculator from './components/AttentionWorkingSetCalculator.vue'
import AuditTrailPanel from './components/AuditTrailPanel.vue'
import { api } from './api.js'

const session = ref(null)
const summary = ref(null)
const auditPanel = ref(null)

async function onSessionReady(activatedSession) {
  session.value = activatedSession
  summary.value = await api.getSummary(activatedSession.session_id)
  auditPanel.value?.load()
}

function onAssertionAdded(newSummary) {
  summary.value = newSummary
  auditPanel.value?.load()
}

async function refreshSummary() {
  summary.value = await api.getSummary(session.value.session_id)
  auditPanel.value?.load()
}

function onClosed(newSummary) {
  summary.value = newSummary
  auditPanel.value?.load()
}
</script>

<template>
  <main>
    <header>
      <h1>Perioperative Conversational AI — deterministic core demo</h1>
      <p class="hint">
        Demo UI over the Phase 1 deterministic core (models, reconciliation,
        gap engine, closure gate) plus the v1.1 Model Layer (§6A) — no LLM
        or orchestrator yet. Not a clinical tool. See the repo README for
        scope.
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
      <ModelLayerPanel
        v-if="summary"
        :session-id="session.session_id"
        :summary="summary"
        @refresh="refreshSummary"
      />
      <AuditTrailPanel ref="auditPanel" :session-id="session.session_id" />
    </template>

    <CausalEcdCalculator />
    <AttentionWorkingSetCalculator />
  </main>
</template>
