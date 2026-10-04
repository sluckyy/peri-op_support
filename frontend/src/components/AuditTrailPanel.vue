<script setup>
import { onMounted, watch, ref } from 'vue'
import { api, formatApiError } from '../api.js'

const props = defineProps({ sessionId: { type: String, required: true } })

const events = ref([])
const error = ref(null)

async function load() {
  try {
    events.value = await api.getAuditLineage(props.sessionId)
  } catch (e) {
    error.value = formatApiError(e)
  }
}

onMounted(load)
// The parent doesn't know when a mutation happened elsewhere on the
// page, so this polls lightly rather than needing every action handler
// wired to also refresh audit -- fine for a demo, not a scalable pattern.
defineExpose({ load })
watch(() => props.sessionId, load)
</script>

<template>
  <section class="card">
    <h2>Audit trail (SVC-014)</h2>
    <p class="hint">
      Immutable lineage of this session's Phase 1 core mutations --
      <code>getLineage</code>. Not yet wired up for v1.1 Model Layer
      mutations (hypotheses, repairs, obligations) -- see README.
    </p>
    <table v-if="events.length">
      <thead>
        <tr>
          <th>Occurred at</th>
          <th>Event</th>
          <th>Entity</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="e in events" :key="e.event_id">
          <td>{{ new Date(e.occurred_at).toLocaleTimeString() }}</td>
          <td><span class="pill">{{ e.event_type }}</span></td>
          <td>{{ e.entity_type }}</td>
          <td><code>{{ JSON.stringify(e.payload) }}</code></td>
        </tr>
      </tbody>
    </table>
    <p v-else class="hint">No events yet.</p>
    <p v-if="error" class="alert alert-error">{{ error }}</p>
  </section>
</template>
