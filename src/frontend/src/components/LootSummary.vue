<template>
  <Teleport to="body">
    <div v-if="loot" class="modal-overlay" @click.self="dismiss">
      <div class="modal-box dnd-panel dnd-panel-gold loot-box">
        <!-- Header -->
        <div class="loot-header">
          <div class="loot-icon-row">
            <span class="loot-icon">&#x2694;</span>
            <span class="loot-icon loot-icon-lg">&#x1F4B0;</span>
            <span class="loot-icon">&#x2694;</span>
          </div>
          <h2 class="loot-title">Victory!</h2>
          <p class="loot-subtitle">
            Enemies defeated:
            <span class="loot-enemies">{{ loot.enemies_defeated.join(', ') || 'Unknown foes' }}</span>
          </p>
        </div>

        <hr class="gold-divider-plain" />

        <!-- Coin summary -->
        <div v-if="hasCoin" class="loot-section">
          <div class="loot-section-label">Coin</div>
          <div class="loot-coins-row">
            <span v-if="loot.coins.gp" class="coin-badge coin-gp">{{ loot.coins.gp }} gp</span>
            <span v-if="loot.coins.sp" class="coin-badge coin-sp">{{ loot.coins.sp }} sp</span>
            <span v-if="loot.coins.cp" class="coin-badge coin-cp">{{ loot.coins.cp }} cp</span>
          </div>
        </div>

        <!-- Items -->
        <div v-if="items.length > 0" class="loot-section">
          <div class="loot-section-label">Items</div>
          <div class="loot-items-list">
            <div
              v-for="item in items"
              :key="item.id"
              class="loot-item"
              :class="{ 'loot-item-taken': item.taken_by }"
            >
              <div class="loot-item-info">
                <span class="loot-item-name">{{ item.name }}</span>
                <span class="loot-item-desc">{{ item.description }}</span>
                <span class="loot-item-weight">{{ item.weight }} lb · {{ item.cost_gp }} gp</span>
              </div>
              <div class="loot-item-action">
                <span v-if="item.taken_by" class="loot-taken-by">
                  Taken by {{ item.taken_by }}
                </span>
                <button
                  v-else-if="myCharacterId"
                  class="dnd-button loot-take-btn"
                  @click="takeItem(item)"
                >
                  Take
                </button>
                <span v-else class="loot-no-char">—</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!hasCoin && items.length === 0" class="loot-empty">
          <span class="parchment-text">The enemies carried nothing of value.</span>
        </div>

        <div class="modal-actions">
          <button class="dnd-button-ghost" @click="dismiss">Close</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useCampaignStore } from '../stores/campaign'
import { useAuthStore } from '../stores/auth'

const campaignStore = useCampaignStore()
const authStore = useAuthStore()

const loot = computed(() => campaignStore.pendingLoot)

const hasCoin = computed(() => {
  if (!loot.value) return false
  const { gp, sp, cp } = loot.value.coins
  return gp > 0 || sp > 0 || cp > 0
})

const items = computed(() => loot.value?.items || [])

const myCharacterId = computed(() => {
  if (!authStore.user) return null
  const me = campaignStore.players.find(p => p.user_id === authStore.user.user_id)
  return me?.character_object_id || null
})

function takeItem(item) {
  if (!myCharacterId.value) return
  campaignStore.sendTakeLoot(item.id, myCharacterId.value)
}

function dismiss() {
  campaignStore.clearLoot()
}

function onWindowKeydown(event) {
  if (!loot.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopImmediatePropagation()
    dismiss()
  }
}

onMounted(() => window.addEventListener('keydown', onWindowKeydown))
onUnmounted(() => window.removeEventListener('keydown', onWindowKeydown))
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

.loot-box {
  max-width: 500px;
  width: 100%;
  animation: loot-appear 0.3s ease;
}

@keyframes loot-appear {
  from { opacity: 0; transform: scale(0.92) translateY(-12px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}

.loot-header {
  text-align: center;
  margin-bottom: 0.75rem;
}

.loot-icon-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.35rem;
}

.loot-icon {
  color: #c9a227;
  font-size: 1.1rem;
}

.loot-icon-lg {
  font-size: 1.7rem;
}

.loot-title {
  font-family: 'Cinzel', serif;
  font-size: 1.6rem;
  font-weight: 700;
  color: #c9a227;
  text-shadow: 0 0 16px rgba(201,162,39,0.5);
  margin: 0 0 0.2rem;
}

.loot-subtitle {
  font-family: 'Crimson Text', serif;
  font-size: 1rem;
  color: #e8d5b7;
  margin: 0;
}

.loot-enemies {
  color: #e07272;
  font-style: italic;
}

.loot-section {
  margin-top: 0.9rem;
}

.loot-section-label {
  font-family: 'Cinzel', serif;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #8a7355;
  margin-bottom: 0.45rem;
}

/* Coins */
.loot-coins-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.coin-badge {
  font-family: 'Cinzel', serif;
  font-size: 0.9rem;
  font-weight: 700;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  border: 1px solid;
}

.coin-gp {
  color: #c9a227;
  border-color: #c9a227;
  background: rgba(201,162,39,0.1);
}

.coin-sp {
  color: #aaa;
  border-color: #666;
  background: rgba(180,180,180,0.08);
}

.coin-cp {
  color: #b87333;
  border-color: #7a4d22;
  background: rgba(184,115,51,0.1);
}

/* Items list */
.loot-items-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.loot-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0.6rem;
  background: rgba(201,162,39,0.04);
  border: 1px solid #3d2e10;
  border-radius: 4px;
  transition: opacity 0.2s;
}

.loot-item-taken {
  opacity: 0.5;
}

.loot-item-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.loot-item-name {
  font-family: 'Cinzel', serif;
  font-size: 0.82rem;
  font-weight: 600;
  color: #e8d5b7;
}

.loot-item-desc {
  font-family: 'Crimson Text', serif;
  font-size: 0.82rem;
  color: #8a7355;
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 280px;
}

.loot-item-weight {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  color: #5a4830;
  letter-spacing: 0.04em;
}

.loot-item-action {
  flex-shrink: 0;
}

.loot-take-btn {
  padding: 0.25rem 0.75rem;
  font-size: 0.78rem;
}

.loot-taken-by {
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  color: #4ade80;
}

.loot-no-char {
  color: #5a4830;
  font-size: 0.82rem;
}

.loot-empty {
  margin-top: 0.75rem;
  text-align: center;
  font-size: 0.9rem;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 1.25rem;
}
</style>
