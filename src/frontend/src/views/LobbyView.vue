<template>
  <div class="lobby-page">
    <!-- Loading overlay -->
    <div v-if="loading" class="loading-overlay">
      <div class="spinner-lg"></div>
      <p class="loading-text">Preparing the realm...</p>
    </div>

    <!-- Character Creator mode -->
    <div v-else-if="needsCharacter" class="creator-wrapper">
      <div class="creator-header">
        <!-- Torchlight glow background -->
        <div class="torch-glow"></div>
        <div class="creator-title-block">
          <svg class="creator-d20" viewBox="0 0 50 50" fill="none" xmlns="http://www.w3.org/2000/svg">
            <polygon points="25,3 47,15 47,35 25,47 3,35 3,15"
              stroke="#c9a227" stroke-width="1.5" fill="none"/>
            <line x1="25" y1="3"  x2="25" y2="21" stroke="#c9a227" stroke-width="1" opacity="0.5"/>
            <line x1="47" y1="15" x2="25" y2="21" stroke="#c9a227" stroke-width="1" opacity="0.5"/>
            <line x1="47" y1="35" x2="25" y2="21" stroke="#c9a227" stroke-width="1" opacity="0.5"/>
            <line x1="25" y1="47" x2="25" y2="21" stroke="#c9a227" stroke-width="1" opacity="0.5"/>
            <line x1="3"  y1="35" x2="25" y2="21" stroke="#c9a227" stroke-width="1" opacity="0.5"/>
            <line x1="3"  y1="15" x2="25" y2="21" stroke="#c9a227" stroke-width="1" opacity="0.5"/>
            <text x="25" y="25" text-anchor="middle" dominant-baseline="middle"
                  fill="#c9a227" font-size="11" font-family="Cinzel, serif" font-weight="700">20</text>
          </svg>
          <div>
            <h1 class="creator-heading">Create Your Hero</h1>
            <p class="creator-sub">
              Campaign: <strong class="camp-name-inline">{{ campaignName }}</strong>
            </p>
          </div>
        </div>
      </div>

      <div class="creator-card dnd-panel">
        <CharacterCreator
          :campaignId="campaignId"
          @created="onCharacterCreated"
        />
      </div>
    </div>

    <!-- Returning Hero mode -->
    <div v-else class="returning-wrapper">
      <div class="returning-header">
        <h1 class="page-title">Welcome Back, Adventurer</h1>
        <p class="page-sub">Campaign: <strong>{{ campaignName }}</strong></p>
        <div class="gold-divider"></div>
      </div>

      <div class="returning-content">
        <!-- Character card -->
        <div class="hero-card dnd-panel dnd-panel-gold" v-if="existingPlayer">
          <div class="hero-card-header">
            <div class="hero-avatar">
              {{ heroInitial }}
            </div>
            <div class="hero-info">
              <h2 class="hero-char-name">{{ existingPlayer.character_name }}</h2>
              <p class="hero-details">
                {{ existingPlayer.race }} {{ existingPlayer.class_type }} &bull;
                <span class="hero-status" :class="statusClass">{{ existingPlayer.health_status || 'Healthy' }}</span>
              </p>
            </div>
          </div>

          <div class="gold-divider-plain"></div>

          <!-- HP Bar -->
          <div class="stat-row">
            <span class="stat-lbl">HP</span>
            <div class="bar-wrapper">
              <div class="hp-bar-container">
                <div class="hp-bar-fill"
                  :style="{ '--hp-pct': hpPct + '%' }"></div>
              </div>
            </div>
            <span class="stat-nums">{{ existingPlayer.hp_current ?? '?' }} / {{ existingPlayer.hp_max ?? '?' }}</span>
          </div>

          <!-- DM Summary -->
          <div v-if="joinResult?.summary" class="dm-summary">
            <div class="dnd-section-heading">DM's Note</div>
            <p class="parchment-text">{{ joinResult.summary }}</p>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="lobby-actions">
          <button class="dnd-button enter-btn" @click="enterGame">
            ⚔ Enter the Game
          </button>
          <RouterLink to="/campaigns" class="dnd-button-ghost">
            ← Back to Campaigns
          </RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useCampaignStore } from '../stores/campaign'
import { useAuthStore } from '../stores/auth'
import CharacterCreator from '../components/CharacterCreator.vue'

const route = useRoute()
const router = useRouter()
const campaignStore = useCampaignStore()
const authStore = useAuthStore()

const campaignId = route.params.id
const loading = ref(true)
const needsCharacter = ref(false)

const joinResult = computed(() => campaignStore.joinResult)
const campaignName = computed(() => campaignStore.currentMeta?.name || `Campaign ${campaignId}`)
const existingPlayer = computed(() => {
  if (!joinResult.value) return null
  return joinResult.value.player || null
})

const heroInitial = computed(() => {
  return existingPlayer.value?.character_name?.charAt(0)?.toUpperCase() || '?'
})

const hpPct = computed(() => {
  const p = existingPlayer.value
  if (!p || !p.hp_max) return 100
  return Math.max(0, Math.min(100, (p.hp_current / p.hp_max) * 100))
})

const statusClass = computed(() => {
  const s = (existingPlayer.value?.health_status || '').toLowerCase()
  if (s === 'healthy')     return 'text-green-400'
  if (s === 'bloodied')    return 'text-yellow-400'
  if (s === 'critical')    return 'text-red-400'
  if (s === 'unconscious') return 'text-gray-400'
  return 'text-parchment'
})

onMounted(async () => {
  // Join campaign if not already in joinResult
  if (!campaignStore.joinResult) {
    const result = await campaignStore.joinCampaign(campaignId)
    if (!result) {
      // Failed - redirect back
      router.push('/campaigns')
      return
    }
  }

  needsCharacter.value = campaignStore.joinResult?.needs_character === true
  loading.value = false
})

function onCharacterCreated(charData) {
  // Character created - navigate to game
  router.push(`/campaigns/${campaignId}/game`)
}

function enterGame() {
  router.push(`/campaigns/${campaignId}/game`)
}
</script>

<style scoped>
.lobby-page {
  min-height: calc(100vh - 64px);
  background: radial-gradient(ellipse at center, #130e04 0%, #0d0a06 70%);
}

/* Loading overlay */
.loading-overlay {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: calc(100vh - 64px);
  gap: 1.5rem;
}

.spinner-lg {
  width: 48px;
  height: 48px;
  border: 3px solid #3d2e10;
  border-top-color: #c9a227;
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

.loading-text {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #8a7355;
  font-size: 1.1rem;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Creator mode */
.creator-wrapper {
  max-width: 750px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.creator-header {
  position: relative;
  text-align: center;
  margin-bottom: 2rem;
  padding: 1.5rem;
  overflow: hidden;
}

.torch-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, rgba(201,162,39,0.08) 0%, transparent 70%);
  pointer-events: none;
}

.creator-title-block {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  position: relative;
  z-index: 1;
}

.creator-d20 {
  width: 50px;
  height: 50px;
  filter: drop-shadow(0 0 10px rgba(201,162,39,0.5));
  flex-shrink: 0;
}

.creator-heading {
  font-family: 'Cinzel', serif;
  font-size: 1.8rem;
  font-weight: 700;
  color: #c9a227;
  margin: 0 0 0.25rem;
  text-align: left;
}

.creator-sub {
  font-family: 'Crimson Text', serif;
  color: #8a7355;
  font-style: italic;
  font-size: 0.95rem;
  margin: 0;
  text-align: left;
}

.camp-name-inline {
  color: #e8d5b7;
  font-style: normal;
}

.creator-card {
  padding: 2rem;
}

/* Returning hero mode */
.returning-wrapper {
  max-width: 640px;
  margin: 0 auto;
  padding: 2.5rem 1.5rem;
}

.returning-header {
  text-align: center;
  margin-bottom: 2rem;
}

.page-title {
  font-family: 'Cinzel', serif;
  font-size: 2rem;
  font-weight: 700;
  color: #c9a227;
  margin-bottom: 0.35rem;
}

.page-sub {
  font-family: 'Crimson Text', serif;
  color: #8a7355;
  font-style: italic;
  margin-bottom: 1rem;
}

.page-sub strong {
  color: #e8d5b7;
  font-style: normal;
}

.returning-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* Hero card */
.hero-card {
  padding: 1.5rem;
}

.hero-card-header {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  margin-bottom: 0.75rem;
}

.hero-avatar {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #7a6115, #c9a227);
  color: #1a0e00;
  font-family: 'Cinzel', serif;
  font-weight: 700;
  font-size: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 16px rgba(201,162,39,0.4);
  flex-shrink: 0;
}

.hero-char-name {
  font-family: 'Cinzel', serif;
  font-size: 1.4rem;
  font-weight: 700;
  color: #c9a227;
  margin: 0 0 0.25rem;
}

.hero-details {
  font-family: 'Crimson Text', serif;
  color: #8a7355;
  font-size: 1rem;
  margin: 0;
}

.hero-status { font-weight: 600; }

.stat-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.stat-lbl {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: #8a7355;
  text-transform: uppercase;
  width: 28px;
  flex-shrink: 0;
}

.bar-wrapper {
  flex: 1;
}

.stat-nums {
  font-family: 'Cinzel', serif;
  font-size: 0.78rem;
  color: #e8d5b7;
  white-space: nowrap;
  flex-shrink: 0;
}

.dm-summary {
  margin-top: 1rem;
}

/* Action buttons */
.lobby-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

.enter-btn {
  font-size: 1rem;
  padding: 0.65rem 2.5rem;
  text-decoration: none;
}

.text-green-400  { color: #4ade80; }
.text-yellow-400 { color: #facc15; }
.text-red-400    { color: #f87171; }
.text-gray-400   { color: #9ca3af; }
.text-parchment  { color: #e8d5b7; }
</style>
