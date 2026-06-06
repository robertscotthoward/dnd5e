<template>
  <div class="min-h-screen bg-dnd-dark text-dnd-parchment font-crimson">
    <NavBar />
    <main class="pt-16">
      <RouterView />
    </main>
    <HelpOverlay v-model:visible="helpVisible" />

    <!-- Server-down toast -->
    <Transition name="server-toast">
      <div v-if="campaignStore.serverDown" class="server-down-toast">
        <span class="toast-icon">⚠</span>
        <span class="toast-msg">Server unreachable — your action was not sent.</span>
        <button class="toast-reconnect" @click="reconnect">Reconnect</button>
        <button class="toast-dismiss" @click="campaignStore.serverDown = false">✕</button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import NavBar from './components/NavBar.vue'
import HelpOverlay from './components/HelpOverlay.vue'
import { useCampaignStore } from './stores/campaign'

const helpVisible = ref(false)
const campaignStore = useCampaignStore()

function reconnect() {
  if (campaignStore.currentMeta?.id) {
    campaignStore.connectWs(campaignStore.currentMeta.id)
  }
}

function onKeydown(event) {
  if (event.key === 'F1') {
    event.preventDefault()
    helpVisible.value = !helpVisible.value
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.server-down-toast {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: linear-gradient(to right, #3b0a0a, #1f0505);
  border: 1px solid #b91c1c;
  border-radius: 8px;
  padding: 0.65rem 1.1rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.7), 0 0 0 1px rgba(185,28,28,0.3);
  z-index: 9999;
  font-family: 'Crimson Text', serif;
  font-size: 0.95rem;
  color: #fca5a5;
  white-space: nowrap;
}

.toast-icon {
  font-size: 1.1rem;
  color: #f87171;
}

.toast-msg {
  color: #fecaca;
}

.toast-reconnect {
  background: #7f1d1d;
  border: 1px solid #b91c1c;
  border-radius: 4px;
  color: #fca5a5;
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 0.2rem 0.6rem;
  cursor: pointer;
  transition: background 0.15s;
}
.toast-reconnect:hover {
  background: #991b1b;
  color: #fee2e2;
}

.toast-dismiss {
  background: none;
  border: none;
  color: #9ca3af;
  font-size: 0.85rem;
  cursor: pointer;
  padding: 0 0.1rem;
  line-height: 1;
}
.toast-dismiss:hover {
  color: #f87171;
}

.server-toast-enter-active,
.server-toast-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.server-toast-enter-from,
.server-toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(1rem);
}
</style>
