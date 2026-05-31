<template>
  <div class="game-layout">
    <!-- Left Sidebar: Party -->
    <aside class="left-sidebar">
      <!-- Campaign info -->
      <div class="sidebar-section campaign-info">
        <div class="camp-title">{{ campaignStore.currentMeta?.name || 'Campaign' }}</div>
        <div class="camp-stats">
          <span class="dnd-badge dnd-badge-muted">Turn {{ campaignStore.currentMeta?.turn_number || 1 }}</span>
          <span class="dnd-badge mode-badge" :class="modeBadgeClass">
            {{ campaignStore.gameMode }}
          </span>
        </div>
      </div>

      <hr class="gold-divider-plain" />

      <!-- Party list -->
      <div class="sidebar-section">
        <div class="dnd-section-heading">
          <span>⚔</span> The Party
        </div>

        <div v-if="campaignStore.players.length === 0" class="no-players">
          <p>Awaiting adventurers...</p>
        </div>

        <div class="party-list">
          <div v-for="player in campaignStore.players" :key="player.character_object_id || player.user_id" class="party-item">
            <div class="online-dot" :class="{ online: true }"></div>
            <PlayerCard
              :player="player"
              :isActiveTurn="player.character_object_id === campaignStore.activeTurn"
            />
          </div>
        </div>
      </div>

      <hr class="gold-divider-plain" />

      <!-- Snapshot button -->
      <div class="sidebar-section">
        <button class="dnd-button-ghost snapshot-btn" @click="openSnapshotModal">
          📸 Create Snapshot
        </button>
      </div>

      <!-- Leave game -->
      <div class="sidebar-bottom">
        <button class="dnd-button-danger leave-btn" @click="leaveGame">
          ← Leave Game
        </button>
      </div>
    </aside>

    <!-- Center Panel: Chat + Actions -->
    <main class="center-panel">
      <!-- Campaign header bar -->
      <div class="game-header-bar">
        <span class="game-camp-name">{{ campaignStore.currentMeta?.name }}</span>
        <span class="dnd-badge mode-badge-sm" :class="modeBadgeClass">
          {{ campaignStore.gameMode }}
        </span>
        <span v-if="campaignStore.gameMode === 'Combat' && campaignStore.activeTurn" class="active-turn-info">
          Active: {{ activeTurnName }}
        </span>
        <div class="ws-indicator" :class="wsClass">
          <span class="ws-dot"></span>
          {{ campaignStore.wsStatus }}
        </div>
        <button
          v-if="myCharacterId"
          class="sheet-toggle-btn"
          :class="{ active: sheetOpen }"
          @click="sheetOpen = !sheetOpen"
          title="Character Sheet"
        >
          &#x1F4DC; Sheet
        </button>
      </div>

      <!-- Tab bar -->
      <div class="center-tab-bar">
        <button
          class="center-tab"
          :class="{ active: centerTab === 'chat' }"
          @click="centerTab = 'chat'"
        >Chat</button>
        <button
          class="center-tab"
          :class="{ active: centerTab === 'journal' }"
          @click="centerTab = 'journal'"
        >Journal <span v-if="campaignStore.journal.length" class="tab-badge">{{ campaignStore.journal.length }}</span></button>
      </div>

      <!-- Chat window -->
      <div v-show="centerTab === 'chat'" class="chat-area">
        <ChatWindow />
      </div>

      <!-- Journal -->
      <div v-show="centerTab === 'journal'" class="chat-area">
        <JournalTab />
      </div>

      <!-- Action bar (chat tab only) -->
      <ActionBar
        v-if="centerTab === 'chat'"
        :gameMode="campaignStore.gameMode"
        :activeTurn="campaignStore.activeTurn"
        :myCharacterId="myCharacterId"
        :characterConditions="myCharacterConditions"
      />
    </main>

    <!-- Right Sidebar: World Info -->
    <aside class="right-sidebar">
      <!-- Current Location -->
      <div class="sidebar-section">
        <div class="dnd-section-heading">
          <span>🗺</span> Location
        </div>
        <div class="location-name">
          {{ currentLocation?.name || 'Unknown Location' }}
        </div>
        <p class="location-desc parchment-text">
          {{ currentLocation?.description || 'The world holds its breath...' }}
        </p>
      </div>

      <hr class="gold-divider-plain" />

      <!-- Turn Info -->
      <div class="sidebar-section">
        <div class="dnd-section-heading">
          <span>⏳</span> Turn Info
        </div>
        <div class="turn-info-grid">
          <div class="turn-info-item">
            <span class="ti-label">Turn</span>
            <span class="ti-value">{{ campaignStore.currentMeta?.turn_number || 1 }}</span>
          </div>
          <div class="turn-info-item">
            <span class="ti-label">Mode</span>
            <span class="ti-value mode-badge-inline" :class="modeBadgeClass">{{ campaignStore.gameMode }}</span>
          </div>
          <div v-if="campaignStore.gameMode === 'Combat'" class="turn-info-item">
            <span class="ti-label">Active</span>
            <span class="ti-value">{{ activeTurnName || '—' }}</span>
          </div>
        </div>
      </div>

      <hr class="gold-divider-plain" />

      <!-- Initiative Tracker (Combat only) -->
      <div v-if="campaignStore.gameMode === 'Combat'" class="sidebar-section">
        <InitiativeTracker
          :order="campaignStore.initiativeOrder"
          :activeTurn="campaignStore.activeTurn"
        />
      </div>

      <hr v-if="campaignStore.gameMode === 'Combat'" class="gold-divider-plain" />

      <!-- Recent Events -->
      <div class="sidebar-section">
        <div class="dnd-section-heading">
          <span>📜</span> Recent Events
        </div>
        <div class="recent-events">
          <div
            v-for="(msg, idx) in recentEvents"
            :key="idx"
            class="event-item"
            :class="eventClass(msg)"
          >
            {{ truncate(msg.text || msg.message || msg.content, 80) }}
          </div>
          <div v-if="recentEvents.length === 0" class="no-events">
            No events yet...
          </div>
        </div>
      </div>

      <hr class="gold-divider-plain" />

      <!-- Quest Tracker -->
      <div class="sidebar-section">
        <div class="dnd-section-heading">
          <span>📋</span> Quests
        </div>
        <QuestTracker />
      </div>

      <hr class="gold-divider-plain" />

      <!-- Snapshots -->
      <div class="sidebar-section">
        <div
          class="dnd-section-heading snapshot-toggle"
          @click="snapshotsOpen = !snapshotsOpen"
          style="cursor:pointer"
        >
          <span>📸</span> Snapshots
          <span class="toggle-icon">{{ snapshotsOpen ? '▲' : '▼' }}</span>
        </div>
        <div v-if="snapshotsOpen" class="snapshots-list">
          <template v-if="campaignStore.snapshots.length === 0">
            <div class="no-snapshots">No snapshots yet.</div>
          </template>
          <template v-else>
            <SnapshotNode
              v-for="node in snapshotTree"
              :key="node.snap.id"
              :node="node"
              :restoringId="restoringSnapshotId"
              @restore="confirmRestore"
            />
          </template>
        </div>
      </div>
    </aside>

    <!-- Snapshot Modal -->
    <Teleport to="body">
      <div v-if="showSnapshotModal" class="modal-overlay" @click.self="showSnapshotModal = false">
        <div class="modal-box dnd-panel dnd-panel-gold">
          <h3 class="modal-title">Create Snapshot</h3>
          <p class="modal-desc">Save the current game state with a label.</p>
          <div class="form-field">
            <label class="dnd-label">Snapshot Label</label>
            <input
              v-model="snapshotLabel"
              class="dnd-input"
              placeholder="e.g. Before the Dragon's Lair"
              @keydown.enter="createSnapshot"
              ref="snapInputEl"
            />
          </div>
          <div class="modal-actions">
            <button class="dnd-button-ghost" @click="showSnapshotModal = false">Cancel</button>
            <button class="dnd-button" @click="createSnapshot" :disabled="!snapshotLabel.trim()">
              Save Snapshot
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Level-Up Dialog -->
    <LevelUpDialog :campaignId="campaignId" @confirmed="onLevelUpConfirmed" />

    <!-- Loot Summary -->
    <LootSummary />

    <!-- Character Sheet Panel -->
    <CharacterSheet
      :open="sheetOpen"
      :campaignId="campaignId"
      :characterId="myCharacterId"
      @close="sheetOpen = false"
    />

    <!-- Restore Confirm Modal -->
    <Teleport to="body">
      <div v-if="restoreTarget" class="modal-overlay" @click.self="restoreTarget = null">
        <div class="modal-box dnd-panel dnd-panel-gold">
          <h3 class="modal-title">Restore Snapshot</h3>
          <p class="modal-desc">
            Restore to <strong class="snap-confirm-label">{{ restoreTarget.label }}</strong>?
            Current world state will be overwritten.
          </p>
          <div class="modal-actions">
            <button class="dnd-button-ghost" @click="restoreTarget = null">Cancel</button>
            <button class="dnd-button dnd-button-danger" @click="doRestore">
              Restore
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCampaignStore } from '../stores/campaign'
import { useAuthStore } from '../stores/auth'
import PlayerCard from '../components/PlayerCard.vue'
import ChatWindow from '../components/ChatWindow.vue'
import ActionBar from '../components/ActionBar.vue'
import SnapshotNode from '../components/SnapshotNode.vue'
import LevelUpDialog from '../components/LevelUpDialog.vue'
import CharacterSheet from '../components/CharacterSheet.vue'
import InitiativeTracker from '../components/InitiativeTracker.vue'
import LootSummary from '../components/LootSummary.vue'
import JournalTab from '../components/JournalTab.vue'
import QuestTracker from '../components/QuestTracker.vue'

const route = useRoute()
const router = useRouter()
const campaignStore = useCampaignStore()
const authStore = useAuthStore()

const campaignId = route.params.id
const centerTab = ref('chat')
const snapshotsOpen = ref(false)
const showSnapshotModal = ref(false)
const snapshotLabel = ref('')
const snapInputEl = ref(null)
const restoreTarget = ref(null)
const restoringSnapshotId = ref(null)
const sheetOpen = ref(false)

// Computed
const myCharacterId = computed(() => {
  if (!authStore.user) return null
  const me = campaignStore.players.find(p => p.user_id === authStore.user.user_id)
  return me?.character_object_id || null
})

const myCharacterConditions = computed(() => {
  if (!authStore.user) return []
  const me = campaignStore.players.find(p => p.user_id === authStore.user.user_id)
  return me?.conditions || []
})

const modeBadgeClass = computed(() => {
  const m = (campaignStore.gameMode || '').toLowerCase()
  return `mode-${m}`
})

const wsClass = computed(() => {
  switch (campaignStore.wsStatus) {
    case 'connected':    return 'ws-connected'
    case 'connecting':   return 'ws-connecting'
    case 'error':        return 'ws-error'
    default:             return 'ws-disconnected'
  }
})

const currentLocation = computed(() => {
  return campaignStore.currentMeta?.location || null
})

const recentEvents = computed(() => {
  return [...campaignStore.chat].slice(-5).reverse()
})

const activeTurnName = computed(() => {
  if (!campaignStore.activeTurn) return null
  const p = campaignStore.players.find(pl => pl.character_object_id === campaignStore.activeTurn)
  return p?.character_name || `Player #${campaignStore.activeTurn}`
})

// Build parent→child tree from the flat snapshot list.
// Each node: { snap, children[] }
const snapshotTree = computed(() => {
  const snaps = campaignStore.snapshots
  const byId = {}
  snaps.forEach(s => { byId[s.id] = { snap: s, children: [] } })
  const roots = []
  snaps.forEach(s => {
    const parent = s.parent_snapshot && byId[s.parent_snapshot]
    if (parent) {
      parent.children.push(byId[s.id])
    } else {
      roots.push(byId[s.id])
    }
  })
  return roots
})

// Methods
function truncate(text, len) {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '...' : text
}

function eventClass(msg) {
  const type = (msg.sender_type || '').toUpperCase()
  if (type === 'DM')     return 'event-dm'
  if (type === 'PC')     return 'event-pc'
  return 'event-system'
}

function openSnapshotModal() {
  snapshotLabel.value = ''
  showSnapshotModal.value = true
  nextTick(() => {
    if (snapInputEl.value) snapInputEl.value.focus()
  })
}

function createSnapshot() {
  if (!snapshotLabel.value.trim()) return
  campaignStore.sendSnapshot(snapshotLabel.value.trim())
  showSnapshotModal.value = false
  snapshotLabel.value = ''
}

function confirmRestore(snap) {
  restoreTarget.value = snap
}

async function doRestore() {
  const snap = restoreTarget.value
  if (!snap) return
  const snapId = snap.id || snap.snapshot_id
  restoreTarget.value = null
  restoringSnapshotId.value = snapId
  await campaignStore.restoreSnapshot(campaignId, snapId)
  restoringSnapshotId.value = null
}

function leaveGame() {
  campaignStore.disconnectWs()
  router.push('/campaigns')
}

function onLevelUpConfirmed({ hpGain, asiChoices }) {
  // Broadcast the level-up to chat so all players see it
  const me = campaignStore.players.find(p => p.user_id === authStore.user?.user_id)
  const name = me?.character_name || 'A hero'
  campaignStore.sendChat(`${name} leveled up! +${hpGain} HP gained.`)
}

onMounted(async () => {
  await campaignStore.loadState(campaignId)
  campaignStore.connectWs(campaignId)
  await campaignStore.fetchSnapshots(campaignId)
  await campaignStore.fetchJournal(campaignId)
  await campaignStore.fetchQuests(campaignId)
})

onUnmounted(() => {
  campaignStore.disconnectWs()
})
</script>

<style scoped>
.game-layout {
  display: flex;
  height: calc(100vh - 64px);
  overflow: hidden;
  background: #0d0a06;
}

/* ===== LEFT SIDEBAR ===== */
.left-sidebar {
  width: 220px;
  flex-shrink: 0;
  background: #110d05;
  border-right: 1px solid #3d2e10;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ===== CENTER PANEL ===== */
.center-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  background: #0d0a06;
}

/* ===== RIGHT SIDEBAR ===== */
.right-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: #110d05;
  border-left: 1px solid #3d2e10;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Shared sidebar section */
.sidebar-section {
  padding: 0.875rem;
}

.sidebar-bottom {
  padding: 0.875rem;
  margin-top: auto;
  border-top: 1px solid #3d2e10;
}

/* Campaign info */
.campaign-info { background: rgba(201,162,39,0.04); }

.camp-title {
  font-family: 'Cinzel', serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: #c9a227;
  margin-bottom: 0.4rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.camp-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

/* Party list */
.no-players {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #8a7355;
  font-size: 0.85rem;
}

.party-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.party-item {
  position: relative;
}

.online-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3d2e10;
  z-index: 1;
}
.online-dot.online {
  background: #4ade80;
  box-shadow: 0 0 5px rgba(74,222,128,0.6);
}

.snapshot-btn {
  width: 100%;
  font-size: 0.72rem;
  padding: 0.4rem;
}

.leave-btn {
  width: 100%;
  font-size: 0.72rem;
  justify-content: center;
}

/* Center panel header */
.game-header-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  background: #110d05;
  border-bottom: 1px solid #3d2e10;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.game-camp-name {
  font-family: 'Cinzel', serif;
  font-size: 0.85rem;
  font-weight: 600;
  color: #c9a227;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.mode-badge-sm {
  font-size: 0.62rem;
}

.mode-badge-inline {
  font-family: 'Cinzel', serif;
  font-size: 0.62rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.active-turn-info {
  font-family: 'Crimson Text', serif;
  font-size: 0.85rem;
  color: #8a7355;
  font-style: italic;
}

.sheet-toggle-btn {
  background: transparent;
  border: 1px solid #3d2e10;
  color: #8a7355;
  cursor: pointer;
  font-family: 'Cinzel', serif;
  font-size: 0.6rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 0.2rem 0.55rem;
  border-radius: 3px;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
  margin-left: 0.35rem;
}
.sheet-toggle-btn:hover {
  color: #c9a227;
  border-color: #c9a227;
}
.sheet-toggle-btn.active {
  color: #c9a227;
  border-color: #7a6115;
  background: rgba(201, 162, 39, 0.1);
}

.ws-indicator {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-family: 'Cinzel', serif;
  font-size: 0.6rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-left: auto;
}
.ws-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.ws-connected    { color: #4ade80; }
.ws-connecting   { color: #fde68a; }
.ws-disconnected { color: #8a7355; }
.ws-error        { color: #f87171; }

/* Center tab bar */
.center-tab-bar {
  display: flex;
  flex-shrink: 0;
  background: #110d05;
  border-bottom: 1px solid #3d2e10;
}

.center-tab {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: #8a7355;
  cursor: pointer;
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  padding: 0.45rem 0.9rem;
  transition: color 0.15s, border-color 0.15s;
}

.center-tab:hover {
  color: #c9a227;
}

.center-tab.active {
  color: #c9a227;
  border-bottom-color: #c9a227;
}

.tab-badge {
  display: inline-block;
  background: rgba(201,162,39,0.2);
  color: #c9a227;
  font-size: 0.55rem;
  padding: 0 0.3rem;
  border-radius: 8px;
  margin-left: 0.25rem;
  line-height: 1.4;
}

/* Chat area */
.chat-area {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Right sidebar sections */
.location-name {
  font-family: 'Cinzel', serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: #c9a227;
  margin-bottom: 0.35rem;
}

.location-desc {
  font-size: 0.88rem;
  line-height: 1.5;
  margin: 0;
}

.turn-info-grid {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.turn-info-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.ti-label {
  font-family: 'Cinzel', serif;
  font-size: 0.62rem;
  letter-spacing: 0.08em;
  color: #8a7355;
  text-transform: uppercase;
}
.ti-value {
  font-family: 'Cinzel', serif;
  font-size: 0.8rem;
  font-weight: 600;
  color: #e8d5b7;
}

/* Recent events */
.recent-events {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.event-item {
  font-family: 'Crimson Text', serif;
  font-size: 0.82rem;
  line-height: 1.35;
  padding: 0.3rem 0.5rem;
  border-radius: 3px;
  border-left: 2px solid transparent;
}
.event-dm     { color: #c9a227; border-left-color: #7a6115; background: rgba(201,162,39,0.05); font-style: italic; }
.event-pc     { color: #e8d5b7; border-left-color: #3d2e10; }
.event-system { color: #8a7355; font-style: italic; }
.no-events    { color: #5a4530; font-style: italic; font-size: 0.82rem; font-family: 'Crimson Text', serif; }

/* Snapshots */
.snapshot-toggle {
  margin-bottom: 0;
}
.toggle-icon {
  margin-left: auto;
  font-size: 0.65rem;
  color: #8a7355;
}
.snapshots-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-top: 0.5rem;
}
.snapshot-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.3rem 0.5rem;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 3px;
}
.snap-label {
  font-family: 'Crimson Text', serif;
  font-size: 0.82rem;
  color: #e8d5b7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}
.snap-restore-btn {
  flex-shrink: 0;
  background: transparent;
  border: 1px solid #3d2e10;
  color: #8a7355;
  cursor: pointer;
  font-size: 0.72rem;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  line-height: 1;
  transition: color 0.15s, border-color 0.15s;
}
.snap-restore-btn:hover:not(:disabled) {
  color: #c9a227;
  border-color: #c9a227;
}
.snap-restore-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.snap-confirm-label {
  color: #c9a227;
}
.no-snapshots {
  color: #5a4530;
  font-style: italic;
  font-size: 0.82rem;
  font-family: 'Crimson Text', serif;
}

/* Game mode badge classes */
.mode-exploration { color: #86efac; border-color: #14532d; background: rgba(26,74,26,0.3); }
.mode-combat      { color: #fca5a5; border-color: #7f1d1d; background: rgba(139,26,26,0.3); }
.mode-social      { color: #93c5fd; border-color: #1e3a5f; background: rgba(30,58,95,0.3); }
.mode-travel      { color: #fde68a; border-color: #713f12; background: rgba(113,63,18,0.3); }

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

.modal-box {
  max-width: 440px;
  width: 100%;
}

.modal-title {
  font-family: 'Cinzel', serif;
  font-size: 1.2rem;
  font-weight: 600;
  color: #c9a227;
  margin-bottom: 0.35rem;
}

.modal-desc {
  color: #8a7355;
  font-style: italic;
  font-size: 0.95rem;
  margin-bottom: 1rem;
}

.modal-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

/* Responsive: hide sidebars on small screens */
@media (max-width: 900px) {
  .right-sidebar { display: none; }
}
@media (max-width: 640px) {
  .left-sidebar { width: 180px; }
}
@media (max-width: 480px) {
  .left-sidebar { display: none; }
}
</style>
