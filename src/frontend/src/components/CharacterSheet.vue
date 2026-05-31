<template>
  <!-- Slide-out overlay -->
  <Teleport to="body">
    <Transition name="sheet-slide">
      <div v-if="open" class="sheet-overlay" @click.self="$emit('close')">
        <aside class="sheet-panel">
          <!-- Header -->
          <div class="sheet-header">
            <div class="sheet-title-block">
              <span class="sheet-name">{{ char?.name || 'Character Sheet' }}</span>
              <span v-if="char" class="sheet-subtitle">
                {{ char.race }} &middot;
                <span v-for="(cls, i) in char.classes" :key="i">
                  {{ cls.type }} {{ cls.level }}<span v-if="i < char.classes.length - 1"> / </span>
                </span>
              </span>
            </div>
            <button class="sheet-close-btn" @click="$emit('close')" title="Close">&#x2715;</button>
          </div>

          <div v-if="loading" class="sheet-loading">Loading...</div>
          <div v-else-if="!char" class="sheet-empty">No character data.</div>

          <div v-else class="sheet-body">

            <!-- HP + XP row -->
            <section class="sheet-section">
              <div class="sheet-row-stats">
                <div class="stat-pill">
                  <span class="spl">HP</span>
                  <span class="spv" :class="hpColor">{{ char.hp.current }} / {{ char.hp.max }}</span>
                </div>
                <div class="stat-pill">
                  <span class="spl">XP</span>
                  <span class="spv">{{ char.experience || 0 }}</span>
                </div>
                <div class="stat-pill">
                  <span class="spl">Level</span>
                  <span class="spv">{{ totalLevel }}</span>
                </div>
              </div>
            </section>

            <div class="gold-divider-plain"></div>

            <!-- Ability Scores -->
            <section class="sheet-section">
              <div class="sheet-section-title">Ability Scores</div>
              <div class="ability-grid">
                <div
                  v-for="(ab, key) in char.abilities"
                  :key="key"
                  class="ability-cell"
                >
                  <span class="ab-name">{{ ABILITY_LABELS[key] || key.toUpperCase() }}</span>
                  <span class="ab-score">{{ ab.score }}</span>
                  <span class="ab-mod" :class="ab.modifier >= 0 ? 'mod-pos' : 'mod-neg'">
                    {{ ab.modifier >= 0 ? '+' : '' }}{{ ab.modifier }}
                  </span>
                </div>
              </div>
            </section>

            <div class="gold-divider-plain"></div>

            <!-- Background / Region -->
            <section v-if="char.background || char.region" class="sheet-section">
              <div class="sheet-section-title">Background</div>
              <div v-if="char.region" class="sheet-field">
                <span class="field-label">Region:</span>
                <span class="field-value">{{ char.region }}</span>
              </div>
              <p v-if="char.background" class="background-text parchment-text">
                {{ char.background }}
              </p>
            </section>

            <div v-if="char.background || char.region" class="gold-divider-plain"></div>

            <!-- Proficiencies -->
            <section v-if="char.proficiencies?.length" class="sheet-section">
              <div class="sheet-section-title">Proficiencies</div>
              <ul class="tag-list">
                <li v-for="(prof, i) in char.proficiencies" :key="i" class="tag-item">
                  {{ prof }}
                </li>
              </ul>
            </section>

            <div v-if="char.proficiencies?.length" class="gold-divider-plain"></div>

            <!-- Class Features -->
            <section v-if="char.features?.length" class="sheet-section">
              <div class="sheet-section-title">Class Features</div>
              <ul class="feature-list">
                <li v-for="(feat, i) in char.features" :key="i" class="feature-item">
                  <span class="feat-name">{{ feat.name || feat }}</span>
                  <span v-if="feat.description" class="feat-desc">{{ feat.description }}</span>
                </li>
              </ul>
            </section>

            <div v-if="char.features?.length" class="gold-divider-plain"></div>

            <!-- Conditions -->
            <section v-if="char.conditions?.length" class="sheet-section">
              <div class="sheet-section-title">Conditions</div>
              <ul class="tag-list">
                <li
                  v-for="(cond, i) in char.conditions"
                  :key="i"
                  class="tag-item tag-condition"
                >
                  {{ cond }}
                </li>
              </ul>
            </section>

            <div v-if="char.conditions?.length" class="gold-divider-plain"></div>

            <!-- Equipped Items -->
            <section class="sheet-section">
              <div class="sheet-section-title">Equipment</div>
              <div v-if="!char.items?.length" class="empty-note">No items carried.</div>
              <ul v-else class="item-list">
                <li
                  v-for="item in char.items"
                  :key="item.id"
                  class="item-row"
                >
                  <span class="item-name">{{ item.name }}</span>
                  <span v-if="item.equipped" class="item-badge equipped-badge">Equipped</span>
                  <span class="item-weight">{{ item.weight > 0 ? item.weight + ' lb' : '' }}</span>
                </li>
              </ul>
              <div v-if="char.items?.length" class="enc-summary">
                Total: {{ totalWeight }} lb
              </div>
            </section>

            <!-- Goals -->
            <div v-if="char.goals?.length" class="gold-divider-plain"></div>
            <section v-if="char.goals?.length" class="sheet-section">
              <div class="sheet-section-title">Goals</div>
              <ul class="goal-list">
                <li v-for="(g, i) in char.goals" :key="i" class="goal-item">{{ g }}</li>
              </ul>
            </section>

          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const ABILITY_LABELS = {
  str: 'STR', dex: 'DEX', con: 'CON',
  int: 'INT', wis: 'WIS', chr: 'CHA',
}

const props = defineProps({
  open: { type: Boolean, default: false },
  campaignId: { type: String, required: true },
  characterId: { type: Number, default: null },
})

defineEmits(['close'])

const char = ref(null)
const loading = ref(false)

async function fetchCharacter() {
  if (!props.characterId || !props.campaignId) return
  loading.value = true
  try {
    const res = await fetch(
      `/api/campaigns/${props.campaignId}/characters/${props.characterId}`,
      { credentials: 'include' }
    )
    if (res.ok) {
      char.value = await res.json()
    } else {
      char.value = null
    }
  } catch {
    char.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.open, (val) => {
  if (val) fetchCharacter()
})

watch(() => props.characterId, () => {
  if (props.open) fetchCharacter()
})

const totalLevel = computed(() => {
  if (!char.value?.classes?.length) return 1
  return char.value.classes.reduce((sum, c) => sum + (c.level || 1), 0)
})

const hpColor = computed(() => {
  if (!char.value) return ''
  const pct = char.value.hp.max > 0
    ? (char.value.hp.current / char.value.hp.max) * 100
    : 100
  if (pct > 60) return 'hp-green'
  if (pct > 30) return 'hp-yellow'
  return 'hp-red'
})

const totalWeight = computed(() => {
  if (!char.value?.items) return 0
  return char.value.items.reduce((s, i) => s + (i.weight || 0), 0).toFixed(1)
})
</script>

<style scoped>
/* Slide-out transition */
.sheet-slide-enter-active,
.sheet-slide-leave-active {
  transition: transform 0.25s ease, opacity 0.2s ease;
}
.sheet-slide-enter-from,
.sheet-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 300;
  display: flex;
  justify-content: flex-end;
}

.sheet-panel {
  width: 360px;
  max-width: 95vw;
  height: 100%;
  background: #110d05;
  border-left: 2px solid #c9a227;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.sheet-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 1rem 1rem 0.75rem;
  border-bottom: 1px solid #3d2e10;
  flex-shrink: 0;
  background: rgba(201, 162, 39, 0.06);
}

.sheet-title-block {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.sheet-name {
  font-family: 'Cinzel', serif;
  font-size: 1.1rem;
  font-weight: 700;
  color: #c9a227;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sheet-subtitle {
  font-family: 'Crimson Text', serif;
  font-size: 0.88rem;
  color: #8a7355;
  font-style: italic;
}

.sheet-close-btn {
  background: transparent;
  border: 1px solid #3d2e10;
  color: #8a7355;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.2rem 0.45rem;
  border-radius: 3px;
  flex-shrink: 0;
  transition: color 0.15s, border-color 0.15s;
}
.sheet-close-btn:hover {
  color: #c9a227;
  border-color: #c9a227;
}

.sheet-loading,
.sheet-empty {
  padding: 2rem;
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #5a4530;
  text-align: center;
}

.sheet-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Sections */
.sheet-section {
  padding: 0.75rem 1rem;
}

.sheet-section-title {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #8a7355;
  margin-bottom: 0.5rem;
}

/* HP/XP row */
.sheet-row-stats {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.stat-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 5px;
  padding: 0.35rem 0.75rem;
  min-width: 60px;
}

.spl {
  font-family: 'Cinzel', serif;
  font-size: 0.58rem;
  letter-spacing: 0.1em;
  color: #8a7355;
  text-transform: uppercase;
  margin-bottom: 0.15rem;
}

.spv {
  font-family: 'Cinzel', serif;
  font-size: 0.9rem;
  font-weight: 700;
  color: #e8d5b7;
}
.hp-green  { color: #4ade80; }
.hp-yellow { color: #facc15; }
.hp-red    { color: #f87171; }

/* Ability grid */
.ability-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.4rem;
}

.ability-cell {
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 5px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.4rem 0.25rem;
}

.ab-name {
  font-family: 'Cinzel', serif;
  font-size: 0.55rem;
  letter-spacing: 0.1em;
  color: #8a7355;
  text-transform: uppercase;
}

.ab-score {
  font-family: 'Cinzel', serif;
  font-size: 1.1rem;
  font-weight: 700;
  color: #e8d5b7;
  line-height: 1.2;
}

.ab-mod {
  font-family: 'Cinzel', serif;
  font-size: 0.78rem;
  font-weight: 600;
}
.mod-pos { color: #86efac; }
.mod-neg { color: #f87171; }

/* Background text */
.sheet-field {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.35rem;
  font-family: 'Crimson Text', serif;
  font-size: 0.88rem;
}
.field-label { color: #8a7355; }
.field-value { color: #e8d5b7; }

.background-text {
  font-size: 0.88rem;
  line-height: 1.55;
  margin: 0;
  color: #c8b48a;
}

/* Tags (proficiencies, conditions) */
.tag-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.tag-item {
  font-family: 'Crimson Text', serif;
  font-size: 0.8rem;
  padding: 0.1rem 0.5rem;
  border: 1px solid #3d2e10;
  border-radius: 3px;
  background: rgba(61, 46, 16, 0.2);
  color: #c8b48a;
}

.tag-condition {
  border-color: #7f1d1d;
  background: rgba(139, 26, 26, 0.2);
  color: #fca5a5;
}

/* Features */
.feature-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.feature-item {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.feat-name {
  font-family: 'Cinzel', serif;
  font-size: 0.78rem;
  font-weight: 600;
  color: #c9a227;
}

.feat-desc {
  font-family: 'Crimson Text', serif;
  font-size: 0.82rem;
  color: #8a7355;
  font-style: italic;
}

/* Items */
.item-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.4rem;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 3px;
}

.item-name {
  font-family: 'Crimson Text', serif;
  font-size: 0.88rem;
  color: #e8d5b7;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-badge {
  font-family: 'Cinzel', serif;
  font-size: 0.55rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  flex-shrink: 0;
}

.equipped-badge {
  background: rgba(201, 162, 39, 0.12);
  color: #c9a227;
  border: 1px solid #7a6115;
}

.item-weight {
  font-family: 'Crimson Text', serif;
  font-size: 0.78rem;
  color: #8a7355;
  flex-shrink: 0;
}

.enc-summary {
  margin-top: 0.4rem;
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  color: #8a7355;
  text-align: right;
}

.empty-note {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #5a4530;
  font-size: 0.85rem;
}

/* Goals */
.goal-list {
  list-style: disc;
  margin: 0;
  padding-left: 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.goal-item {
  font-family: 'Crimson Text', serif;
  font-size: 0.88rem;
  color: #c8b48a;
}

/* Divider reuse */
.gold-divider-plain {
  height: 1px;
  background: #3d2e10;
  margin: 0;
}
</style>
