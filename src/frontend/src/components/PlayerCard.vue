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

    <!-- Location ancestry -->
    <div v-if="locationAncestry.length > 0" class="location-ancestry">
      <span
        v-for="(anc, i) in locationAncestry"
        :key="i"
        class="anc-item"
      >{{ anc.name }} <em class="anc-type">({{ anc.type }})</em><span v-if="i < locationAncestry.length - 1" class="anc-sep"> → </span></span>
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

    <!-- Conditions badges -->
    <div v-if="conditions.length > 0" class="conditions-section">
      <span
        v-for="cond in conditions"
        :key="cond"
        class="condition-badge"
        :class="conditionClass(cond)"
        :title="cond"
      >{{ cond }}</span>
    </div>

    <!-- Death Saves Panel (only shown when HP = 0) -->
    <div v-if="isUnconscious" class="death-saves-panel">
      <div class="ds-label">Death Saves</div>
      <div class="ds-rows">
        <div class="ds-row">
          <span class="ds-row-label success">S</span>
          <span
            v-for="n in 3"
            :key="'s' + n"
            class="ds-pip pip-success"
            :class="{ filled: n <= deathSaveSuccesses }"
          ></span>
        </div>
        <div class="ds-row">
          <span class="ds-row-label failure">F</span>
          <span
            v-for="n in 3"
            :key="'f' + n"
            class="ds-pip pip-failure"
            :class="{ filled: n <= deathSaveFailures }"
          ></span>
        </div>
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

const locationAncestry = computed(() => {
  return Array.isArray(props.player.location_ancestry) ? props.player.location_ancestry : []
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

const conditions = computed(() => {
  return Array.isArray(props.player.conditions) ? props.player.conditions : []
})

const DEBILITATING = new Set([
  'blinded', 'charmed', 'deafened', 'exhaustion', 'frightened',
  'incapacitated', 'invisible', 'paralyzed', 'petrified', 'poisoned',
  'restrained', 'stunned', 'unconscious',
])

function conditionClass(cond) {
  const key = cond.toLowerCase()
  if (key === 'poisoned') return 'cond-poison'
  if (key === 'blinded' || key === 'deafened') return 'cond-sensory'
  if (key === 'prone') return 'cond-prone'
  if (key === 'restrained' || key === 'paralyzed' || key === 'petrified' || key === 'stunned') return 'cond-restrained'
  if (key === 'frightened' || key === 'charmed') return 'cond-mental'
  if (key === 'exhaustion') return 'cond-exhaustion'
  if (key === 'incapacitated' || key === 'unconscious') return 'cond-incapacitated'
  if (key === 'invisible') return 'cond-invisible'
  if (DEBILITATING.has(key)) return 'cond-debuff'
  return 'cond-neutral'
}

const isUnconscious = computed(() => {
  return props.player.hp_current !== undefined && props.player.hp_current <= 0 && props.player.hp_max > 0
})

const deathSaveSuccesses = computed(() => {
  return props.player.death_saves?.successes ?? 0
})

const deathSaveFailures = computed(() => {
  return props.player.death_saves?.failures ?? 0
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

/* Death Saves Panel */
.death-saves-panel {
  margin-top: 0.5rem;
  padding: 0.4rem 0.5rem;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid #334155;
  border-radius: 4px;
}

.ds-label {
  font-family: 'Cinzel', serif;
  font-size: 0.58rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #94a3b8;
  margin-bottom: 0.3rem;
}

.ds-rows {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.ds-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.ds-row-label {
  font-family: 'Cinzel', serif;
  font-size: 0.58rem;
  font-weight: 700;
  width: 10px;
  text-align: center;
}
.ds-row-label.success { color: #86efac; }
.ds-row-label.failure { color: #f87171; }

.ds-pip {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid;
  transition: background 0.2s, box-shadow 0.2s;
}

.pip-success {
  border-color: #14532d;
  background: transparent;
}
.pip-success.filled {
  background: #86efac;
  border-color: #86efac;
  box-shadow: 0 0 4px rgba(134,239,172,0.6);
}

.pip-failure {
  border-color: #7f1d1d;
  background: transparent;
}
.pip-failure.filled {
  background: #f87171;
  border-color: #f87171;
  box-shadow: 0 0 4px rgba(248,113,113,0.6);
}

.mt-2 { margin-top: 0.5rem; }
.text-green-400 { color: #4ade80; }
.text-yellow-400 { color: #facc15; }
.text-red-400 { color: #f87171; }

/* Condition badges */
.conditions-section {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  margin-top: 0.5rem;
}

.condition-badge {
  display: inline-block;
  font-family: 'Cinzel', serif;
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  border: 1px solid;
  white-space: nowrap;
}

.cond-poison     { color: #86efac; border-color: #14532d; background: rgba(34,197,94,0.15); }
.cond-sensory    { color: #94a3b8; border-color: #334155; background: rgba(51,65,85,0.3); }
.cond-prone      { color: #fcd34d; border-color: #713f12; background: rgba(113,63,18,0.2); }
.cond-restrained { color: #f87171; border-color: #7f1d1d; background: rgba(139,26,26,0.25); }
.cond-mental     { color: #c084fc; border-color: #6b21a8; background: rgba(107,33,168,0.2); }
.cond-exhaustion { color: #fb923c; border-color: #7c2d12; background: rgba(124,45,18,0.2); }
.cond-incapacitated { color: #64748b; border-color: #1e293b; background: rgba(15,23,42,0.5); }
.cond-invisible  { color: #e2e8f0; border-color: #475569; background: rgba(71,85,105,0.15); }
.cond-debuff     { color: #f87171; border-color: #7f1d1d; background: rgba(139,26,26,0.2); }
.cond-neutral    { color: #8a7355; border-color: #3d2e10; background: rgba(61,46,16,0.2); }

/* Location ancestry */
.location-ancestry {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0;
  margin-top: 0.25rem;
  margin-bottom: 0.1rem;
  line-height: 1.4;
}

.anc-item {
  font-family: 'Crimson Text', serif;
  font-size: 0.72rem;
  color: #7a6540;
  white-space: nowrap;
}

.anc-type {
  color: #5a4a30;
  font-style: italic;
}

.anc-sep {
  color: #4a3a22;
  margin: 0 0.1rem;
}
</style>
