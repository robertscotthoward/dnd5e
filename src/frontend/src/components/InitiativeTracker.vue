<template>
  <div class="initiative-tracker">
    <div class="dnd-section-heading">
      <span>⚔</span> Initiative
    </div>
    <div class="init-list">
      <div
        v-for="(entry, idx) in order"
        :key="entry.id"
        class="init-row"
        :class="{ 'init-active': entry.id === activeTurn }"
      >
        <span class="init-pos">{{ idx + 1 }}</span>
        <span class="init-name">{{ entry.name }}</span>
        <span class="init-score">{{ entry.initiative }}</span>
        <span v-if="entry.id === activeTurn" class="init-arrow">▶</span>
      </div>
      <div v-if="order.length === 0" class="no-init">
        No active combat.
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  order: {
    type: Array,
    default: () => [],
  },
  activeTurn: {
    type: Number,
    default: null,
  },
})
</script>

<style scoped>
.initiative-tracker {
  padding: 0;
}

.init-list {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin-top: 0.35rem;
}

.init-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.3rem 0.5rem;
  border-radius: 3px;
  border-left: 2px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}

.init-row.init-active {
  background: rgba(201, 162, 39, 0.12);
  border-left-color: #c9a227;
}

.init-pos {
  font-family: 'Cinzel', serif;
  font-size: 0.62rem;
  color: #5a4530;
  width: 1rem;
  text-align: center;
  flex-shrink: 0;
}

.init-name {
  font-family: 'Crimson Text', serif;
  font-size: 0.9rem;
  color: #e8d5b7;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.init-row.init-active .init-name {
  color: #c9a227;
  font-weight: 600;
}

.init-score {
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  color: #8a7355;
  flex-shrink: 0;
  min-width: 1.4rem;
  text-align: right;
}

.init-arrow {
  font-size: 0.55rem;
  color: #c9a227;
  flex-shrink: 0;
}

.no-init {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #5a4530;
  font-size: 0.82rem;
  padding: 0.3rem 0.5rem;
}
</style>
