<template>
  <div class="snap-tree-node">
    <div class="snapshot-item">
      <span class="snap-connector" v-if="depth > 0">└</span>
      <span class="snap-label">{{ node.snap.label || 'Snapshot' }}</span>
      <button
        class="snap-restore-btn"
        :disabled="restoringId === node.snap.id"
        @click="$emit('restore', node.snap)"
        title="Restore to this snapshot"
      >
        {{ restoringId === node.snap.id ? '...' : '↩' }}
      </button>
    </div>
    <div v-if="node.children.length" class="snap-children">
      <SnapshotNode
        v-for="child in node.children"
        :key="child.snap.id"
        :node="child"
        :depth="depth + 1"
        :restoringId="restoringId"
        @restore="$emit('restore', $event)"
      />
    </div>
  </div>
</template>

<script setup>
defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  restoringId: { type: String, default: null },
})
defineEmits(['restore'])
</script>

<style scoped>
.snap-tree-node {
  display: flex;
  flex-direction: column;
}

.snapshot-item {
  display: flex;
  align-items: center;
  padding: 0.3rem 0.5rem;
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-radius: 3px;
  margin-bottom: 0.3rem;
  gap: 0.3rem;
}

.snap-connector {
  flex-shrink: 0;
  color: #5a4530;
  font-size: 0.75rem;
  line-height: 1;
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

.snap-children {
  padding-left: 1rem;
  border-left: 1px solid #3d2e10;
  margin-left: 0.75rem;
  margin-bottom: 0.2rem;
}
</style>
