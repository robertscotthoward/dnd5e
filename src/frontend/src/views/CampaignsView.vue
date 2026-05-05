<template>
  <div class="campaigns-page">
    <div class="campaigns-inner">
      <!-- Header -->
      <div class="page-header">
        <h1 class="page-title">Choose Your Adventure</h1>
        <p class="page-sub">Create a new campaign or join an existing one.</p>
        <div class="gold-divider"></div>
      </div>

      <!-- Create Campaign Section -->
      <div class="create-section dnd-panel dnd-panel-gold">
        <h3 class="section-sub-title">⚔ Forge a New Campaign</h3>
        <div class="create-form">
          <div class="create-inputs">
            <div class="form-group">
              <label class="dnd-label" for="camp-name">Campaign Name</label>
              <input
                id="camp-name"
                v-model="newName"
                class="dnd-input"
                placeholder="The Shadows of Baldur's Gate..."
                maxlength="80"
                @keydown.enter="handleCreate"
              />
            </div>
            <div class="form-group">
              <label class="dnd-label" for="camp-seed">World Seed (optional)</label>
              <input
                id="camp-seed"
                v-model="newSeed"
                class="dnd-input"
                placeholder="A seed for the AI world generator..."
                maxlength="200"
              />
            </div>
          </div>
          <button
            class="dnd-button create-btn"
            @click="handleCreate"
            :disabled="!newName.trim() || campaignStore.loading"
          >
            <span v-if="campaignStore.loading" class="spinner-sm"></span>
            <span v-else>✦ Create Campaign</span>
          </button>
        </div>
      </div>

      <div class="gold-divider"></div>

      <!-- Campaigns List -->
      <div class="list-section">
        <h3 class="section-sub-title">🗺 Existing Campaigns</h3>

        <!-- Loading -->
        <div v-if="campaignStore.loading && campaigns.length === 0" class="loading-state">
          <div class="spinner"></div>
          <span>Consulting the tomes...</span>
        </div>

        <!-- Empty state -->
        <div v-else-if="campaigns.length === 0" class="empty-state">
          <div class="empty-scroll">📜</div>
          <p class="empty-text">No campaigns found. Create the first one!</p>
          <p class="empty-sub">Be the first to forge a legend in this realm.</p>
        </div>

        <!-- Campaign grid -->
        <div v-else class="campaigns-grid">
          <div
            v-for="campaign in campaigns"
            :key="campaign.campaign_id || campaign.id"
            class="campaign-card dnd-panel"
          >
            <!-- Campaign header -->
            <div class="camp-header">
              <h4 class="camp-name">{{ campaign.name }}</h4>
              <div class="camp-badges">
                <span class="dnd-badge" :class="modeBadge(campaign.game_mode)">
                  {{ campaign.game_mode || 'Exploration' }}
                </span>
              </div>
            </div>

            <!-- Campaign meta -->
            <div class="camp-meta">
              <div class="meta-item">
                <span class="meta-icon">📖</span>
                <span class="meta-text">Turn {{ campaign.turn_number || 1 }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-icon">👥</span>
                <span class="meta-text">{{ campaign.player_count || 0 }} players</span>
              </div>
            </div>

            <p class="camp-creator">
              Created by <strong>{{ campaign.created_by || campaign.owner || 'unknown' }}</strong>
            </p>

            <!-- Join button -->
            <button
              class="dnd-button join-btn"
              @click="handleJoin(campaign.campaign_id || campaign.id)"
              :disabled="joiningId === (campaign.campaign_id || campaign.id)"
            >
              <span v-if="joiningId === (campaign.campaign_id || campaign.id)" class="spinner-sm"></span>
              <span v-else>⚔ Join Campaign</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Error message -->
      <div v-if="campaignStore.error" class="error-banner">
        {{ campaignStore.error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useCampaignStore } from '../stores/campaign'
import { useAuthStore } from '../stores/auth'

const campaignStore = useCampaignStore()
const authStore = useAuthStore()
const router = useRouter()

const newName = ref('')
const newSeed = ref('')
const joiningId = ref(null)

const campaigns = computed(() => campaignStore.campaigns)

onMounted(() => {
  campaignStore.fetchCampaigns()
})

async function handleCreate() {
  if (!newName.value.trim()) return
  const result = await campaignStore.createCampaign(newName.value.trim(), newSeed.value.trim() || null)
  if (result) {
    const id = result.campaign_id || result.id
    newName.value = ''
    newSeed.value = ''
    router.push(`/campaigns/${id}/lobby`)
  }
}

async function handleJoin(id) {
  joiningId.value = id
  const result = await campaignStore.joinCampaign(id)
  joiningId.value = null
  if (result) {
    if (result.needs_character) {
      router.push(`/campaigns/${id}/lobby`)
    } else {
      router.push(`/campaigns/${id}/game`)
    }
  }
}

function modeBadge(mode) {
  const m = (mode || '').toLowerCase()
  if (m === 'combat')      return 'dnd-badge-red'
  if (m === 'social')      return 'dnd-badge-blue'
  if (m === 'travel')      return 'dnd-badge-gold'
  return 'dnd-badge-green'
}
</script>

<style scoped>
.campaigns-page {
  min-height: calc(100vh - 64px);
  padding: 2.5rem 1.5rem;
  background: radial-gradient(ellipse at top center, #130e04 0%, #0d0a06 60%);
}

.campaigns-inner {
  max-width: 1000px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 2rem;
  text-align: center;
}

.page-title {
  font-family: 'Cinzel', serif;
  font-size: 2.2rem;
  font-weight: 700;
  color: #c9a227;
  margin-bottom: 0.35rem;
  text-shadow: 0 0 20px rgba(201,162,39,0.3);
}

.page-sub {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #8a7355;
  font-size: 1rem;
  margin-bottom: 1rem;
}

/* Create Section */
.create-section {
  margin-bottom: 1.5rem;
}

.section-sub-title {
  font-family: 'Cinzel', serif;
  font-size: 1.1rem;
  font-weight: 600;
  color: #c9a227;
  margin-bottom: 1rem;
}

.create-form {
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  flex-wrap: wrap;
}

.create-inputs {
  flex: 1;
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.form-group {
  flex: 1;
  min-width: 200px;
}

.create-btn {
  flex-shrink: 0;
  padding: 0.55rem 1.5rem;
  height: fit-content;
  align-self: flex-end;
}

/* Campaigns grid */
.list-section { margin-top: 1rem; }

.loading-state {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 2rem;
  color: #8a7355;
  font-family: 'Crimson Text', serif;
  font-style: italic;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  opacity: 0.7;
}

.empty-scroll { font-size: 3rem; margin-bottom: 1rem; }
.empty-text {
  font-family: 'Cinzel', serif;
  color: #8a7355;
  font-size: 1rem;
  margin-bottom: 0.35rem;
}
.empty-sub {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #5a4530;
  font-size: 0.9rem;
}

.campaigns-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.25rem;
  margin-top: 1rem;
}

.campaign-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.campaign-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 20px rgba(201,162,39,0.25);
}

.camp-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}

.camp-name {
  font-family: 'Cinzel', serif;
  font-size: 1.05rem;
  font-weight: 600;
  color: #c9a227;
  margin: 0;
  line-height: 1.2;
  flex: 1;
}

.camp-badges {
  flex-shrink: 0;
}

.camp-meta {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.meta-icon { font-size: 0.85rem; }
.meta-text {
  font-family: 'Crimson Text', serif;
  font-size: 0.85rem;
  color: #8a7355;
}

.camp-creator {
  font-family: 'Crimson Text', serif;
  font-size: 0.82rem;
  color: #8a7355;
  font-style: italic;
  margin: 0;
  flex: 1;
}
.camp-creator strong { color: #c4aa82; font-style: normal; }

.join-btn {
  width: 100%;
  justify-content: center;
  padding: 0.5rem;
  margin-top: auto;
}

.error-banner {
  background: rgba(139,26,26,0.2);
  border: 1px solid #7f1d1d;
  border-radius: 4px;
  padding: 0.75rem 1rem;
  color: #f87171;
  font-family: 'Crimson Text', serif;
  margin-top: 1rem;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #3d2e10;
  border-top-color: #c9a227;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(26,14,0,0.3);
  border-top-color: #1a0e00;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
