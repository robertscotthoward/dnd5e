<template>
  <Teleport to="body">
    <div v-if="levelUp" class="modal-overlay" @click.self="dismiss">
      <div class="modal-box dnd-panel dnd-panel-gold level-up-box">
        <div class="lu-header">
          <div class="lu-star-row">
            <span class="lu-star">&#9733;</span>
            <span class="lu-star lu-star-lg">&#9733;</span>
            <span class="lu-star">&#9733;</span>
          </div>
          <h2 class="lu-title">Level Up!</h2>
          <p class="lu-subtitle">
            {{ levelUp.character_name }} reaches
            <strong class="lu-level">Level {{ levelUp.new_level }}</strong>
          </p>
        </div>

        <hr class="gold-divider-plain" />

        <!-- Hit Die Roll -->
        <div class="lu-section">
          <div class="lu-section-label">Hit Die (d{{ levelUp.hit_die }})</div>
          <div class="lu-roll-row">
            <button
              class="dnd-button lu-roll-btn"
              :disabled="hpRolled"
              @click="rollHitDie"
            >
              Roll d{{ levelUp.hit_die }}
            </button>
            <span v-if="hpRolled" class="lu-roll-result">+{{ hpGain }} HP</span>
          </div>
        </div>

        <!-- ASI Section -->
        <div v-if="levelUp.has_asi" class="lu-section">
          <div class="lu-section-label">Ability Score Improvement</div>
          <p class="lu-asi-desc">
            You may increase two ability scores by 1 each, or one score by 2.
          </p>
          <div class="lu-asi-grid">
            <div v-for="ab in abilities" :key="ab.key" class="lu-asi-row">
              <span class="lu-ab-name">{{ ab.label }}</span>
              <div class="lu-ab-controls">
                <button
                  class="lu-adj-btn"
                  :disabled="ab.bonus === 0"
                  @click="adjustAsi(ab.key, -1)"
                >-</button>
                <span class="lu-ab-bonus">{{ ab.bonus > 0 ? '+' + ab.bonus : ab.bonus }}</span>
                <button
                  class="lu-adj-btn"
                  :disabled="asiPointsRemaining === 0"
                  @click="adjustAsi(ab.key, 1)"
                >+</button>
              </div>
            </div>
          </div>
          <div class="lu-asi-points">
            Points remaining: <strong>{{ asiPointsRemaining }}</strong>
          </div>
        </div>

        <!-- Class Features note -->
        <div class="lu-section lu-features">
          <div class="lu-section-label">New Class Features</div>
          <p class="lu-features-text parchment-text">
            As a level {{ levelUp.new_level }} {{ levelUp.class_type }}, consult your class table
            for new features, spells, and abilities.
          </p>
        </div>

        <div class="modal-actions">
          <button
            class="dnd-button"
            :disabled="!canConfirm"
            @click="confirm"
          >
            Confirm Level Up
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useCampaignStore } from '../stores/campaign'

const campaignStore = useCampaignStore()

const props = defineProps({
  campaignId: { type: String, required: true },
})
const emit = defineEmits(['confirmed'])

const levelUp = computed(() => campaignStore.pendingLevelUp)

const hpRolled = ref(false)
const hpGain = ref(0)

const ASI_TOTAL = 2
const asiAllocated = ref(0)
const abilities = ref([
  { key: 'str', label: 'Strength',     bonus: 0 },
  { key: 'dex', label: 'Dexterity',    bonus: 0 },
  { key: 'con', label: 'Constitution', bonus: 0 },
  { key: 'int', label: 'Intelligence', bonus: 0 },
  { key: 'wis', label: 'Wisdom',       bonus: 0 },
  { key: 'chr', label: 'Charisma',     bonus: 0 },
])

const asiPointsRemaining = computed(() => ASI_TOTAL - asiAllocated.value)

const canConfirm = computed(() => {
  if (!levelUp.value) return false
  if (!hpRolled.value) return false
  // ASI must be fully allocated if available
  if (levelUp.value.has_asi && asiAllocated.value < ASI_TOTAL) return false
  return true
})

function rollHitDie() {
  if (!levelUp.value) return
  const sides = levelUp.value.hit_die || 8
  hpGain.value = Math.floor(Math.random() * sides) + 1
  hpRolled.value = true
}

function adjustAsi(key, delta) {
  const ab = abilities.value.find(a => a.key === key)
  if (!ab) return
  const newBonus = ab.bonus + delta
  if (newBonus < 0) return
  if (delta > 0 && asiAllocated.value >= ASI_TOTAL) return
  ab.bonus = newBonus
  asiAllocated.value += delta
}

async function confirm() {
  if (!levelUp.value || !canConfirm.value) return

  // Apply HP gain via set_object_property is handled by the DM agent;
  // here we just send the choices back via the REST endpoint so the
  // backend can persist them.
  const charId = levelUp.value.character_id
  const asiChoices = abilities.value
    .filter(a => a.bonus > 0)
    .reduce((acc, a) => { acc[a.key] = a.bonus; return acc }, {})

  try {
    await fetch(`/api/campaigns/${props.campaignId}/characters/${charId}/level-up`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hp_gain: hpGain.value, asi_choices: asiChoices }),
      credentials: 'include',
    })
  } catch (_) {
    // best-effort; the level is already saved server-side
  }

  emit('confirmed', { hpGain: hpGain.value, asiChoices })
  campaignStore.clearLevelUp()
  hpRolled.value = false
  hpGain.value = 0
  asiAllocated.value = 0
  abilities.value.forEach(a => { a.bonus = 0 })
}

function dismiss() {
  // Only close if confirmed, otherwise force them through the flow
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.82);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
  padding: 1rem;
}

.level-up-box {
  max-width: 480px;
  width: 100%;
  animation: lu-appear 0.3s ease;
}

@keyframes lu-appear {
  from { opacity: 0; transform: scale(0.92) translateY(-12px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}

.lu-header {
  text-align: center;
  margin-bottom: 0.75rem;
}

.lu-star-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.35rem;
}

.lu-star {
  color: #c9a227;
  font-size: 1.1rem;
}
.lu-star-lg {
  font-size: 1.6rem;
}

.lu-title {
  font-family: 'Cinzel', serif;
  font-size: 1.6rem;
  font-weight: 700;
  color: #c9a227;
  text-shadow: 0 0 16px rgba(201,162,39,0.5);
  margin: 0 0 0.2rem;
}

.lu-subtitle {
  font-family: 'Crimson Text', serif;
  font-size: 1.05rem;
  color: #e8d5b7;
  margin: 0;
}

.lu-level {
  color: #c9a227;
}

.lu-section {
  margin-top: 1rem;
}

.lu-section-label {
  font-family: 'Cinzel', serif;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #8a7355;
  margin-bottom: 0.5rem;
}

.lu-roll-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.lu-roll-btn {
  min-width: 100px;
}

.lu-roll-result {
  font-family: 'Cinzel', serif;
  font-size: 1.1rem;
  font-weight: 700;
  color: #4ade80;
}

.lu-asi-desc {
  font-family: 'Crimson Text', serif;
  font-size: 0.92rem;
  color: #8a7355;
  font-style: italic;
  margin: 0 0 0.6rem;
}

.lu-asi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem 1rem;
  margin-bottom: 0.5rem;
}

.lu-asi-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.lu-ab-name {
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  color: #e8d5b7;
}

.lu-ab-controls {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.lu-adj-btn {
  width: 22px;
  height: 22px;
  background: #1a1109;
  border: 1px solid #3d2e10;
  color: #c9a227;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.85rem;
  line-height: 1;
  transition: border-color 0.15s;
}
.lu-adj-btn:hover:not(:disabled) {
  border-color: #c9a227;
}
.lu-adj-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.lu-ab-bonus {
  font-family: 'Cinzel', serif;
  font-size: 0.82rem;
  font-weight: 600;
  color: #c9a227;
  min-width: 24px;
  text-align: center;
}

.lu-asi-points {
  font-family: 'Cinzel', serif;
  font-size: 0.68rem;
  color: #8a7355;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.lu-features-text {
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0;
  color: #8a7355;
  font-style: italic;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 1.25rem;
}
</style>
