<template>
  <div class="min-h-screen bg-dnd-dark text-dnd-parchment font-crimson">
    <NavBar />
    <main class="pt-16">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import NavBar from './components/NavBar.vue'
</script>
