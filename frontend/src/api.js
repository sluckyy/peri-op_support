const BASE = '/api'

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

  closeSession: (sessionId) =>
    request(`/sessions/${sessionId}/close`, { method: 'POST' }),
}
