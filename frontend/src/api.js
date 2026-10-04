const BASE = '/api'

// FastAPI's HTTPException(detail=...) can be a plain string, or a dict
// such as {"reasons": [...]} or {"message": "..."}. Centralised here so
// every component shows a readable message instead of accidentally
// interpolating the raw object (which Vue will JSON.stringify).
export function formatApiError(e) {
  const detail = e?.body?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') {
    const reasons = detail.reasons ?? detail.blocking_reasons
    const parts = []
    if (typeof detail.message === 'string') parts.push(detail.message)
    if (Array.isArray(reasons)) parts.push(reasons.join('; '))
    if (parts.length) return parts.join(': ')
  }
  if (typeof e?.body?.message === 'string') return e.body.message
  return e?.message ?? String(e)
}

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const isJson = resp.headers.get('content-type')?.includes('application/json')
  const body = isJson ? await resp.json() : await resp.text()
  if (!resp.ok) {
    const err = new Error(`${resp.status} ${resp.statusText}`)
    err.status = resp.status
    err.body = body
    throw err
  }
  return body
}

export const api = {
  listConcepts: () => request('/concepts'),

  createSession: (payload) =>
    request('/sessions', { method: 'POST', body: JSON.stringify(payload) }),

  acknowledgeNotice: (sessionId) =>
    request(`/sessions/${sessionId}/notice`, { method: 'POST' }),

  activateSession: (sessionId) =>
    request(`/sessions/${sessionId}/activate`, { method: 'POST' }),

  addAssertion: (sessionId, payload) =>
    request(`/sessions/${sessionId}/assertions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getSummary: (sessionId) => request(`/sessions/${sessionId}/summary`),

  getAuditLineage: (sessionId) => request(`/sessions/${sessionId}/audit`),

  closeSession: (sessionId) =>
    request(`/sessions/${sessionId}/close`, { method: 'POST' }),

  resolveConflictReview: (sessionId, reviewId, payload) =>
    request(`/sessions/${sessionId}/conflict-reviews/${reviewId}/resolve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // v1.1 Model Layer (§6A)
  createHypothesis: (sessionId, payload) =>
    request(`/sessions/${sessionId}/hypotheses`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  promoteHypothesis: (sessionId, hypothesisId, payload) =>
    request(`/sessions/${sessionId}/hypotheses/${hypothesisId}/promote`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  correctProposition: (sessionId, propositionId, payload) =>
    request(`/sessions/${sessionId}/propositions/${propositionId}/correct`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  createRepair: (sessionId, payload) =>
    request(`/sessions/${sessionId}/repairs`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  resolveRepair: (sessionId, repairId) =>
    request(`/sessions/${sessionId}/repairs/${repairId}/resolve`, { method: 'POST' }),

  createContradiction: (sessionId, payload) =>
    request(`/sessions/${sessionId}/contradictions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  createUncertainty: (sessionId, payload) =>
    request(`/sessions/${sessionId}/uncertainties`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  createCausalHypothesis: (sessionId, payload) =>
    request(`/sessions/${sessionId}/causal-hypotheses`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateCausalHypothesisStatus: (sessionId, causalId, payload) =>
    request(`/sessions/${sessionId}/causal-hypotheses/${causalId}/status`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  applyPsychSafetySignal: (sessionId, signalNames) =>
    request(`/sessions/${sessionId}/psychological-safety/signal`, {
      method: 'POST',
      body: JSON.stringify({ signal_names: signalNames }),
    }),

  checkHumour: (sessionId, payload) =>
    request(`/sessions/${sessionId}/humour/check`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  causalEcd: (payload) =>
    request('/tools/causal-ecd', { method: 'POST', body: JSON.stringify(payload) }),

  attentionWorkingSet: (payload) =>
    request('/tools/attention-working-set', { method: 'POST', body: JSON.stringify(payload) }),
}
