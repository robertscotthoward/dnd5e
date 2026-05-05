<template>
  <div class="char-creator">
    <!-- Step dots -->
    <div class="step-dots">
      <div
        v-for="s in TOTAL_STEPS"
        :key="s"
        class="step-dot"
        :class="{ active: s === currentStep, done: s < currentStep }"
        @click="s < currentStep ? currentStep = s : null"
      >
        <span v-if="s < currentStep">✓</span>
        <span v-else>{{ s }}</span>
      </div>
    </div>

    <hr class="gold-divider-plain" />

    <!-- STEP 1: Name -->
    <div v-if="currentStep === 1" class="step-panel fade-in-up">
      <h3 class="step-title">What is your name, adventurer?</h3>
      <p class="step-desc">Choose a name that will echo through the halls of history.</p>
      <div class="form-field">
        <label class="dnd-label">Character Name</label>
        <input
          v-model="form.name"
          class="dnd-input"
          placeholder="e.g. Aranea Shadowmere"
          maxlength="50"
          @keydown.enter="nextStep"
        />
      </div>
    </div>

    <!-- STEP 2: Region -->
    <div v-else-if="currentStep === 2" class="step-panel fade-in-up">
      <h3 class="step-title">Where do you hail from?</h3>
      <p class="step-desc">Your homeland shapes your history and knowledge of the world.</p>
      <div class="region-grid">
        <button
          v-for="region in REGIONS"
          :key="region"
          class="region-btn"
          :class="{ selected: form.region === region }"
          @click="form.region = region"
        >
          {{ region }}
        </button>
      </div>
    </div>

    <!-- STEP 3: Race -->
    <div v-else-if="currentStep === 3" class="step-panel fade-in-up">
      <h3 class="step-title">Choose your race</h3>
      <p class="step-desc">Your ancestry grants you unique gifts and shapes who you are.</p>
      <div class="race-grid">
        <button
          v-for="race in RACES"
          :key="race.name"
          class="race-card"
          :class="{ selected: form.race === race.name }"
          @click="form.race = race.name"
        >
          <span class="race-emoji">{{ race.emoji }}</span>
          <span class="race-name">{{ race.name }}</span>
          <span class="race-bonus">{{ race.bonus }}</span>
        </button>
      </div>
    </div>

    <!-- STEP 4: Class -->
    <div v-else-if="currentStep === 4" class="step-panel fade-in-up">
      <h3 class="step-title">Choose your class</h3>
      <p class="step-desc">Your calling defines your skills and powers in the world.</p>
      <div class="class-grid">
        <button
          v-for="cls in CLASSES"
          :key="cls.name"
          class="class-card"
          :class="{ selected: form.classType === cls.name }"
          @click="form.classType = cls.name"
        >
          <span class="class-emoji">{{ cls.emoji }}</span>
          <span class="class-name">{{ cls.name }}</span>
          <span class="class-hit-die">{{ cls.hitDie }}</span>
          <span class="class-role">{{ cls.role }}</span>
        </button>
      </div>
    </div>

    <!-- STEP 5: Roll Stats -->
    <div v-else-if="currentStep === 5" class="step-panel fade-in-up">
      <h3 class="step-title">Roll Your Ability Scores</h3>
      <p class="step-desc">4d6 drop lowest — the fates decide your potential.</p>

      <div v-if="rolling" class="loading-bg">
        <div class="spinner"></div>
        <span class="loading-text">The dice tumble across the table...</span>
      </div>

      <div v-else-if="rollData">
        <!-- Abilities table -->
        <div class="abilities-table">
          <div class="abilities-header">
            <span>Ability</span>
            <span class="header-dice">Dice (4d6 drop lowest)</span>
            <span class="header-base">Base</span>
            <span class="header-racial">Racial</span>
            <span class="header-bonus">Bonus d{{ rollData.bonus_die }} <span class="bonus-pip">{{ rollData.bonus_die }}</span></span>
            <span class="header-final">Final</span>
          </div>

          <div
            v-for="ab in ABILITIES"
            :key="ab"
            class="ability-row"
            :class="{ 'row-boosted': bonusAllocation[ab] > 0 }"
          >
            <!-- Label -->
            <span class="ab-label">{{ AB_LABELS[ab] }}</span>

            <!-- Dice display: kept (gold) + dropped (dim) -->
            <div class="dice-group">
              <span
                v-for="(d, i) in rollData.rolls[ab].kept"
                :key="'k' + i"
                class="die die-kept"
              >{{ d }}</span>
              <span class="die die-dropped" title="Dropped">{{ rollData.rolls[ab].dropped }}</span>
            </div>

            <!-- Base total -->
            <span class="ab-base">{{ rollData.rolls[ab].total }}</span>

            <!-- Racial bonus -->
            <span
              class="ab-racial"
              :class="rollData.racial_bonuses[ab] ? 'racial-positive' : 'racial-zero'"
            >
              {{ rollData.racial_bonuses[ab] ? '+' + rollData.racial_bonuses[ab] : '—' }}
            </span>

            <!-- Bonus allocation controls -->
            <div class="bonus-alloc">
              <button
                class="alloc-btn"
                @click="removeBonus(ab)"
                :disabled="bonusAllocation[ab] === 0"
              >−</button>
              <span class="alloc-val" :class="{ 'alloc-active': bonusAllocation[ab] > 0 }">
                {{ bonusAllocation[ab] > 0 ? '+' + bonusAllocation[ab] : '·' }}
              </span>
              <button
                class="alloc-btn"
                @click="addBonus(ab)"
                :disabled="bonusRemaining === 0"
              >+</button>
            </div>

            <!-- Final score -->
            <span class="ab-final">
              {{ rollData.rolls[ab].total + (rollData.racial_bonuses[ab] || 0) + bonusAllocation[ab] }}
            </span>
          </div>
        </div>

        <!-- Bonus die summary -->
        <div class="bonus-die-row">
          <div class="bonus-die-info">
            <span class="bonus-die-label">Bonus d6 rolled:</span>
            <span class="die die-bonus">{{ rollData.bonus_die }}</span>
          </div>
          <div
            class="bonus-remaining"
            :class="bonusRemaining === 0 ? 'remaining-zero' : 'remaining-active'"
          >
            {{ bonusRemaining }} point{{ bonusRemaining !== 1 ? 's' : '' }} to distribute
          </div>
        </div>

        <!-- Reroll -->
        <div class="reroll-row">
          <button class="dnd-button-ghost reroll-btn" @click="rollStats" :disabled="rolling">
            ↺ Roll Again
          </button>
          <span class="reroll-note">Rolling again resets all bonus allocations.</span>
        </div>
      </div>

      <div v-else-if="rollError" class="error-msg">
        {{ rollError }}
        <button class="dnd-button-ghost" style="font-size:0.75rem;margin-top:0.5rem" @click="rollStats">
          Try Again
        </button>
      </div>
    </div>

    <!-- STEP 6: Review & Confirm -->
    <div v-else-if="currentStep === 6" class="step-panel fade-in-up">
      <h3 class="step-title">Your Hero Awaits</h3>

      <!-- Choices summary -->
      <div class="review-grid">
        <div class="review-item">
          <span class="review-label">Name</span>
          <span class="review-value">{{ form.name }}</span>
        </div>
        <div class="review-item">
          <span class="review-label">Region</span>
          <span class="review-value">{{ form.region }}</span>
        </div>
        <div class="review-item">
          <span class="review-label">Race</span>
          <span class="review-value">{{ form.race }}</span>
        </div>
        <div class="review-item">
          <span class="review-label">Class</span>
          <span class="review-value">{{ form.classType }}</span>
        </div>
      </div>

      <!-- Rolled stats summary -->
      <div v-if="finalAbilities" class="stats-summary">
        <div class="dnd-section-heading" style="margin-bottom:0.6rem">Ability Scores</div>
        <div class="stats-row">
          <div v-for="ab in ABILITIES" :key="ab" class="stat-chip">
            <span class="stat-chip-label">{{ AB_LABELS[ab] }}</span>
            <span class="stat-chip-value">{{ finalAbilities[ab] }}</span>
            <span class="stat-chip-mod">{{ modSign(finalAbilities[ab]) }}</span>
          </div>
        </div>
      </div>

      <!-- AI-generated background -->
      <div class="background-section">
        <div class="dnd-section-heading">Origin Story</div>
        <div v-if="creatingChar" class="loading-bg">
          <div class="spinner"></div>
          <span class="loading-text">The fates are weaving your story...</span>
        </div>
        <div v-else-if="generatedBackground" class="background-content">
          <div v-if="!editingBg" class="background-text parchment-text">
            {{ generatedBackground }}
          </div>
          <textarea
            v-else
            v-model="generatedBackground"
            class="dnd-input bg-textarea"
            rows="6"
          ></textarea>
          <div class="bg-actions">
            <button class="dnd-button-ghost" style="font-size:0.72rem" @click="toggleEdit">
              {{ editingBg ? '✓ Done Editing' : '✏ Edit' }}
            </button>
            <button class="dnd-button-ghost" style="font-size:0.72rem" @click="regenerateBackground" :disabled="creatingChar">
              ↺ Regenerate
            </button>
          </div>
        </div>
        <div v-else-if="creationError" class="error-msg">
          {{ creationError }}
          <button class="dnd-button-ghost" style="font-size:0.72rem; margin-top:0.5rem" @click="submitCharacter">
            Retry
          </button>
        </div>
      </div>
    </div>

    <!-- Navigation buttons -->
    <div class="step-nav">
      <button
        v-if="currentStep > 1"
        class="dnd-button-ghost"
        @click="prevStep"
      >
        ← Previous
      </button>
      <div class="spacer"></div>
      <button
        v-if="currentStep < TOTAL_STEPS - 1"
        class="dnd-button"
        @click="nextStep"
        :disabled="!canProceed"
      >
        Next →
      </button>
      <button
        v-else-if="currentStep === TOTAL_STEPS - 1"
        class="dnd-button"
        @click="goToReview"
        :disabled="!canProceed"
      >
        Review →
      </button>
      <button
        v-else-if="currentStep === TOTAL_STEPS"
        class="dnd-button begin-btn"
        @click="beginAdventure"
        :disabled="!generatedBackground || creatingChar"
      >
        ⚔ Begin Adventure
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useCampaignStore } from '../stores/campaign'

const props = defineProps({
  campaignId: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['created'])
const campaignStore = useCampaignStore()

const TOTAL_STEPS = 6
const currentStep = ref(1)
const creatingChar = ref(false)
const creationError = ref(null)
const generatedBackground = ref('')
const editingBg = ref(false)

const form = ref({
  name: '',
  region: '',
  race: '',
  classType: '',
})

// Roll stats state
const rolling = ref(false)
const rollError = ref(null)
const rollData = ref(null)
const bonusAllocation = ref({ str: 0, dex: 0, con: 0, int: 0, wis: 0, chr: 0 })

const ABILITIES = ['str', 'dex', 'con', 'int', 'wis', 'chr']
const AB_LABELS = { str: 'STR', dex: 'DEX', con: 'CON', int: 'INT', wis: 'WIS', chr: 'CHA' }

const bonusRemaining = computed(() => {
  if (!rollData.value) return 0
  const used = Object.values(bonusAllocation.value).reduce((s, v) => s + v, 0)
  return rollData.value.bonus_die - used
})

const finalAbilities = computed(() => {
  if (!rollData.value) return null
  const result = {}
  for (const ab of ABILITIES) {
    result[ab] =
      rollData.value.rolls[ab].total +
      (rollData.value.racial_bonuses[ab] || 0) +
      bonusAllocation.value[ab]
  }
  return result
})

// Auto-roll when entering step 5 for the first time
watch(currentStep, (newStep) => {
  if (newStep === 5 && !rollData.value) {
    rollStats()
  }
})

const REGIONS = [
  'The Sword Coast', 'The North', 'Waterdeep', "Baldur's Gate",
  'Neverwinter', 'Icewind Dale', 'The High Forest', 'Amn',
  'Calimshan', 'The Underdark', 'The Dalelands', 'Sembia',
]

const RACES = [
  { name: 'Human',     emoji: '👤', bonus: '+1 to all abilities' },
  { name: 'Elf',       emoji: '🧝', bonus: '+2 DEX, +1 INT' },
  { name: 'Dwarf',     emoji: '⛏',  bonus: '+2 CON, +1 WIS' },
  { name: 'Halfling',  emoji: '🍀', bonus: '+2 DEX, +1 CHA' },
  { name: 'Half-Elf',  emoji: '🌙', bonus: '+2 CHA, +1 DEX/WIS' },
  { name: 'Half-Orc',  emoji: '💪', bonus: '+2 STR, +1 CON' },
  { name: 'Dragonborn',emoji: '🐉', bonus: '+2 STR, +1 CHA' },
  { name: 'Gnome',     emoji: '🔬', bonus: '+2 INT, +1 CON' },
  { name: 'Tiefling',  emoji: '😈', bonus: '+2 CHA, +1 INT' },
]

const CLASSES = [
  { name: 'Barbarian', emoji: '🪓', hitDie: 'd12', role: 'Melee Brute' },
  { name: 'Bard',      emoji: '🎵', hitDie: 'd8',  role: 'Support Caster' },
  { name: 'Cleric',    emoji: '✝',  hitDie: 'd8',  role: 'Divine Healer' },
  { name: 'Druid',     emoji: '🌿', hitDie: 'd8',  role: 'Nature Shaper' },
  { name: 'Fighter',   emoji: '⚔',  hitDie: 'd10', role: 'Combat Specialist' },
  { name: 'Monk',      emoji: '🥋', hitDie: 'd8',  role: 'Martial Artist' },
  { name: 'Paladin',   emoji: '🛡',  hitDie: 'd10', role: 'Holy Warrior' },
  { name: 'Ranger',    emoji: '🏹', hitDie: 'd10', role: 'Wilderness Hunter' },
  { name: 'Rogue',     emoji: '🗡',  hitDie: 'd8',  role: 'Stealthy Striker' },
  { name: 'Sorcerer',  emoji: '🔮', hitDie: 'd6',  role: 'Innate Magic' },
  { name: 'Warlock',   emoji: '📜', hitDie: 'd8',  role: 'Pact Magic' },
  { name: 'Wizard',    emoji: '🧙', hitDie: 'd6',  role: 'Arcane Scholar' },
]

const canProceed = computed(() => {
  switch (currentStep.value) {
    case 1: return form.value.name.trim().length >= 2
    case 2: return !!form.value.region
    case 3: return !!form.value.race
    case 4: return !!form.value.classType
    case 5: return rollData.value !== null
    default: return true
  }
})

function nextStep() {
  if (!canProceed.value) return
  if (currentStep.value < TOTAL_STEPS) {
    currentStep.value++
  }
}

function prevStep() {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

async function goToReview() {
  if (!canProceed.value) return
  currentStep.value = 6
  await submitCharacter()
}

async function rollStats() {
  rolling.value = true
  rollError.value = null
  bonusAllocation.value = { str: 0, dex: 0, con: 0, int: 0, wis: 0, chr: 0 }
  try {
    const res = await fetch(`/api/campaigns/${props.campaignId}/roll-stats`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ race: form.value.race }),
    })
    if (res.ok) {
      rollData.value = await res.json()
    } else {
      const err = await res.json().catch(() => ({}))
      rollError.value = err.detail || 'Failed to roll stats.'
    }
  } catch (e) {
    rollError.value = 'Network error. Please try again.'
  }
  rolling.value = false
}

function addBonus(ability) {
  if (bonusRemaining.value > 0) {
    bonusAllocation.value[ability]++
  }
}

function removeBonus(ability) {
  if (bonusAllocation.value[ability] > 0) {
    bonusAllocation.value[ability]--
  }
}

function modSign(score) {
  const mod = Math.floor((score - 10) / 2)
  return mod >= 0 ? `+${mod}` : `${mod}`
}

async function submitCharacter() {
  creatingChar.value = true
  creationError.value = null
  generatedBackground.value = ''

  const charData = {
    name: form.value.name,
    region: form.value.region,
    race: form.value.race,
    class_type: form.value.classType,
    abilities: finalAbilities.value,
  }

  const result = await campaignStore.createCharacter(props.campaignId, charData)

  if (result) {
    generatedBackground.value = result.background || result.origin_story || 'Your story begins now...'
  } else {
    creationError.value = campaignStore.error || 'Failed to create character. Please try again.'
  }

  creatingChar.value = false
}

async function regenerateBackground() {
  await submitCharacter()
}

function toggleEdit() {
  editingBg.value = !editingBg.value
}

function beginAdventure() {
  emit('created', {
    ...form.value,
    background: generatedBackground.value,
  })
}
</script>

<style scoped>
.char-creator {
  max-width: 720px;
  margin: 0 auto;
}

.step-dots {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.step-dot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 2px solid #3d2e10;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Cinzel', serif;
  font-size: 0.8rem;
  font-weight: 700;
  color: #8a7355;
  cursor: default;
  transition: all 0.2s ease;
  background: #1a1109;
}
.step-dot.active {
  border-color: #c9a227;
  color: #c9a227;
  box-shadow: 0 0 10px rgba(201,162,39,0.4);
}
.step-dot.done {
  border-color: #7a6115;
  color: #4ade80;
  cursor: pointer;
  background: rgba(74,222,128,0.08);
}

.step-panel {
  min-height: 300px;
  margin-bottom: 1.5rem;
}

.step-title {
  font-family: 'Cinzel', serif;
  font-size: 1.35rem;
  font-weight: 700;
  color: #c9a227;
  margin-bottom: 0.35rem;
}

.step-desc {
  color: #8a7355;
  font-style: italic;
  font-size: 1rem;
  margin-bottom: 1.25rem;
}

.form-field {
  max-width: 400px;
}

/* Region grid */
.region-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}
@media (max-width: 480px) {
  .region-grid { grid-template-columns: repeat(2, 1fr); }
}

.region-btn {
  padding: 0.5rem 0.75rem;
  font-family: 'Crimson Text', serif;
  font-size: 0.9rem;
  color: #e8d5b7;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: center;
}
.region-btn:hover {
  border-color: #7a6115;
  background: #221608;
  color: #c9a227;
}
.region-btn.selected {
  border-color: #c9a227;
  background: rgba(201,162,39,0.1);
  color: #c9a227;
  box-shadow: 0 0 8px rgba(201,162,39,0.2);
}

/* Race grid */
.race-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.6rem;
}
@media (max-width: 480px) {
  .race-grid { grid-template-columns: repeat(2, 1fr); }
}

.race-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 0.5rem;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.race-card:hover {
  border-color: #7a6115;
  background: #221608;
}
.race-card.selected {
  border-color: #c9a227;
  background: rgba(201,162,39,0.08);
  box-shadow: 0 0 10px rgba(201,162,39,0.25);
}
.race-emoji { font-size: 1.5rem; }
.race-name {
  font-family: 'Cinzel', serif;
  font-size: 0.8rem;
  font-weight: 600;
  color: #c9a227;
}
.race-bonus {
  font-size: 0.7rem;
  color: #8a7355;
  text-align: center;
}

/* Class grid */
.class-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
}
@media (max-width: 600px) {
  .class-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 400px) {
  .class-grid { grid-template-columns: repeat(2, 1fr); }
}

.class-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  padding: 0.65rem 0.4rem;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.class-card:hover {
  border-color: #7a6115;
  background: #221608;
}
.class-card.selected {
  border-color: #c9a227;
  background: rgba(201,162,39,0.08);
  box-shadow: 0 0 10px rgba(201,162,39,0.25);
}
.class-emoji { font-size: 1.3rem; }
.class-name {
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  font-weight: 600;
  color: #c9a227;
}
.class-hit-die {
  font-family: 'Cinzel', serif;
  font-size: 0.62rem;
  color: #8a7355;
}
.class-role {
  font-size: 0.62rem;
  color: #8a7355;
  text-align: center;
}

/* ===== ROLL STATS STEP ===== */
.abilities-table {
  border: 1px solid #3d2e10;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 1rem;
}

.abilities-header {
  display: grid;
  grid-template-columns: 3rem 1fr 3rem 3.5rem 6rem 3rem;
  gap: 0.5rem;
  align-items: center;
  padding: 0.4rem 0.75rem;
  background: #110c04;
  font-family: 'Cinzel', serif;
  font-size: 0.6rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #7a6115;
  border-bottom: 1px solid #3d2e10;
}
.header-dice { text-align: center; }
.header-base, .header-racial, .header-final { text-align: center; }
.header-bonus { text-align: center; }

.ability-row {
  display: grid;
  grid-template-columns: 3rem 1fr 3rem 3.5rem 6rem 3rem;
  gap: 0.5rem;
  align-items: center;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #2a1e08;
  transition: background 0.15s;
}
.ability-row:last-child { border-bottom: none; }
.ability-row:hover { background: rgba(201,162,39,0.04); }
.ability-row.row-boosted { background: rgba(201,162,39,0.07); }

.ab-label {
  font-family: 'Cinzel', serif;
  font-size: 0.78rem;
  font-weight: 700;
  color: #c9a227;
}

.dice-group {
  display: flex;
  gap: 0.3rem;
  justify-content: center;
  flex-wrap: wrap;
}

.die {
  width: 28px;
  height: 28px;
  border-radius: 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: 'Cinzel', serif;
  font-size: 0.85rem;
  font-weight: 700;
  flex-shrink: 0;
}

.die-kept {
  background: rgba(201,162,39,0.18);
  border: 1.5px solid #c9a227;
  color: #e8d5b7;
  box-shadow: 0 0 6px rgba(201,162,39,0.3);
}

.die-dropped {
  background: #1a1109;
  border: 1.5px solid #3d2e10;
  color: #4a3820;
  text-decoration: line-through;
  opacity: 0.55;
}

.die-bonus {
  background: linear-gradient(135deg, #1a1109, #221608);
  border: 2px solid #4ade80;
  color: #4ade80;
  font-size: 1rem;
  width: 34px;
  height: 34px;
  box-shadow: 0 0 8px rgba(74,222,128,0.35);
}

.ab-base {
  text-align: center;
  font-family: 'Cinzel', serif;
  font-size: 0.9rem;
  color: #e8d5b7;
}

.ab-racial {
  text-align: center;
  font-family: 'Cinzel', serif;
  font-size: 0.8rem;
}
.racial-positive { color: #4ade80; }
.racial-zero { color: #3d2e10; }

.bonus-alloc {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.2rem;
}

.alloc-btn {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid #3d2e10;
  background: #1a1109;
  color: #8a7355;
  font-size: 0.9rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.12s;
}
.alloc-btn:hover:not(:disabled) {
  border-color: #c9a227;
  color: #c9a227;
  background: rgba(201,162,39,0.1);
}
.alloc-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.alloc-val {
  width: 1.6rem;
  text-align: center;
  font-family: 'Cinzel', serif;
  font-size: 0.75rem;
  color: #5a4530;
}
.alloc-active { color: #4ade80; }

.ab-final {
  text-align: center;
  font-family: 'Cinzel', serif;
  font-size: 1rem;
  font-weight: 700;
  color: #c9a227;
}

.bonus-die-row {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.75rem 1rem;
  background: #0f0b04;
  border: 1px solid #2a1e08;
  border-radius: 6px;
  margin-bottom: 0.75rem;
}

.bonus-die-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.bonus-die-label {
  font-family: 'Cinzel', serif;
  font-size: 0.75rem;
  color: #8a7355;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.bonus-pip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: rgba(74,222,128,0.2);
  border: 1px solid #4ade80;
  color: #4ade80;
  font-family: 'Cinzel', serif;
  font-size: 0.7rem;
  font-weight: 700;
  margin-left: 0.25rem;
}

.bonus-remaining {
  font-family: 'Cinzel', serif;
  font-size: 0.8rem;
  font-weight: 600;
}
.remaining-active { color: #4ade80; }
.remaining-zero { color: #5a4530; }

.reroll-row {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.reroll-btn { font-size: 0.85rem; }

.reroll-note {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  font-size: 0.85rem;
  color: #5a4530;
}

/* Review */
.review-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}
.review-item {
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 4px;
  padding: 0.6rem 0.875rem;
}
.review-label {
  display: block;
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #8a7355;
  margin-bottom: 0.2rem;
}
.review-value {
  display: block;
  font-family: 'Crimson Text', serif;
  font-size: 1rem;
  color: #e8d5b7;
  font-weight: 600;
}

/* Stats chips row in review */
.stats-summary {
  margin-bottom: 1.25rem;
}
.stats-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.stat-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  min-width: 52px;
}
.stat-chip-label {
  font-family: 'Cinzel', serif;
  font-size: 0.58rem;
  letter-spacing: 0.08em;
  color: #7a6115;
  text-transform: uppercase;
}
.stat-chip-value {
  font-family: 'Cinzel', serif;
  font-size: 1.1rem;
  font-weight: 700;
  color: #c9a227;
  line-height: 1.1;
}
.stat-chip-mod {
  font-family: 'Cinzel', serif;
  font-size: 0.68rem;
  color: #8a7355;
}

.background-section { margin-bottom: 1.5rem; }

.loading-bg {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.5rem;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 6px;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #3d2e10;
  border-top-color: #c9a227;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

.loading-text {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #8a7355;
}

.background-content {
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 6px;
  padding: 1rem;
}
.background-text {
  font-size: 1rem;
  line-height: 1.7;
  margin-bottom: 0.75rem;
}
.bg-textarea {
  min-height: 120px;
  resize: vertical;
  margin-bottom: 0.75rem;
  width: 100%;
}
.bg-actions {
  display: flex;
  gap: 0.5rem;
}

.error-msg {
  display: flex;
  flex-direction: column;
  color: #f87171;
  font-family: 'Crimson Text', serif;
  padding: 1rem;
  background: rgba(139,26,26,0.15);
  border: 1px solid #7f1d1d;
  border-radius: 4px;
}

/* Navigation */
.step-nav {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding-top: 0.5rem;
  border-top: 1px solid #3d2e10;
}
.spacer { flex: 1; }

.begin-btn {
  padding: 0.6rem 2rem;
  font-size: 1rem;
}
</style>
