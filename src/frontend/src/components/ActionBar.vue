<template>
  <div class="action-bar">
    <!-- Mode badge -->
    <div class="mode-header">
      <span class="mode-label">Mode:</span>
      <span class="dnd-badge mode-badge" :class="modeBadgeClass">
        {{ modeIcon }} {{ gameMode }}
      </span>
      <span v-if="gameMode === 'Combat' && activeTurn !== null" class="turn-info">
        <template v-if="isMyTurn">
          <span class="my-turn-text">YOUR TURN</span>
        </template>
        <template v-else>
          <span class="waiting-turn-text">Waiting for turn...</span>
        </template>
      </span>
    </div>

    <!-- Action buttons -->
    <div class="action-buttons">
      <button
        v-for="action in currentActions"
        :key="action.action"
        class="action-btn"
        :class="{ 'action-btn-disabled': isDisabled }"
        :disabled="isDisabled"
        @click="doAction(action.action)"
        :title="action.action"
      >
        <span class="action-emoji">{{ action.label.split(' ')[0] }}</span>
        <span class="action-text">{{ action.label.split(' ').slice(1).join(' ') }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useCampaignStore } from '../stores/campaign'

const props = defineProps({
  gameMode: {
    type: String,
    default: 'Exploration',
  },
  activeTurn: {
    type: Number,
    default: null,
  },
  myCharacterId: {
    type: Number,
    default: null,
  },
})

const campaignStore = useCampaignStore()

const ACTIONS = {
  Exploration: [
    { label: '👁 Look Around',  action: 'Look Around' },
    { label: '🔍 Search',       action: 'Search' },
    { label: '🚪 Investigate',  action: 'Investigate' },
    { label: '🏕 Rest',         action: 'Rest' },
    { label: '🤫 Stealth',      action: 'Stealth' },
  ],
  Social: [
    { label: '💬 Talk',         action: 'Talk' },
    { label: '🤝 Persuade',     action: 'Persuade' },
    { label: '😠 Intimidate',   action: 'Intimidate' },
    { label: '🎭 Deceive',      action: 'Deceive' },
    { label: '👁 Insight',      action: 'Insight' },
  ],
  Travel: [
    { label: '🗺 Navigate',     action: 'Navigate' },
    { label: '🌲 Forage',       action: 'Forage' },
    { label: '🏃 Scout',        action: 'Scout' },
    { label: '⚡ Fast Travel',  action: 'Fast Travel' },
    { label: '🔥 Set Camp',     action: 'Set Camp' },
  ],
  Combat: [
    { label: '⚔ Attack',       action: 'Attack' },
    { label: '✨ Cast Spell',   action: 'Cast Spell' },
    { label: '💨 Dash',         action: 'Dash' },
    { label: '🛡 Dodge',        action: 'Dodge' },
    { label: '🤸 Disengage',    action: 'Disengage' },
    { label: '🤝 Help',         action: 'Help' },
    { label: '🙈 Hide',         action: 'Hide' },
    { label: '⏳ Ready',        action: 'Ready' },
    { label: '🔎 Search',       action: 'Search' },
    { label: '🎒 Use Object',   action: 'Use Object' },
  ],
}

const currentActions = computed(() => {
  return ACTIONS[props.gameMode] || ACTIONS['Exploration']
})

const isMyTurn = computed(() => {
  if (props.gameMode !== 'Combat') return true
  if (props.activeTurn === null) return true
  if (props.myCharacterId === null) return false
  return props.activeTurn === props.myCharacterId
})

const isDisabled = computed(() => {
  return props.gameMode === 'Combat' && !isMyTurn.value
})

const modeBadgeClass = computed(() => {
  const m = (props.gameMode || '').toLowerCase()
  return `mode-${m}`
})

const modeIcon = computed(() => {
  switch (props.gameMode) {
    case 'Exploration': return '🗺'
    case 'Social':      return '💬'
    case 'Travel':      return '🏃'
    case 'Combat':      return '⚔'
    default:            return '🎲'
  }
})

function doAction(action) {
  campaignStore.sendAction(action)
}
</script>

<style scoped>
.action-bar {
  padding: 0.75rem 1rem;
  background: #110d05;
  border-top: 1px solid #3d2e10;
}

.mode-header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.6rem;
  flex-wrap: wrap;
}

.mode-label {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: #8a7355;
  text-transform: uppercase;
}

.mode-badge {
  font-size: 0.68rem;
  padding: 0.18rem 0.55rem;
}

.my-turn-text {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #c9a227;
  background: rgba(201,162,39,0.15);
  border: 1px solid #7a6115;
  border-radius: 3px;
  padding: 0.12rem 0.45rem;
  animation: blink-gold 1.2s ease-in-out infinite;
}

.waiting-turn-text {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  color: #8a7355;
  font-style: italic;
}

@keyframes blink-gold {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 0.35rem 0.7rem;
  border-radius: 4px;
  border: 1px solid #3d2e10;
  background: linear-gradient(135deg, #1a1109 0%, #221608 100%);
  color: #c9a227;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  text-transform: uppercase;
}

.action-btn:hover:not(:disabled) {
  border-color: #7a6115;
  background: linear-gradient(135deg, #221608 0%, #2e1e09 100%);
  box-shadow: 0 0 8px rgba(201,162,39,0.2);
  transform: translateY(-1px);
}

.action-btn:active:not(:disabled) {
  transform: translateY(0);
}

.action-btn-disabled,
.action-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  transform: none;
}

.action-emoji {
  font-size: 0.85rem;
}

.action-text {
  font-size: 0.68rem;
}
</style>
