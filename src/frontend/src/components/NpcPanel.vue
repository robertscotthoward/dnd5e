<template>
  <div class="npc-panel">
    <div v-if="npcs.length === 0" class="npc-empty">
      No known NPCs.
    </div>
    <div v-else class="npc-list">
      <div v-for="npc in npcs" :key="npc.id" class="npc-card">
        <div class="npc-header">
          <span class="npc-name">{{ npc.name }}</span>
          <span class="npc-badge" :class="dispositionClass(npc.disposition)">
            {{ npc.disposition }}
          </span>
        </div>
        <p v-if="npc.notes" class="npc-notes">{{ npc.notes }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useCampaignStore } from '../stores/campaign'

const campaignStore = useCampaignStore()
const npcs = computed(() => campaignStore.npcRelationships)

function dispositionClass(d) {
  switch (d) {
    case 'friendly': return 'disp-friendly'
    case 'allied':   return 'disp-allied'
    case 'hostile':  return 'disp-hostile'
    default:         return 'disp-neutral'
  }
}
</script>

<style scoped>
.npc-panel {
  display: flex;
  flex-direction: column;
}

.npc-empty {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #5a4530;
  font-size: 0.82rem;
}

.npc-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.npc-card {
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-left: 3px solid #7a6115;
  border-radius: 3px;
  padding: 0.45rem 0.6rem;
}

.npc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
}

.npc-name {
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  font-weight: 600;
  color: #e8d5b7;
  letter-spacing: 0.03em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.npc-badge {
  font-family: 'Cinzel', serif;
  font-size: 0.58rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.1rem 0.4rem;
  border-radius: 2px;
  flex-shrink: 0;
}

.disp-friendly { background: rgba(74,222,128,0.12); color: #86efac; border: 1px solid #14532d; }
.disp-allied   { background: rgba(147,197,253,0.12); color: #93c5fd; border: 1px solid #1e3a5f; }
.disp-hostile  { background: rgba(252,165,165,0.12); color: #fca5a5; border: 1px solid #7f1d1d; }
.disp-neutral  { background: rgba(253,230,138,0.08); color: #fde68a; border: 1px solid #713f12; }

.npc-notes {
  font-family: 'Crimson Text', serif;
  font-size: 0.8rem;
  color: #8a7355;
  font-style: italic;
  margin: 0.3rem 0 0;
  line-height: 1.35;
}
</style>
