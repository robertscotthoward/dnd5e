<template>
  <div class="player-card" :class="{ 'is-active-turn': isActiveTurn }">
    <!-- Header: Character name + race/class -->
    <div class="card-header">
      <div class="char-name-row">
        <span class="char-name">{{ player.character_name || 'Unknown' }}</span>
        <span class="dnd-badge dnd-badge-muted">
          {{ player.race || '?' }} {{ player.class_type || '?' }}
        </span>
      </div>
      <div class="username-row">
        <span class="username-label">{{ player.username }}</span>
        <span v-if="isActiveTurn" class="turn-indicator">YOUR TURN</span>
      </div>
    </div>

    <div class="gold-divider-plain"></div>

    <!-- HP Section -->
    <div class="stat-section">
      <div class="stat-header">
        <span class="stat-label">HP</span>
        <span class="stat-numbers">
          <span :class="hpColor">{{ player.hp_current ?? '?' }}</span>
          <span class="stat-sep"> / </span>
          <span class="stat-max">{{ player.hp_max ?? '?' }}</span>
        </span>
      </div>
      <div class="hp-bar-container">
        <div
          class="hp-bar-fill"
          :style="{ '--hp-pct': hpPercent + '%' }"
        ></div>
      </div>
    </div>

    <!-- Encumbrance Section -->
    <div class="stat-section mt-2">
      <div class="stat-header">
        <span class="stat-label">ENC</span>
        <span class="stat-numbers">
          <span class="stat-current">{{ encCurrent }}</span>
          <span class="stat-sep"> / </span>
          <span class="stat-max">{{ encMax }}</span>
          <span class="stat-unit"> lb</span>
        </span>
      </div>
      <div class="enc-bar-container">
        <div
          class="enc-bar-fill"
          :style="{ '--enc-pct': encPercent + '%' }"
        ></div>
      </div>
    </div>

    <!-- Status Badge -->
    <div class="card-footer">
      <div class="status-badge" :class="statusClass">
        <span class="status-dot"></span>
        {{ statusText }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  player: {
    type: Object,
    required: true,
  },
  isActiveTurn: {
    type: Boolean,
    default: false,
  },
})

const hpPercent = computed(() => {
  if (!props.player.hp_max || props.player.hp_max === 0) return 100
  const pct = props.player.hp_percent
  if (pct !== undefined) return Math.max(0, Math.min(100, pct))
  const calc = (props.player.hp_current / props.player.hp_max) * 100
  return Math.max(0, Math.min(100, calc))
})

const hpColor = computed(() => {
  const pct = hpPercent.value
  if (pct > 60) return 'stat-current text-green-400'
  if (pct > 30) return 'stat-current text-yellow-400'
  return 'stat-current text-red-400'
})

const encCurrent = computed(() => {
  return props.player.encumbrance_current !== undefined
    ? Math.round(props.player.encumbrance_current)
    : '?'
})

const encMax = computed(() => {
  return props.player.encumbrance_max !== undefined
    ? Math.round(props.player.encumbrance_max)
    : '?'
})

const encPercent = computed(() => {
  if (!props.player.encumbrance_max || props.player.encumbrance_max === 0) return 0
  const pct = (props.player.encumbrance_current / props.player.encumbrance_max) * 100
  return Math.max(0, Math.min(100, pct))
})

const statusText = computed(() => {
  const s = (props.player.health_status || '').toLowerCase()
  if (s === 'healthy') return 'Healthy'
  if (s === 'bloodied') return 'Bloodied'
  if (s === 'critical') return 'Critical'
  if (s === 'unconscious') return 'Unconscious'
  if (s === 'dead') return 'Dead'
  return props.player.health_status || 'Unknown'
})

const statusClass = computed(() => {
  const s = (props.player.health_status || '').toLowerCase()
  if (s === 'healthy')     return 'status-healthy'
  if (s === 'bloodied')    return 'status-bloodied'
  if (s === 'critical')    return 'status-critical'
  if (s === 'unconscious') return 'status-unconscious'
  if (s === 'dead')        return 'status-dead'
  return 'status-unknown'
})
</script>

<style scoped>
.player-card {
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 6px;
  padding: 0.875rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.player-card.is-active-turn {
  border-color: #c9a227;
  box-shadow: 0 0 12px rgba(201,162,39,0.3);
}

.card-header { margin-bottom: 0.5rem; }

.char-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.char-name {
  font-family: 'Cinzel', serif;
  font-size: 0.95rem;
  font-weight: 600;
  color: #c9a227;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 130px;
}

.username-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.15rem;
}

.username-label {
  font-family: 'Crimson Text', serif;
  font-size: 0.78rem;
  color: #8a7355;
}

.turn-indicator {
  font-family: 'Cinzel', serif;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #c9a227;
  background: rgba(201,162,39,0.15);
  border: 1px solid #7a6115;
  border-radius: 3px;
  padding: 0.1rem 0.4rem;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.stat-section { margin-top: 0.5rem; }

.stat-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 0.3rem;
}

.stat-label {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: #8a7355;
  text-transform: uppercase;
}

.stat-numbers {
  font-family: 'Cinzel', serif;
  font-size: 0.78rem;
  font-weight: 600;
}

.stat-current { font-weight: 700; }
.stat-sep { color: #8a7355; }
.stat-max { color: #8a7355; }
.stat-unit { color: #8a7355; font-size: 0.65rem; }

.card-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.6rem;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-family: 'Cinzel', serif;
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.12rem 0.45rem;
  border-radius: 3px;
  border: 1px solid currentColor;
}

.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.status-healthy    { color: #86efac; border-color: #14532d; background: rgba(26,74,26,0.3); }
.status-bloodied   { color: #fcd34d; border-color: #713f12; background: rgba(113,63,18,0.3); }
.status-critical   { color: #f87171; border-color: #7f1d1d; background: rgba(139,26,26,0.3); }
.status-unconscious{ color: #94a3b8; border-color: #334155; background: rgba(30,41,59,0.4); }
.status-dead       { color: #64748b; border-color: #1e293b; background: rgba(15,23,42,0.5); }
.status-unknown    { color: #8a7355; border-color: #3d2e10; background: rgba(61,46,16,0.2); }

.mt-2 { margin-top: 0.5rem; }
.text-green-400 { color: #4ade80; }
.text-yellow-400 { color: #facc15; }
.text-red-400 { color: #f87171; }
</style>
