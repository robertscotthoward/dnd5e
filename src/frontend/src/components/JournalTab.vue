<template>
  <div class="journal-panel">
    <div class="journal-header">
      <span class="journal-title">Campaign Journal</span>
      <span class="journal-count" v-if="entries.length">{{ entries.length }} entries</span>
    </div>

    <div v-if="entries.length === 0" class="journal-empty">
      <p>No journal entries yet. The chronicle begins when the DM speaks.</p>
    </div>

    <div v-else class="journal-scroll" ref="scrollEl">
      <div
        v-for="(entry, idx) in reversedEntries"
        :key="idx"
        class="journal-entry"
      >
        <div class="entry-turn">Turn {{ entry.turn_number }}</div>
        <p class="entry-text">{{ entry.entry }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useCampaignStore } from '../stores/campaign'

const campaignStore = useCampaignStore()
const scrollEl = ref(null)

const entries = computed(() => campaignStore.journal)
const reversedEntries = computed(() => [...campaignStore.journal].reverse())
</script>

<style scoped>
.journal-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0d0a06;
}

.journal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: #110d05;
  border-bottom: 1px solid #3d2e10;
  flex-shrink: 0;
}

.journal-title {
  font-family: 'Cinzel', serif;
  font-size: 0.85rem;
  font-weight: 600;
  color: #c9a227;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.journal-count {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  color: #8a7355;
  letter-spacing: 0.05em;
}

.journal-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.journal-empty p {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #5a4530;
  font-size: 0.95rem;
  text-align: center;
}

.journal-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.journal-entry {
  background: #110d05;
  border: 1px solid #3d2e10;
  border-left: 3px solid #7a6115;
  border-radius: 3px;
  padding: 0.75rem 1rem;
}

.entry-turn {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #8a7355;
  margin-bottom: 0.4rem;
}

.entry-text {
  font-family: 'Crimson Text', serif;
  font-size: 1rem;
  line-height: 1.6;
  color: #e8d5b7;
  margin: 0;
  font-style: italic;
}
</style>
