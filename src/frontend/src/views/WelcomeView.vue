<template>
  <div style="font-family: sans-serif; max-width: 600px; margin: 80px auto; text-align: center;">
    <h1>D&D 5e AI Game Engine</h1>
    <p>An AI-powered Dungeons &amp; Dragons 5th Edition game engine with agents for the Dungeon Master, players, and world simulation.</p>

    <button @click="checkHealth" :disabled="loading" style="padding: 10px 24px; font-size: 1rem; cursor: pointer;">
      {{ loading ? 'Checking...' : 'Check API Health' }}
    </button>

    <div v-if="result !== null" style="margin-top: 20px; padding: 12px; background: #f0f0f0; border-radius: 6px;">
      <strong>API Response:</strong>
      <pre style="text-align: left; margin-top: 8px;">{{ JSON.stringify(result, null, 2) }}</pre>
    </div>

    <div v-if="error" style="margin-top: 20px; color: red;">
      Error: {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const result = ref(null)
const error = ref(null)
const loading = ref(false)

async function checkHealth() {
  loading.value = true
  error.value = null
  result.value = null
  try {
    const response = await fetch('/api/health')
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    result.value = await response.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>
