<template>
  <div class="login-page">
    <div class="login-container">
      <!-- D20 Icon at top -->
      <div class="login-icon">
        <svg viewBox="0 0 60 60" fill="none" xmlns="http://www.w3.org/2000/svg" class="login-d20">
          <polygon
            points="30,4 56,18 56,42 30,56 4,42 4,18"
            stroke="#c9a227"
            stroke-width="2"
            fill="none"
          />
          <line x1="30" y1="4"  x2="30" y2="26" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
          <line x1="56" y1="18" x2="30" y2="26" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
          <line x1="56" y1="42" x2="30" y2="26" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
          <line x1="30" y1="56" x2="30" y2="26" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
          <line x1="4"  y1="42" x2="30" y2="26" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
          <line x1="4"  y1="18" x2="30" y2="26" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
          <text x="30" y="30" text-anchor="middle" dominant-baseline="middle"
                fill="#c9a227" font-size="14" font-family="Cinzel, serif" font-weight="700">20</text>
        </svg>
      </div>

      <h2 class="login-heading">D&amp;D 5e AI Game Engine</h2>
      <p class="login-sub">Enter the realm or forge your legend anew.</p>

      <div class="gold-divider"></div>

      <!-- Tabs -->
      <div class="tab-row">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'login' }"
          @click="activeTab = 'login'; clearError()"
        >
          Sign In
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'register' }"
          @click="activeTab = 'register'; clearError()"
        >
          Join the Realm
        </button>
      </div>

      <!-- Login Form -->
      <form v-if="activeTab === 'login'" class="auth-form" @submit.prevent="handleLogin">
        <div class="form-field">
          <label class="dnd-label" for="login-username">Username</label>
          <input
            id="login-username"
            v-model="loginForm.username"
            class="dnd-input"
            type="text"
            placeholder="Your adventurer name"
            autocomplete="username"
            required
          />
        </div>
        <div class="form-field">
          <label class="dnd-label" for="login-password">Password</label>
          <input
            id="login-password"
            v-model="loginForm.password"
            class="dnd-input"
            type="password"
            placeholder="Your secret passphrase"
            autocomplete="current-password"
            required
          />
        </div>

        <div v-if="authStore.error" class="error-banner">
          {{ authStore.error }}
        </div>

        <button
          type="submit"
          class="dnd-button submit-btn"
          :disabled="authStore.loading"
        >
          <span v-if="authStore.loading" class="spinner-sm"></span>
          <span v-else>⚔ Sign In</span>
        </button>
      </form>

      <!-- Register Form -->
      <form v-else class="auth-form" @submit.prevent="handleRegister">
        <div class="form-field">
          <label class="dnd-label" for="reg-username">Choose a Username</label>
          <input
            id="reg-username"
            v-model="regForm.username"
            class="dnd-input"
            type="text"
            placeholder="Your adventurer name"
            autocomplete="username"
            required
            minlength="3"
          />
        </div>
        <div class="form-field">
          <label class="dnd-label" for="reg-password">Choose a Password</label>
          <input
            id="reg-password"
            v-model="regForm.password"
            class="dnd-input"
            type="password"
            placeholder="A strong passphrase"
            autocomplete="new-password"
            required
            minlength="6"
          />
        </div>
        <div class="form-field">
          <label class="dnd-label" for="reg-confirm">Confirm Password</label>
          <input
            id="reg-confirm"
            v-model="regForm.confirm"
            class="dnd-input"
            type="password"
            placeholder="Repeat your passphrase"
            autocomplete="new-password"
            required
          />
        </div>

        <div v-if="localError || authStore.error" class="error-banner">
          {{ localError || authStore.error }}
        </div>

        <button
          type="submit"
          class="dnd-button submit-btn"
          :disabled="authStore.loading"
        >
          <span v-if="authStore.loading" class="spinner-sm"></span>
          <span v-else>✦ Create Account</span>
        </button>
      </form>

      <!-- Celtic knot decorative footer -->
      <div class="login-footer">
        <div class="celtic-divider">
          <span>✦ ✦ ✦</span>
        </div>
        <p class="login-footer-text">
          <RouterLink to="/">Return to the Gates</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const activeTab = ref('login')
const localError = ref('')

const loginForm = ref({ username: '', password: '' })
const regForm = ref({ username: '', password: '', confirm: '' })

function clearError() {
  localError.value = ''
  authStore.error = null
}

async function handleLogin() {
  clearError()
  const ok = await authStore.login(loginForm.value.username, loginForm.value.password)
  if (ok) {
    const redirect = router.currentRoute.value.query.redirect || '/campaigns'
    router.push(redirect)
  }
}

async function handleRegister() {
  clearError()
  if (regForm.value.password !== regForm.value.confirm) {
    localError.value = 'Passwords do not match.'
    return
  }
  const ok = await authStore.register(regForm.value.username, regForm.value.password)
  if (ok) {
    router.push('/campaigns')
  }
}
</script>

<style scoped>
.login-page {
  min-height: calc(100vh - 64px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  background: radial-gradient(ellipse at center, #130e04 0%, #0d0a06 70%);
}

.login-container {
  width: 100%;
  max-width: 440px;
  background: #1a1109;
  border: 1px solid #7a6115;
  border-radius: 8px;
  padding: 2.5rem 2rem;
  box-shadow: 0 0 40px rgba(201,162,39,0.15), 0 8px 32px rgba(0,0,0,0.6);
  position: relative;
}

.login-container::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(201,162,39,0.05) 0%, transparent 50%);
  pointer-events: none;
}

.login-icon {
  display: flex;
  justify-content: center;
  margin-bottom: 1rem;
}

.login-d20 {
  width: 60px;
  height: 60px;
  filter: drop-shadow(0 0 12px rgba(201,162,39,0.5));
  animation: d20-slow-spin 15s linear infinite;
}

.login-heading {
  text-align: center;
  font-family: 'Cinzel', serif;
  font-size: 1.35rem;
  font-weight: 700;
  color: #c9a227;
  margin-bottom: 0.25rem;
}

.login-sub {
  text-align: center;
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #8a7355;
  font-size: 0.95rem;
  margin-bottom: 0;
}

.tab-row {
  display: flex;
  border-bottom: 1px solid #3d2e10;
  margin-bottom: 1.5rem;
}

.tab-btn {
  flex: 1;
  padding: 0.6rem 0;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  font-family: 'Cinzel', serif;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #8a7355;
  cursor: pointer;
  text-transform: uppercase;
  transition: color 0.2s, border-color 0.2s;
}

.tab-btn:hover { color: #c9a227; }

.tab-btn.active {
  color: #c9a227;
  border-bottom-color: #c9a227;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.error-banner {
  background: rgba(139,26,26,0.2);
  border: 1px solid #7f1d1d;
  border-radius: 4px;
  padding: 0.6rem 0.875rem;
  color: #f87171;
  font-family: 'Crimson Text', serif;
  font-size: 0.95rem;
}

.submit-btn {
  width: 100%;
  justify-content: center;
  padding: 0.65rem;
  font-size: 0.9rem;
  margin-top: 0.25rem;
}

.spinner-sm {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(26,14,0,0.4);
  border-top-color: #1a0e00;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.login-footer {
  margin-top: 2rem;
  text-align: center;
}

.celtic-divider {
  color: #7a6115;
  font-size: 0.8rem;
  letter-spacing: 0.3em;
  margin-bottom: 0.75rem;
  opacity: 0.7;
}

.login-footer-text {
  font-family: 'Crimson Text', serif;
  font-size: 0.9rem;
  color: #8a7355;
  margin: 0;
}

.login-footer-text a {
  color: #8a7355;
  transition: color 0.2s;
}

.login-footer-text a:hover {
  color: #c9a227;
}
</style>
