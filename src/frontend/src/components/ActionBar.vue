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

    <!-- Active conditions badges -->
    <div v-if="activeConditions.length > 0" class="conditions-row">
      <span
        v-for="cond in activeConditions"
        :key="cond"
        class="condition-badge"
        :class="`condition-${cond.toLowerCase().replace(/\s+/g, '-')}`"
        :title="conditionDescriptions[cond] || cond"
      >
        {{ conditionIcon(cond) }} {{ cond }}
      </span>
    </div>

    <!-- Action buttons -->
    <div class="action-buttons">
      <button
        v-for="action in currentActions"
        :key="action.action"
        class="action-btn"
        :class="{ 'action-btn-disabled': isButtonDisabled(action) }"
        :disabled="isButtonDisabled(action)"
        @click="doAction(action.action)"
        :title="buttonTooltip(action)"
      >
        <span class="action-emoji">{{ action.label.split(' ')[0] }}</span>
        <span class="action-text">{{ action.label.split(' ').slice(1).join(' ') }}</span>
      </button>
    </div>

    <!-- Rest buttons (Exploration mode only) -->
    <div v-if="gameMode === 'Exploration' && myCharacterId" class="rest-buttons">
      <button
        class="rest-btn rest-btn-short"
        :disabled="isResting"
        @click="doShortRest"
        title="Short Rest: Roll hit dice to recover HP. Warlocks also recover pact magic slots."
      >
        <span class="rest-emoji">🌙</span>
        <span class="rest-label">Short Rest</span>
        <span class="rest-hint">Roll hit die</span>
      </button>
      <button
        class="rest-btn rest-btn-long"
        :disabled="isResting"
        @click="confirmLongRest"
        title="Long Rest: Restore all HP, spell slots, and abilities."
      >
        <span class="rest-emoji">🌅</span>
        <span class="rest-label">Long Rest</span>
        <span class="rest-hint">Full restore</span>
      </button>
    </div>

    <!-- Long rest confirm overlay -->
    <Teleport to="body">
      <div v-if="showLongRestConfirm" class="rest-overlay" @click.self="showLongRestConfirm = false">
        <div class="rest-confirm-box">
          <div class="rest-confirm-title">Take a Long Rest?</div>
          <p class="rest-confirm-desc">
            The party camps until dawn. All HP, spell slots, and abilities are restored.
            This advances in-game time by 8 hours.
          </p>
          <div class="rest-confirm-actions">
            <button class="rest-confirm-cancel" @click="showLongRestConfirm = false">Cancel</button>
            <button class="rest-confirm-ok" @click="doLongRest">Rest Until Dawn</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
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
  characterConditions: {
    type: Array,
    default: () => [],
  },
})

const showLongRestConfirm = ref(false)
const isResting = ref(false)

const campaignStore = useCampaignStore()

function onWindowKeydown(event) {
  if (!showLongRestConfirm.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopImmediatePropagation()
    showLongRestConfirm.value = false
  }
}

onMounted(() => window.addEventListener('keydown', onWindowKeydown))
onUnmounted(() => window.removeEventListener('keydown', onWindowKeydown))

const ACTIONS = {
  Exploration: [
    { label: '👁 Look Around',  action: 'Look Around',  blockedBy: [] },
    { label: '🔍 Search',       action: 'Search',       blockedBy: ['blinded'] },
    { label: '🚪 Investigate',  action: 'Investigate',  blockedBy: [] },
    { label: '🤫 Stealth',      action: 'Stealth',      blockedBy: ['prone', 'restrained', 'paralyzed'] },
  ],
  Social: [
    { label: '💬 Talk',         action: 'Talk',         blockedBy: ['silenced'] },
    { label: '🤝 Persuade',     action: 'Persuade',     blockedBy: ['silenced'] },
    { label: '😠 Intimidate',   action: 'Intimidate',   blockedBy: ['silenced'] },
    { label: '🎭 Deceive',      action: 'Deceive',      blockedBy: ['silenced'] },
    { label: '👁 Insight',      action: 'Insight',      blockedBy: ['blinded'] },
  ],
  Travel: [
    { label: '🗺 Navigate',     action: 'Navigate',     blockedBy: ['blinded', 'incapacitated'] },
    { label: '🌲 Forage',       action: 'Forage',       blockedBy: ['restrained', 'paralyzed', 'incapacitated'] },
    { label: '🏃 Scout',        action: 'Scout',        blockedBy: ['restrained', 'paralyzed', 'incapacitated'] },
    { label: '⚡ Fast Travel',  action: 'Fast Travel',  blockedBy: ['restrained', 'paralyzed', 'incapacitated'] },
    { label: '🔥 Set Camp',     action: 'Set Camp',     blockedBy: ['incapacitated'] },
  ],
  Combat: [
    { label: '⚔ Attack',       action: 'Attack',       blockedBy: ['unconscious', 'paralyzed', 'petrified', 'incapacitated'] },
    { label: '✨ Cast Spell',   action: 'Cast Spell',   blockedBy: ['silenced', 'unconscious', 'paralyzed', 'petrified', 'incapacitated'] },
    { label: '💨 Dash',         action: 'Dash',         blockedBy: ['unconscious', 'paralyzed', 'petrified', 'restrained', 'incapacitated'] },
    { label: '🛡 Dodge',        action: 'Dodge',        blockedBy: ['unconscious', 'paralyzed', 'petrified', 'incapacitated'] },
    { label: '🤸 Disengage',    action: 'Disengage',    blockedBy: ['unconscious', 'paralyzed', 'petrified', 'restrained', 'incapacitated'] },
    { label: '🤝 Help',         action: 'Help',         blockedBy: ['unconscious', 'paralyzed', 'petrified', 'incapacitated'] },
    { label: '🙈 Hide',         action: 'Hide',         blockedBy: ['unconscious', 'paralyzed', 'petrified', 'restrained', 'incapacitated', 'blinded'] },
    { label: '⏳ Ready',        action: 'Ready',        blockedBy: ['unconscious', 'paralyzed', 'petrified', 'incapacitated'] },
    { label: '🔎 Search',       action: 'Search',       blockedBy: ['unconscious', 'blinded'] },
    { label: '🎒 Use Object',   action: 'Use Object',   blockedBy: ['unconscious', 'paralyzed', 'petrified', 'incapacitated'] },
  ],
}

// Human-readable explanations of each condition
const conditionDescriptions = {
  silenced:      'You cannot speak or cast spells with verbal components.',
  unconscious:   'You are unconscious and cannot take actions.',
  paralyzed:     'You are paralyzed and cannot move or take actions.',
  blinded:       'You cannot see and automatically fail sight-based checks.',
  prone:         'You are prone; movement costs double and ranged attacks are at disadvantage.',
  restrained:    'You are restrained; speed is 0 and attack rolls are at disadvantage.',
  petrified:     'You are petrified and cannot take actions.',
  incapacitated: 'You are incapacitated and cannot take actions.',
  stunned:       'You are stunned; automatically fail STR/DEX saves.',
  poisoned:      'You have disadvantage on attack rolls and ability checks.',
  frightened:    'You are frightened; disadvantage on ability checks and attacks.',
  charmed:       'You are charmed; cannot attack the charmer.',
  exhaustion:    'You suffer levels of exhaustion affecting your abilities.',
}

const activeConditions = computed(() => {
  const conds = (props.characterConditions || []).map(c => c.toLowerCase())
  return [...new Set(conds)]
})

const currentActions = computed(() => {
  return ACTIONS[props.gameMode] || ACTIONS['Exploration']
})

const isMyTurn = computed(() => {
  if (props.gameMode !== 'Combat') return true
  if (props.activeTurn === null) return true
  if (props.myCharacterId === null) return false
  return props.activeTurn === props.myCharacterId
})

const notMyTurn = computed(() => {
  return props.gameMode === 'Combat' && !isMyTurn.value
})

function getBlockingCondition(action) {
  const conds = activeConditions.value
  return (action.blockedBy || []).find(c => conds.includes(c)) || null
}

function isButtonDisabled(action) {
  if (notMyTurn.value) return true
  return getBlockingCondition(action) !== null
}

function buttonTooltip(action) {
  if (notMyTurn.value) return 'Wait for your turn'
  const blocking = getBlockingCondition(action)
  if (blocking) {
    return conditionDescriptions[blocking] || `Disabled: ${blocking}`
  }
  return action.action
}

function conditionIcon(cond) {
  const icons = {
    silenced:      '🤐',
    unconscious:   '💀',
    paralyzed:     '🧊',
    blinded:       '🚫',
    prone:         '⬇',
    restrained:    '⛓',
    petrified:     '🪨',
    incapacitated: '⚡',
    stunned:       '💫',
    poisoned:      '☠',
    frightened:    '😱',
    charmed:       '💝',
    exhaustion:    '😴',
  }
  return icons[cond.toLowerCase()] || '⚠'
}

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

function doShortRest() {
  if (!props.myCharacterId || isResting.value) return
  isResting.value = true
  campaignStore.sendShortRest(props.myCharacterId, 1)
  setTimeout(() => { isResting.value = false }, 3000)
}

function confirmLongRest() {
  if (!props.myCharacterId || isResting.value) return
  showLongRestConfirm.value = true
}

function doLongRest() {
  showLongRestConfirm.value = false
  if (!props.myCharacterId || isResting.value) return
  isResting.value = true
  campaignStore.sendLongRest(props.myCharacterId)
  setTimeout(() => { isResting.value = false }, 3000)
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

/* Conditions row */
.conditions-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-bottom: 0.5rem;
}

.condition-badge {
  font-family: 'Cinzel', serif;
  font-size: 0.6rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  border: 1px solid #7f1d1d;
  background: rgba(139,26,26,0.35);
  color: #fca5a5;
  cursor: help;
}

.condition-unconscious  { border-color: #4b0082; background: rgba(75,0,130,0.35); color: #c084fc; }
.condition-silenced     { border-color: #1e3a5f; background: rgba(30,58,95,0.35); color: #93c5fd; }
.condition-paralyzed    { border-color: #0c4a6e; background: rgba(12,74,110,0.35); color: #7dd3fc; }
.condition-blinded      { border-color: #3d2e10; background: rgba(61,46,16,0.35); color: #fde68a; }
.condition-prone        { border-color: #713f12; background: rgba(113,63,18,0.35); color: #fcd34d; }
.condition-restrained   { border-color: #7f1d1d; background: rgba(127,29,29,0.35); color: #fca5a5; }
.condition-petrified    { border-color: #44403c; background: rgba(68,64,60,0.35); color: #d6d3d1; }
.condition-incapacitated{ border-color: #7f1d1d; background: rgba(139,26,26,0.45); color: #f87171; }
.condition-stunned      { border-color: #3730a3; background: rgba(55,48,163,0.35); color: #a5b4fc; }
.condition-poisoned     { border-color: #14532d; background: rgba(20,83,45,0.35); color: #86efac; }
.condition-frightened   { border-color: #7c2d12; background: rgba(124,45,18,0.35); color: #fdba74; }
.condition-charmed      { border-color: #831843; background: rgba(131,24,67,0.35); color: #f9a8d4; }
.condition-exhaustion   { border-color: #1c1917; background: rgba(28,25,23,0.5); color: #a8a29e; }

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

/* Rest buttons */
.rest-buttons {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid #3d2e10;
}

.rest-btn {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
  font-family: 'Cinzel', serif;
  padding: 0.4rem 0.9rem;
  border-radius: 4px;
  border: 1px solid #3d2e10;
  cursor: pointer;
  transition: all 0.15s ease;
  min-width: 90px;
}

.rest-btn-short {
  background: linear-gradient(135deg, #0f1a2e 0%, #142238 100%);
  color: #93c5fd;
  border-color: #1e3a5f;
}

.rest-btn-long {
  background: linear-gradient(135deg, #1a1109 0%, #2a1a06 100%);
  color: #fde68a;
  border-color: #713f12;
}

.rest-btn:hover:not(:disabled) {
  filter: brightness(1.15);
  transform: translateY(-1px);
  box-shadow: 0 0 8px rgba(147,197,253,0.15);
}

.rest-btn-long:hover:not(:disabled) {
  box-shadow: 0 0 8px rgba(253,230,138,0.15);
}

.rest-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

.rest-emoji {
  font-size: 1rem;
}

.rest-label {
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.rest-hint {
  font-size: 0.55rem;
  opacity: 0.65;
  font-family: 'Crimson Text', serif;
  font-style: italic;
}

/* Long rest confirm overlay */
.rest-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
  padding: 1rem;
}

.rest-confirm-box {
  background: #110d05;
  border: 1px solid #7a6115;
  border-radius: 6px;
  padding: 1.5rem;
  max-width: 380px;
  width: 100%;
  box-shadow: 0 0 24px rgba(201,162,39,0.15);
}

.rest-confirm-title {
  font-family: 'Cinzel', serif;
  font-size: 1.1rem;
  font-weight: 600;
  color: #fde68a;
  margin-bottom: 0.5rem;
}

.rest-confirm-desc {
  font-family: 'Crimson Text', serif;
  color: #8a7355;
  font-size: 0.95rem;
  line-height: 1.5;
  margin-bottom: 1.25rem;
  font-style: italic;
}

.rest-confirm-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.rest-confirm-cancel {
  background: transparent;
  border: 1px solid #3d2e10;
  color: #8a7355;
  cursor: pointer;
  font-family: 'Cinzel', serif;
  font-size: 0.68rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.35rem 0.8rem;
  border-radius: 4px;
  transition: color 0.15s, border-color 0.15s;
}

.rest-confirm-cancel:hover {
  color: #c9a227;
  border-color: #7a6115;
}

.rest-confirm-ok {
  background: linear-gradient(135deg, #1a1109 0%, #2a1a06 100%);
  border: 1px solid #7a6115;
  color: #fde68a;
  cursor: pointer;
  font-family: 'Cinzel', serif;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.35rem 0.8rem;
  border-radius: 4px;
  transition: all 0.15s;
}

.rest-confirm-ok:hover {
  filter: brightness(1.15);
  box-shadow: 0 0 8px rgba(253,230,138,0.2);
}
</style>
