<template>
  <div class="chat-window">
    <!-- Dice roll animation overlay -->
    <DiceRollAnimation
      :visible="!!campaignStore.pendingDiceRoll"
      :die="campaignStore.pendingDiceRoll?.die || 'd20'"
      :result="campaignStore.pendingDiceRoll?.result"
      @done="campaignStore.clearDiceRoll()"
    />

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
            {{ msg.sender || msg.sender_name || 'Adventurer' }}
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

    <!-- Slash-command dropdown -->
    <div v-if="slashMenuOpen" class="slash-menu" ref="slashMenuEl">
      <div
        v-for="(cmd, idx) in filteredCommands"
        :key="cmd.name"
        class="slash-item"
        :class="{ 'slash-item-active': idx === slashIndex }"
        @mousedown.prevent="selectCommand(cmd)"
      >
        <span class="slash-name">{{ cmd.name }}</span>
        <span class="slash-desc">{{ cmd.description }}</span>
      </div>
      <div v-if="filteredCommands.length === 0" class="slash-empty">No matching commands</div>
    </div>

    <!-- Input Row -->
    <div class="chat-input-row">
      <input
        ref="inputEl"
        v-model="inputText"
        class="dnd-input chat-input"
        :placeholder="placeholder"
        @keydown="onKeydown"
        @input="onInput"
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
import { ref, computed, watchEffect, nextTick } from 'vue'
import { useCampaignStore } from '../stores/campaign'
import DiceRollAnimation from './DiceRollAnimation.vue'

const campaignStore = useCampaignStore()
const messagesEl = ref(null)
const inputEl = ref(null)
const slashMenuEl = ref(null)
const inputText = ref('')
const slashIndex = ref(0)

// --- Slash commands registry ---
// Commands with hasArg:true are autocompleted with a trailing space so the user
// can keep typing the argument before hitting Enter.
const SLASH_COMMANDS = [
  {
    name: '/clear',
    description: 'Clear the local chat history',
    hasArg: false,
    action: () => { campaignStore.clearChat() },
  },
  {
    name: '/requirement',
    description: 'Add a requirement — /requirement <text>',
    hasArg: true,
    action: null, // handled in sendMessage
  },
]

// Only show the dropdown when the user is still typing the command name itself
// (no space yet after the slash), so /requirement <text> doesn't re-open it.
const slashMenuOpen = computed(() => {
  const t = inputText.value
  return t.startsWith('/') && !t.includes(' ')
})

const filteredCommands = computed(() => {
  const q = inputText.value.toLowerCase()
  return SLASH_COMMANDS.filter(c => c.name.startsWith(q))
})

const placeholder = "Speak your mind... (prefix with 'DM:' to command the Dungeon Master)"

// Reset selection index whenever the filtered list changes
watchEffect(() => {
  if (filteredCommands.value.length > 0) slashIndex.value = 0
})

function onInput() {
  // Keep selection in bounds as the user types
  slashIndex.value = 0
}

function onKeydown(e) {
  if (slashMenuOpen.value && filteredCommands.value.length > 0) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      slashIndex.value = (slashIndex.value + 1) % filteredCommands.value.length
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      slashIndex.value = (slashIndex.value - 1 + filteredCommands.value.length) % filteredCommands.value.length
      return
    }
    if (e.key === 'Tab') {
      e.preventDefault()
      selectCommand(filteredCommands.value[slashIndex.value])
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      // If the typed text is an exact command, run it; otherwise autocomplete
      const exact = SLASH_COMMANDS.find(c => c.name === inputText.value.trim())
      if (exact) {
        selectCommand(exact)
      } else {
        selectCommand(filteredCommands.value[slashIndex.value])
      }
      return
    }
    if (e.key === 'Escape') {
      inputText.value = ''
      return
    }
  }
  // Normal Enter for chat
  if (e.key === 'Enter') {
    e.preventDefault()
    sendMessage()
  }
}

function selectCommand(cmd) {
  if (!cmd) return
  if (cmd.hasArg) {
    // Autocomplete to "/command " and let the user type the argument
    inputText.value = cmd.name + ' '
    nextTick(() => inputEl.value?.focus())
    return
  }
  cmd.action()
  inputText.value = ''
  nextTick(() => inputEl.value?.focus())
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return

  // Handle /requirement <text>
  if (text.startsWith('/requirement ')) {
    const reqText = text.slice('/requirement '.length).trim()
    if (!reqText) return
    inputText.value = ''
    try {
      await fetch(`/api/campaigns/${campaignStore.currentMeta?.id}/requirements`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: reqText }),
      })
    } catch (e) {
      campaignStore.chat.push({
        sender_type: 'SYSTEM',
        text: '[Failed to submit requirement — server unreachable]',
      })
    }
    return
  }

  // Ignore bare slash commands that weren't dispatched
  if (text.startsWith('/')) return

  campaignStore.sendChat(text)
  inputText.value = ''
}

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
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

const statusClass = computed(() => ({
  'status-connected':    campaignStore.wsStatus === 'connected',
  'status-connecting':   campaignStore.wsStatus === 'connecting',
  'status-disconnected': campaignStore.wsStatus === 'disconnected',
  'status-error':        campaignStore.wsStatus === 'error',
}))

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
  const _len = campaignStore.chat.length
  const _thinking = campaignStore.dmThinking
  await nextTick()
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
})
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
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

/* Slash-command dropdown */
.slash-menu {
  position: relative;
  border-top: 1px solid #3d2e10;
  background: #110d05;
  padding: 0.25rem 0;
  z-index: 10;
}

.slash-item {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  padding: 0.45rem 1rem;
  cursor: pointer;
  transition: background 0.1s;
}

.slash-item:hover,
.slash-item-active {
  background: rgba(201, 162, 39, 0.1);
}

.slash-name {
  font-family: 'Cinzel', serif;
  font-size: 0.82rem;
  font-weight: 600;
  color: #c9a227;
  white-space: nowrap;
}

.slash-desc {
  font-family: 'Crimson Text', serif;
  font-size: 0.88rem;
  color: #8a7355;
  font-style: italic;
}

.slash-empty {
  padding: 0.4rem 1rem;
  font-family: 'Crimson Text', serif;
  font-size: 0.85rem;
  color: #5a4530;
  font-style: italic;
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
