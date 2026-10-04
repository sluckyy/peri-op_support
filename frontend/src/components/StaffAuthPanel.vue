<script setup>
import { reactive, ref } from 'vue'
import { api, formatApiError, setAuthToken } from '../api.js'

const emit = defineEmits(['authenticated'])

const mode = ref('login') // 'login' | 'register'
const form = reactive({ username: '', password: '' })
const busy = ref(false)
const error = ref(null)

async function submit() {
  if (!form.username || !form.password) return
  busy.value = true
  error.value = null
  try {
    if (mode.value === 'register') {
      await api.register({ username: form.username, password: form.password })
    }
    const result = await api.login({ username: form.username, password: form.password })
    setAuthToken(result.token)
    emit('authenticated', { token: result.token, username: result.user.username })
  } catch (e) {
    error.value = formatApiError(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="card">
    <h2>Staff sign-in</h2>
    <p class="hint">
      Real authentication (periop_core.auth) -- salted scrypt password
      hashing and unguessable session tokens, not a demo placeholder.
      Patients submit their own data without an account; viewing a
      session's clinical data or taking a Model Layer action requires
      signing in here. Scope honestly stated: single-factor username/
      password only -- no email verification, password reset or MFA.
    </p>
    <div class="form-row">
      <input v-model="form.username" placeholder="username" autocomplete="username" />
      <input v-model="form.password" type="password" placeholder="password (min 8 chars)" autocomplete="current-password" />
      <div class="mode-toggle">
        <button type="button" class="chip" :class="{ active: mode === 'login' }" @click="mode = 'login'">
          Sign in
        </button>
        <button type="button" class="chip" :class="{ active: mode === 'register' }" @click="mode = 'register'">
          Register
        </button>
      </div>
      <button :disabled="busy || !form.username || !form.password" @click="submit">
        {{ mode === 'register' ? 'Register & sign in' : 'Sign in' }}
      </button>
    </div>
    <p v-if="error" class="alert alert-error">{{ error }}</p>
  </section>
</template>

<style scoped>
.form-row {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  flex-wrap: wrap;
}
.mode-toggle {
  display: flex;
  gap: 0.3rem;
}
.chip {
  background: var(--card-bg);
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.3rem 0.7rem;
  font-size: 0.8rem;
  font-weight: 600;
}
.chip.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
</style>
