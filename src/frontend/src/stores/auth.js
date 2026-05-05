import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)  // { user_id, username }
  const loading = ref(false)
  const error = ref(null)

  const isLoggedIn = computed(() => user.value !== null)

  async function register(username, password) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Registration failed')
      user.value = data
      return true
    } catch (e) {
      error.value = e.message
      return false
    } finally {
      loading.value = false
    }
  }

  async function login(username, password) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Login failed')
      user.value = data
      return true
    } catch (e) {
      error.value = e.message
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout(router) {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
    user.value = null
    if (router) router.push('/login')
  }

  async function fetchMe() {
    try {
      const res = await fetch('/api/auth/me', { credentials: 'include' })
      if (res.ok) {
        user.value = await res.json()
      }
    } catch (e) {
      // not logged in
    }
  }

  return { user, loading, error, isLoggedIn, register, login, logout, fetchMe }
})
