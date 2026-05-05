<template>
  <div class="chat-window">
    <!-- Messages Area -->
    <div ref="messagesEl" class="chat-messages">
      <!-- Empty state -->
      <div v-if="campaignStore.chat.length === 0 && !campaignStore.dmThinking" class="chat-empty">
        <div class="empty-icon">⚔</div>
        <p class="empty-text">Your adventure awaits. Speak your first words...</p>
      </div>

      <!-- Chat messages -->
      <div
        v-for="(msg, idx) in campaignStore.chat"
        :key="idx"
        class="chat-message-wrapper"
        :class="messageWrapperClass(msg)"
      >
        <div :class="messageClass(msg)">
          <span v-if="msg.sender_type === 'DM'" class="chat-sender">
            ⚔ Dungeon Master
          </span>
          <span v-else-if="msg.sender_type === 'PC'" class="chat-sender">
            {{ msg.sender_name || 'Adventurer' }}
          </span>
          <span class="msg-text">{{ msg.text || msg.message || msg.content }}</span>
          <span v-if="msg.timestamp" class="chat-msg-timestamp">
            {{ formatTime(msg.timestamp) }}
          </span>
        </div>
      </div>

      <!-- DM Thinking indicator -->
      <div v-if="campaignStore.dmThinking" class="chat-thinking">
        <div class="thinking-inner">
          <span class="chat-sender">⚔ Dungeon Master</span>
          <div class="thinking-dots">
            <span class="dm-thinking-dot">●</span>
            <span class="dm-thinking-dot">●</span>
            <span class="dm-thinking-dot">●</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Input Row -->
    <div class="chat-input-row">
      <input
        v-model="inputText"
        class="dnd-input chat-input"
        :placeholder="placeholder"
        @keydown.enter.prevent="sendMessage"
        :disabled="!campaignStore.ws || campaignStore.wsStatus !== 'connected'"
      />
      <button
        class="dnd-button send-button"
        @click="sendMessage"
        :disabled="!inputText.trim() || !campaignStore.ws || campaignStore.wsStatus !== 'connected'"
      >
        <span>Send</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
        </svg>
      </button>
    </div>

    <!-- Connection status bar -->
    <div class="connection-status" :class="statusClass">
      <span class="status-dot-sm"></span>
      <span>{{ statusText }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watchEffect, nextTick, computed } from 'vue'
import { useCampaignStore } from '../stores/campaign'

const campaignStore = useCampaignStore()
const messagesEl = ref(null)
const inputText = ref('')

const placeholder = "Speak your mind... (prefix with 'DM:' to command the Dungeon Master)"

function messageClass(msg) {
  const type = (msg.sender_type || '').toUpperCase()
  if (type === 'DM') return 'chat-msg-dm'
  if (type === 'PC') return 'chat-msg-pc'
  return 'chat-msg-system'
}

function messageWrapperClass(msg) {
  const type = (msg.sender_type || '').toUpperCase()
  if (type === 'SYSTEM') return 'msg-wrapper-system'
  return ''
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return
  campaignStore.sendChat(text)
  inputText.value = ''
}

const statusClass = computed(() => {
  switch (campaignStore.wsStatus) {
    case 'connected':    return 'status-connected'
    case 'connecting':   return 'status-connecting'
    case 'disconnected': return 'status-disconnected'
    case 'error':        return 'status-error'
    default:             return 'status-disconnected'
  }
})

const statusText = computed(() => {
  switch (campaignStore.wsStatus) {
    case 'connected':    return 'Connected to game server'
    case 'connecting':   return 'Connecting...'
    case 'disconnected': return 'Disconnected from server'
    case 'error':        return 'Connection error'
    default:             return 'Unknown status'
  }
})

// Auto-scroll to bottom when new messages arrive
watchEffect(async () => {
  // Depend on chat length and dmThinking
  const _len = campaignStore.chat.length
  const _thinking = campaignStore.dmThinking
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
})
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0d0a06;
  border: 1px solid #3d2e10;
  border-radius: 6px;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: 0;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  opacity: 0.4;
  gap: 0.5rem;
}
.empty-icon {
  font-size: 2rem;
  color: #c9a227;
}
.empty-text {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #8a7355;
  text-align: center;
  font-size: 1rem;
}

.chat-message-wrapper {
  display: flex;
}
.msg-wrapper-system {
  justify-content: center;
}

.chat-msg-dm,
.chat-msg-pc,
.chat-msg-system {
  max-width: 92%;
  padding: 0.6rem 0.875rem;
  border-radius: 4px;
  border-left: 3px solid transparent;
}

.chat-msg-dm {
  border-left-color: #7a6115;
  background: rgba(201,162,39,0.06);
}
.chat-msg-pc {
  border-left-color: #3d2e10;
  background: rgba(26,17,9,0.6);
}
.chat-msg-system {
  max-width: 100%;
  background: transparent;
  border-left: none;
  text-align: center;
}

.msg-text {
  display: block;
}

.chat-thinking {
  padding: 0.5rem 0;
}
.thinking-inner {
  background: rgba(201,162,39,0.06);
  border-left: 3px solid #7a6115;
  border-radius: 4px;
  padding: 0.6rem 0.875rem;
  max-width: 92%;
}
.thinking-dots {
  display: inline-flex;
  gap: 0.25rem;
  font-size: 0.8rem;
  color: #c9a227;
  margin-top: 0.25rem;
}

.chat-input-row {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid #3d2e10;
  background: #110d05;
}

.chat-input {
  flex: 1;
  font-size: 0.95rem;
}

.send-button {
  flex-shrink: 0;
  padding: 0.5rem 1rem;
  font-size: 0.78rem;
  gap: 0.35rem;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.2rem 1rem;
  font-family: 'Cinzel', serif;
  font-size: 0.6rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-top: 1px solid #1a1109;
}

.status-dot-sm {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-connected    { color: #86efac; }
.status-connecting   { color: #fde68a; }
.status-disconnected { color: #8a7355; }
.status-error        { color: #f87171; }
</style>
