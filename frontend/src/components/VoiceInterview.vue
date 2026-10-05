<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { api, formatApiError } from '../api.js'

const props = defineProps({ sessionId: { type: String, required: true } })
const emit = defineEmits(['answered', 'unavailable'])

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
const canListen = Boolean(Recognition)
const canSpeak = 'speechSynthesis' in window

// idle | thinking | speaking | listening | done | unavailable
const status = ref('idle')
const started = ref(false)
const voiceOn = ref(canSpeak)
const messages = ref([])
const current = ref(null)
const caption = ref('')
const typed = ref('')
const error = ref(null)
const log = ref(null)

let recognition = null

const statusText = computed(() => ({
  thinking: 'Thinking…',
  speaking: 'Speaking…',
  listening: 'Listening… go ahead and answer',
  done: 'Interview finished.',
  unavailable: 'AI interviewer unavailable — use the manual form below.',
}[status.value] ?? ''))

function addMessage(from, text) {
  messages.value.push({ from, text })
  nextTick(() => { if (log.value) log.value.scrollTop = log.value.scrollHeight })
}

function pickVoice() {
  const voices = window.speechSynthesis.getVoices()
  return (
    voices.find((v) => v.lang === 'en-AU') ||
    voices.find((v) => v.lang === 'en-GB') ||
    voices.find((v) => v.lang?.startsWith('en')) ||
    null
  )
}

function speak(text) {
  return new Promise((resolve) => {
    if (!voiceOn.value || !canSpeak) return resolve()
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    const voice = pickVoice()
    if (voice) utterance.voice = voice
    utterance.rate = 1
    utterance.onend = resolve
    utterance.onerror = resolve
    status.value = 'speaking'
    window.speechSynthesis.speak(utterance)
  })
}

function stopListening() {
  if (recognition) {
    recognition.onend = null
    recognition.abort()
    recognition = null
  }
  caption.value = ''
}

function listen() {
  if (!canListen || !voiceOn.value || !current.value) {
    status.value = 'idle'
    return
  }
  stopListening()
  let finalText = ''
  let confidence = null
  recognition = new Recognition()
  recognition.lang = 'en-AU'
  recognition.interimResults = true
  recognition.continuous = false
  recognition.maxAlternatives = 1
  recognition.onresult = (event) => {
    let interim = ''
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i]
      if (result.isFinal) {
        finalText += result[0].transcript
        confidence = result[0].confidence || null
      } else {
        interim += result[0].transcript
      }
    }
    caption.value = (finalText + ' ' + interim).trim()
  }
  recognition.onerror = (event) => {
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      voiceOn.value = false
      error.value = 'Microphone access was blocked, so voice is off. You can type your answers instead.'
    }
  }
  recognition.onend = () => {
    recognition = null
    caption.value = ''
    const text = finalText.trim()
    if (text) {
      submit(text, 'VOICE', confidence)
    } else if (status.value === 'listening') {
      status.value = 'idle'
    }
  }
  status.value = 'listening'
  recognition.start()
}

let presented = 0

async function present(question) {
  const token = ++presented
  current.value = question
  addMessage('agent', question.question)
  if (voiceOn.value && canSpeak) {
    await speak(question.question)
    // Speech was cut short by a typed answer, the mic button or End.
    if (token !== presented || status.value !== 'speaking') return
  }
  if (voiceOn.value && canListen) listen()
  else status.value = 'idle'
}

function handleError(e) {
  stopListening()
  if (e?.status === 503) {
    status.value = 'unavailable'
    emit('unavailable')
  } else {
    status.value = 'idle'
    error.value = formatApiError(e)
  }
}

async function start() {
  error.value = null
  started.value = true
  status.value = 'thinking'
  try {
    const resp = await api.interviewNext(props.sessionId, voiceOn.value ? 'VOICE' : 'TEXT')
    if (resp.done) return finish()
    await present(resp.next)
  } catch (e) {
    handleError(e)
  }
}

async function submit(text, modality, confidence = null) {
  if (!current.value || !text.trim()) return
  error.value = null
  stopListening()
  addMessage('patient', text)
  status.value = 'thinking'
  try {
    const resp = await api.interviewAnswer(props.sessionId, {
      action_id: current.value.action_id,
      transcript: text,
      modality,
      stt_confidence: confidence,
    })
    if (resp.recorded) emit('answered')
    if (resp.done) return finish()
    await present(resp.next)
  } catch (e) {
    handleError(e)
  }
}

function submitTyped() {
  const text = typed.value.trim()
  if (!text || status.value === 'thinking') return
  typed.value = ''
  if (canSpeak) window.speechSynthesis.cancel()
  submit(text, 'TEXT')
}

function finish() {
  current.value = null
  status.value = 'done'
  const closing = 'That is all the questions for now. Thank you — the care team will review your answers.'
  addMessage('agent', closing)
  speak(closing).then(() => { status.value = 'done' })
}

function endInterview() {
  stopListening()
  if (canSpeak) window.speechSynthesis.cancel()
  current.value = null
  status.value = 'done'
  addMessage('agent', 'Interview paused. You can continue at any time.')
}

function toggleVoice() {
  voiceOn.value = !voiceOn.value
  if (!voiceOn.value) {
    stopListening()
    if (canSpeak) window.speechSynthesis.cancel()
    if (status.value === 'listening' || status.value === 'speaking') status.value = 'idle'
  }
}

function micClick() {
  if (status.value === 'listening') {
    recognition?.stop()
    return
  }
  if (canSpeak) window.speechSynthesis.cancel()
  voiceOn.value = true
  listen()
}

onBeforeUnmount(() => {
  stopListening()
  if (canSpeak) window.speechSynthesis.cancel()
})
</script>

<template>
  <section class="card">
    <h2>Talk to the pre-op assistant</h2>
    <p class="hint">
      An AI assistant asks your pre-operative questions out loud and listens to your answers.
      It only records what you say against the question it asked — a clinician reviews
      everything. You can also type. <strong>Demo only: do not use real patient information.</strong>
      <span v-if="canListen">
        Speech recognition is done by your browser (in Chrome, audio is sent to Google).
      </span>
    </p>
    <p v-if="!canListen" class="hint">
      This browser can't do speech recognition, so please type your answers
      (Chrome or Edge support speaking).
    </p>

    <div v-if="!started" class="controls">
      <button @click="start">Start interview</button>
      <label v-if="canSpeak" class="toggle">
        <input v-model="voiceOn" type="checkbox" /> Speak questions aloud
      </label>
    </div>

    <template v-else>
      <div ref="log" class="log" aria-live="polite">
        <div v-for="(m, i) in messages" :key="i" class="bubble" :class="m.from">
          <span class="who">{{ m.from === 'agent' ? 'Assistant' : 'You' }}</span>
          {{ m.text }}
        </div>
        <div v-if="caption" class="bubble patient interim">
          <span class="who">You</span>{{ caption }}
        </div>
      </div>

      <p class="status" :class="status">{{ statusText }}</p>

      <div v-if="current && status !== 'unavailable'" class="answer-row">
        <button
          v-if="canListen"
          class="mic"
          :class="{ live: status === 'listening' }"
          :disabled="status === 'thinking'"
          :aria-label="status === 'listening' ? 'Stop listening' : 'Speak your answer'"
          @click="micClick"
        >
          {{ status === 'listening' ? '■ Stop' : '🎤 Speak' }}
        </button>
        <input
          v-model="typed"
          placeholder="…or type your answer and press Enter"
          :disabled="status === 'thinking'"
          @keyup.enter="submitTyped"
        />
        <button :disabled="status === 'thinking' || !typed.trim()" @click="submitTyped">Send</button>
      </div>

      <div class="controls">
        <button v-if="current" class="secondary" @click="endInterview">End interview</button>
        <button v-else-if="status === 'done'" class="secondary" @click="start">Continue</button>
        <button v-if="canSpeak" class="secondary" @click="toggleVoice">
          Voice: {{ voiceOn ? 'on' : 'off' }}
        </button>
      </div>
    </template>

    <p v-if="error" class="alert alert-error">{{ error }}</p>
  </section>
</template>

<style scoped>
.controls {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 0.6rem;
}
.toggle {
  font-size: 0.85rem;
  color: var(--muted);
}
.log {
  max-height: 22rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem 0;
}
.bubble {
  max-width: 80%;
  padding: 0.55rem 0.8rem;
  border-radius: 0.8rem;
  line-height: 1.4;
  border: 1px solid var(--border);
}
.bubble.agent {
  align-self: flex-start;
  background: var(--card-bg);
}
.bubble.patient {
  align-self: flex-end;
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
.bubble.interim {
  opacity: 0.6;
}
.who {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  opacity: 0.75;
  margin-bottom: 0.15rem;
}
.status {
  min-height: 1.2rem;
  font-size: 0.85rem;
  color: var(--muted);
}
.status.listening {
  color: var(--accent);
  font-weight: 600;
}
.answer-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.answer-row input {
  flex: 1;
  min-width: 0;
}
.mic.live {
  background: #c62828;
  border-color: #c62828;
  color: white;
}
.secondary {
  background: var(--card-bg);
  color: var(--text);
  border: 1px solid var(--border);
}
</style>
