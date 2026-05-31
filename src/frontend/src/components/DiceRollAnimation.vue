<template>
  <Transition name="dice-overlay-fade">
    <div v-if="visible" class="dice-roll-overlay">
      <div class="dice-wrap" :class="'phase-' + phase">
        <svg viewBox="0 0 100 100" class="die-svg" xmlns="http://www.w3.org/2000/svg">
          <polygon :points="polyPoints" class="die-poly" />
        </svg>
        <div class="die-face-label">
          <Transition name="label-swap" mode="out-in">
            <span :key="phase === 'revealing' ? 'result' : 'label'">
              {{ phase === 'revealing' ? displayResult : die }}
            </span>
          </Transition>
        </div>
      </div>
      <div class="dice-caption">{{ phase === 'spinning' ? 'Rolling ' + die + '...' : critText }}</div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'

const props = defineProps({
  die:     { type: String,           default: 'd20' },
  result:  { type: [Number, String], default: null  },
  visible: { type: Boolean,          default: false },
})
const emit = defineEmits(['done'])

const phase = ref('idle') // idle | spinning | revealing

const displayResult = computed(() => (props.result !== null ? String(props.result) : '?'))

const critText = computed(() => {
  if (phase.value !== 'revealing') return ''
  const r = Number(props.result)
  if (!r) return ''
  if (props.die === 'd20' && r === 20) return 'Critical Hit!'
  if (props.die === 'd20' && r === 1)  return 'Critical Miss!'
  return ''
})

const polyPoints = computed(() => {
  const shapes = {
    d4:  '50,8 92,88 8,88',
    d6:  '12,12 88,12 88,88 12,88',
    d8:  '50,4 96,50 50,96 4,50',
    d10: '50,6 90,62 50,94 10,62',
    d12: '50,6 88,35 76,80 24,80 12,35',
    d20: '50,4 88,26 88,74 50,96 12,74 12,26',
  }
  return shapes[props.die] || shapes.d20
})

const _timers = []

function clearTimers() {
  while (_timers.length) clearTimeout(_timers.pop())
}

watch(() => props.visible, (val) => {
  clearTimers()
  if (val) {
    phase.value = 'spinning'
    _timers.push(setTimeout(() => { phase.value = 'revealing' }, 900))
    _timers.push(setTimeout(() => { emit('done') },              2300))
  } else {
    phase.value = 'idle'
  }
})

onUnmounted(clearTimers)
</script>

<style scoped>
.dice-roll-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(13, 10, 6, 0.82);
  z-index: 10;
  pointer-events: none;
  border-radius: inherit;
}

.dice-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 110px;
  height: 110px;
}

/* ── Die SVG ── */
.die-svg {
  width: 100px;
  height: 100px;
  filter: drop-shadow(0 0 8px rgba(201, 162, 39, 0.5));
}

.die-poly {
  fill: rgba(201, 162, 39, 0.12);
  stroke: #c9a227;
  stroke-width: 3;
  stroke-linejoin: round;
}

/* ── Face label (die type / result) ── */
.die-face-label {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-family: 'Cinzel', serif;
  font-weight: 700;
  font-size: 1.35rem;
  color: #c9a227;
  text-align: center;
  pointer-events: none;
  width: 60px;
}

/* ── Caption row ── */
.dice-caption {
  margin-top: 0.75rem;
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #8a7355;
  height: 1.2em;
  transition: color 0.3s;
}

/* Critical colours */
.phase-revealing .die-poly {
  stroke: #f5c518;
}

/* ── Spin phase ── */
@keyframes die-spin {
  0%   { transform: rotate(0deg)   scale(0.7); opacity: 0.4; }
  15%  { opacity: 1; }
  100% { transform: rotate(720deg) scale(1.0); opacity: 1; }
}

.phase-spinning .die-svg {
  animation: die-spin 0.9s cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
}

/* ── Reveal phase ── */
@keyframes die-reveal {
  0%   { transform: scale(1.0); }
  30%  { transform: scale(1.18); }
  100% { transform: scale(1.0); }
}

.phase-revealing .die-svg {
  animation: die-reveal 0.35s ease-out forwards;
}

@keyframes result-pop {
  0%   { transform: translate(-50%, -50%) scale(0.3); opacity: 0; }
  55%  { transform: translate(-50%, -50%) scale(1.3); opacity: 1; }
  100% { transform: translate(-50%, -50%) scale(1.0); opacity: 1; }
}

.phase-revealing .die-face-label {
  font-size: 1.9rem;
  color: #f5c518;
  animation: result-pop 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}

/* ── Overlay enter/leave ── */
.dice-overlay-fade-enter-active {
  transition: opacity 0.25s ease;
}
.dice-overlay-fade-leave-active {
  transition: opacity 0.45s ease;
}
.dice-overlay-fade-enter-from,
.dice-overlay-fade-leave-to {
  opacity: 0;
}

/* ── Label swap ── */
.label-swap-enter-active,
.label-swap-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.label-swap-enter-from { opacity: 0; transform: translateY(-6px); }
.label-swap-leave-to   { opacity: 0; transform: translateY( 6px); }
</style>
