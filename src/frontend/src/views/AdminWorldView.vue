<template>
  <div class="admin-page">
    <!-- Left sidebar -->
    <aside class="admin-sidebar">
      <div class="sidebar-label">Admin</div>
      <RouterLink to="/admin" class="sidebar-link">⚙ Console</RouterLink>
    </aside>

    <!-- Main content -->
    <div class="admin-main">
      <div class="admin-container">
        <!-- Header -->
        <div class="admin-header">
          <div class="admin-header-left">
            <h1 class="admin-title">{{ campaignId }}</h1>
            <p class="admin-subtitle">World object tree</p>
          </div>
          <RouterLink to="/admin" class="dnd-button-ghost">← Console</RouterLink>
        </div>

        <div class="gold-divider" style="margin-bottom:2rem"></div>

        <div v-if="error" class="error-banner">{{ error }}</div>

        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <span>Loading world…</span>
        </div>

        <div v-else-if="!flatNodes.length" class="empty-state">
          No world objects found.
        </div>

        <div v-else class="world-tree dnd-panel">
          <div
            v-for="node in flatNodes"
            :key="node.id"
            class="tree-node"
            :style="{ paddingLeft: (node.depth * 1.5 + 0.75) + 'rem' }"
          >
            <span class="node-name">{{ node.name || '(unnamed)' }}</span>
            <span class="node-type"> ({{ node.type }})</span>
            <span class="node-desc" v-if="node.description"> — {{ node.description }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const campaignId = route.params.id

const rawObjects = ref([])
const loading = ref(false)
const error = ref(null)

onMounted(async () => {
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`/api/admin/world/${campaignId}`, { credentials: 'include' })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      throw new Error(d.detail || 'Failed to load world')
    }
    const data = await res.json()
    rawObjects.value = data.objects
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const flatNodes = computed(() => {
  const objects = rawObjects.value
  if (!objects.length) return []

  function traverse(parentId, depth) {
    return objects
      .filter(o => o.parent === parentId)
      .flatMap(o => [{ ...o, depth }, ...traverse(o.id, depth + 1)])
  }

  return traverse(null, 0)
})
</script>

<style scoped>
.admin-page {
  display: flex;
  min-height: 100vh;
  padding-top: 64px;
  background: #0d0a06;
}

/* ===== Sidebar ===== */
.admin-sidebar {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px solid #2a1e08;
  padding: 1.5rem 0;
  background: #0a0703;
  min-height: calc(100vh - 64px);
}

.sidebar-label {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #4a3820;
  text-transform: uppercase;
  padding: 0 1rem 0.5rem;
}

.sidebar-link {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 1rem;
  font-family: 'Cinzel', serif;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #8a7355;
  text-decoration: none;
  transition: background 0.12s, color 0.12s;
}
.sidebar-link:hover {
  background: rgba(201,162,39,0.06);
  color: #c9a227;
}
.sidebar-link.active {
  background: rgba(201,162,39,0.1);
  color: #c9a227;
  border-right: 2px solid #c9a227;
}

/* ===== Main ===== */
.admin-main {
  flex: 1;
  min-width: 0;
  padding-bottom: 3rem;
}

.admin-container {
  max-width: 960px;
  padding: 2rem 1.5rem;
}

.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.admin-header-left { flex: 1; }

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

/* ===== World tree ===== */
.world-tree {
  padding: 0.5rem 0;
}

.tree-node {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0;
  padding-top: 0.3rem;
  padding-bottom: 0.3rem;
  padding-right: 1rem;
  border-bottom: 1px solid rgba(42,30,8,0.5);
  font-family: 'Crimson Text', serif;
  font-size: 0.97rem;
  line-height: 1.4;
}
.tree-node:last-child {
  border-bottom: none;
}

.node-name {
  font-family: 'Cinzel', serif;
  font-size: 0.82rem;
  font-weight: 700;
  color: #c9a227;
}

.node-type {
  font-family: 'Crimson Text', serif;
  font-size: 0.85rem;
  color: #7a6115;
}

.node-desc {
  color: #8a7355;
  font-size: 0.93rem;
}
</style>
