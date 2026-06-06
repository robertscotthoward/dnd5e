<template>
  <div class="min-h-screen bg-dnd-dark text-dnd-parchment font-crimson">
    <NavBar />
    <main class="pt-16">
      <RouterView />
    </main>
    <HelpOverlay v-model:visible="helpVisible" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import NavBar from './components/NavBar.vue'
import HelpOverlay from './components/HelpOverlay.vue'

const helpVisible = ref(false)

function onKeydown(event) {
  if (event.key === 'F1') {
    event.preventDefault()
    helpVisible.value = !helpVisible.value
  }
  if (event.key === 'Escape' && helpVisible.value) {
    helpVisible.value = false
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>
