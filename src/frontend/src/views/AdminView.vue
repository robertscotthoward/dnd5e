<template>
  <div class="admin-page">
    <div class="admin-container">
      <!-- Header -->
      <div class="admin-header">
        <div class="admin-header-left">
          <h1 class="admin-title">⚙ Admin Console</h1>
          <p class="admin-subtitle">Campaign and player management</p>
        </div>
        <button class="dnd-button-ghost" @click="loadData" :disabled="loading">
          {{ loading ? 'Loading…' : '↺ Refresh' }}
        </button>
      </div>

      <div class="gold-divider" style="margin-bottom:2rem"></div>

      <!-- Error banner -->
      <div v-if="error" class="error-banner">{{ error }}</div>

      <!-- Loading state -->
      <div v-if="loading && !campaigns.length" class="loading-state">
        <div class="spinner"></div>
        <span>Loading campaigns…</span>
      </div>

      <!-- Empty state -->
      <div v-else-if="!loading && !campaigns.length" class="empty-state">
        No campaigns found.
      </div>

      <!-- Campaign list -->
      <div v-else class="campaigns-list">
        <div
          v-for="entry in campaigns"
          :key="entry.meta.id"
          class="campaign-card dnd-panel"
        >
          <!-- Campaign header row -->
          <div class="campaign-header">
            <div class="campaign-info">
              <h2 class="campaign-name">{{ entry.meta.name }}</h2>
              <div class="campaign-meta-row">
                <span class="meta-chip">ID: {{ entry.meta.id }}</span>
                <span class="meta-chip">Turn {{ entry.meta.turn_number }}</span>
                <span class="meta-chip">{{ entry.meta.game_mode }}</span>
                <span class="meta-chip">Created by {{ entry.meta.created_by }}</span>
                <span class="meta-chip">{{ formatDate(entry.meta.created_at) }}</span>
                <span class="meta-chip players-chip">
                  {{ entry.players.length }} player{{ entry.players.length !== 1 ? 's' : '' }}
                </span>
              </div>
            </div>
            <button
              class="delete-btn"
              title="Delete campaign"
              @click="confirmDeleteCampaign(entry.meta)"
            >✕</button>
          </div>

          <!-- Players sub-list -->
          <div class="players-section">
            <div v-if="!entry.players.length" class="no-players">No players yet.</div>
            <div
              v-for="player in entry.players"
              :key="player.user_id"
              class="player-row"
            >
              <div class="player-avatar">{{ player.username.charAt(0).toUpperCase() }}</div>
              <div class="player-info">
                <span class="player-username">{{ player.username }}</span>
                <span v-if="player.character_name" class="player-char">
                  — {{ player.character_name }}
                  <span class="player-race-class">{{ player.race }} {{ player.class_type }}</span>
                </span>
                <span v-else class="player-no-char">no character</span>
              </div>
              <div v-if="player.character_name" class="player-hp">
                <span
                  class="hp-badge"
                  :class="hpClass(player)"
                >{{ player.hp_current }}/{{ player.hp_max }} HP</span>
              </div>
              <button
                class="delete-btn delete-btn-sm"
                title="Remove player"
                @click="confirmRemovePlayer(entry.meta.id, player)"
              >✕</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirm dialog -->
    <div v-if="dialog.visible" class="modal-overlay" @click.self="closeDialog">
      <div class="modal dnd-panel">
        <h3 class="modal-title">{{ dialog.title }}</h3>
        <p class="modal-body">{{ dialog.message }}</p>
        <div class="modal-note" v-if="dialog.note">{{ dialog.note }}</div>
        <div class="modal-actions">
          <button class="dnd-button-ghost" @click="closeDialog">Cancel</button>
          <button class="dnd-button dnd-button-danger" @click="confirmAction" :disabled="acting">
            {{ acting ? 'Working…' : dialog.confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const campaigns = ref([])
const loading = ref(false)
const acting = ref(false)
const error = ref(null)

const dialog = ref({
  visible: false,
  title: '',
  message: '',
  note: '',
  confirmLabel: 'Confirm',
  action: null,
})

onMounted(async () => {
  if (!authStore.isAdmin) {
    router.push('/')
    return
  }
  await loadData()
})

async function loadData() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch('/api/admin/campaigns', { credentials: 'include' })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      throw new Error(d.detail || 'Failed to load campaigns')
    }
    campaigns.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function confirmDeleteCampaign(meta) {
  dialog.value = {
    visible: true,
    title: 'Delete Campaign',
    message: `Delete "${meta.name}"? This cannot be undone.`,
    note: 'The campaign folder will be archived as a zip file before deletion.',
    confirmLabel: 'Delete Campaign',
    action: () => deleteCampaign(meta.id),
  }
}

function confirmRemovePlayer(campaignId, player) {
  const charDesc = player.character_name
    ? ` (${player.character_name})`
    : ''
  dialog.value = {
    visible: true,
    title: 'Remove Player',
    message: `Remove ${player.username}${charDesc} from this campaign?`,
    note: player.character_name
      ? 'Their character will also be removed from the world.'
      : '',
    confirmLabel: 'Remove Player',
    action: () => removePlayer(campaignId, player.user_id),
  }
}

function closeDialog() {
  dialog.value.visible = false
}

async function confirmAction() {
  if (!dialog.value.action) return
  acting.value = true
  await dialog.value.action()
  acting.value = false
  closeDialog()
}

async function deleteCampaign(campaignId) {
  try {
    const res = await fetch(`/api/admin/campaigns/${campaignId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      throw new Error(d.detail || 'Delete failed')
    }
    campaigns.value = campaigns.value.filter(e => e.meta.id !== campaignId)
  } catch (e) {
    error.value = e.message
  }
}

async function removePlayer(campaignId, userId) {
  try {
    const res = await fetch(`/api/admin/campaigns/${campaignId}/players/${userId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      throw new Error(d.detail || 'Remove failed')
    }
    // Remove player from local state without a full reload
    const entry = campaigns.value.find(e => e.meta.id === campaignId)
    if (entry) {
      entry.players = entry.players.filter(p => p.user_id !== userId)
      entry.meta.player_count = entry.players.length
    }
  } catch (e) {
    error.value = e.message
  }
}

function hpClass(player) {
  if (player.hp_max === 0) return 'hp-unknown'
  const pct = player.hp_current / player.hp_max
  if (player.hp_current <= 0) return 'hp-dead'
  if (pct > 0.5) return 'hp-healthy'
  if (pct > 0.25) return 'hp-bloodied'
  return 'hp-critical'
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return iso
  }
}
</script>

<style scoped>
.admin-page {
  min-height: 100vh;
  padding-top: 80px;
  padding-bottom: 3rem;
  background: #0d0a06;
}

.admin-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.admin-header-left {
  flex: 1;
}

.admin-title {
  font-family: 'Cinzel', serif;
  font-size: 1.8rem;
  font-weight: 700;
  color: #c9a227;
  margin-bottom: 0.2rem;
}

.admin-subtitle {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #8a7355;
  font-size: 1rem;
}

.error-banner {
  background: rgba(139,26,26,0.2);
  border: 1px solid #7f1d1d;
  color: #f87171;
  font-family: 'Crimson Text', serif;
  padding: 0.75rem 1rem;
  border-radius: 5px;
  margin-bottom: 1.5rem;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: #8a7355;
  font-family: 'Crimson Text', serif;
  font-style: italic;
  padding: 2rem 0;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #3d2e10;
  border-top-color: #c9a227;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  color: #5a4530;
  font-family: 'Crimson Text', serif;
  font-style: italic;
  text-align: center;
  padding: 3rem 0;
}

/* Campaign cards */
.campaigns-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.campaign-card {
  padding: 1.25rem 1.5rem;
}

.campaign-header {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
}

.campaign-info {
  flex: 1;
  min-width: 0;
}

.campaign-name {
  font-family: 'Cinzel', serif;
  font-size: 1.15rem;
  font-weight: 700;
  color: #c9a227;
  margin-bottom: 0.4rem;
}

.campaign-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.meta-chip {
  font-family: 'Crimson Text', serif;
  font-size: 0.8rem;
  color: #8a7355;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 3px;
  padding: 0.1rem 0.45rem;
}

.players-chip {
  color: #e8d5b7;
}

/* Players sub-section */
.players-section {
  border-top: 1px solid #2a1e08;
  padding-top: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.no-players {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #4a3820;
  font-size: 0.9rem;
  padding: 0.25rem 0;
}

.player-row {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  transition: background 0.12s;
}
.player-row:hover {
  background: rgba(201,162,39,0.04);
}

.player-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3d2e10, #7a6115);
  color: #c9a227;
  font-family: 'Cinzel', serif;
  font-weight: 700;
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.player-info {
  flex: 1;
  min-width: 0;
  font-family: 'Crimson Text', serif;
  font-size: 0.95rem;
}

.player-username {
  color: #e8d5b7;
  font-weight: 600;
}

.player-char {
  color: #8a7355;
}

.player-race-class {
  font-size: 0.82rem;
  color: #5a4530;
}

.player-no-char {
  color: #4a3820;
  font-style: italic;
  font-size: 0.85rem;
}

.player-hp {
  flex-shrink: 0;
}

.hp-badge {
  font-family: 'Cinzel', serif;
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  border: 1px solid;
}
.hp-healthy  { color: #4ade80; border-color: rgba(74,222,128,0.4); background: rgba(74,222,128,0.08); }
.hp-bloodied { color: #fbbf24; border-color: rgba(251,191,36,0.4);  background: rgba(251,191,36,0.08);  }
.hp-critical { color: #f87171; border-color: rgba(248,113,113,0.4); background: rgba(248,113,113,0.08); }
.hp-dead     { color: #6b7280; border-color: rgba(107,114,128,0.4); background: rgba(107,114,128,0.08); }
.hp-unknown  { color: #5a4530; border-color: #3d2e10; background: transparent; }

/* Delete buttons */
.delete-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid #5a1f1f;
  background: rgba(127,29,29,0.15);
  color: #f87171;
  font-size: 0.75rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  line-height: 1;
}
.delete-btn:hover {
  background: rgba(127,29,29,0.4);
  border-color: #f87171;
  box-shadow: 0 0 8px rgba(248,113,113,0.3);
}

.delete-btn-sm {
  width: 22px;
  height: 22px;
  font-size: 0.65rem;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 1rem;
}

.modal {
  max-width: 440px;
  width: 100%;
  padding: 1.75rem 2rem;
}

.modal-title {
  font-family: 'Cinzel', serif;
  font-size: 1.15rem;
  font-weight: 700;
  color: #c9a227;
  margin-bottom: 0.75rem;
}

.modal-body {
  font-family: 'Crimson Text', serif;
  font-size: 1rem;
  color: #e8d5b7;
  margin-bottom: 0.5rem;
  line-height: 1.5;
}

.modal-note {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  font-size: 0.88rem;
  color: #7a6115;
  margin-bottom: 1.25rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
</style>
