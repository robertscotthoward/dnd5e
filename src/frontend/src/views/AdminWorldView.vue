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

        <div class="gold-divider" style="margin-bottom:1.5rem"></div>

        <div v-if="error" class="error-banner">{{ error }}</div>

        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <span>Loading world…</span>
        </div>

        <div v-else-if="!flatNodes.length && !error" class="empty-state">
          No world objects found.
        </div>

        <!-- Two-column layout: tree + detail -->
        <div v-else-if="flatNodes.length" class="world-layout">

          <!-- Tree column -->
          <div class="tree-col">
            <div class="world-tree dnd-panel">
              <div
                v-for="node in flatNodes"
                :key="node.id"
                class="tree-node"
                :class="{ selected: selectedNode?.id === node.id }"
                :style="{ paddingLeft: (node.depth * 1.5 + 0.75) + 'rem' }"
                @click="selectedNode = node"
              >
                <span class="node-name">{{ node.name || '(unnamed)' }}</span>
                <span class="node-type"> ({{ node.type }})</span>
                <span class="node-desc" v-if="node.description"> — {{ node.description }}</span>
              </div>
            </div>
          </div>

          <!-- Detail column -->
          <div class="detail-col">
            <!-- Placeholder when nothing selected -->
            <div v-if="!selectedNode" class="detail-empty dnd-panel">
              <span class="detail-empty-text">Select an item to view details</span>
            </div>

            <!-- Detail panel -->
            <div v-else class="detail-panel dnd-panel">
              <!-- Detail header -->
              <div class="detail-header">
                <span class="detail-name">{{ selectedNode.name || '(unnamed)' }}</span>
                <span class="detail-type-badge">{{ selectedNode.type }}</span>
              </div>
              <p class="detail-desc" v-if="selectedNode.description">{{ selectedNode.description }}</p>

              <!-- Metadata -->
              <div class="detail-section">
                <div class="detail-meta-row">
                  <span class="meta-key">id</span>
                  <span class="meta-val">{{ selectedNode.id }}</span>
                </div>
                <div class="detail-meta-row" v-if="selectedNode.parent !== null && selectedNode.parent !== undefined">
                  <span class="meta-key">parent</span>
                  <span class="meta-val meta-val-link" @click="selectById(selectedNode.parent)">
                    {{ parentName(selectedNode.parent) }} (#{{ selectedNode.parent }})
                  </span>
                </div>
              </div>

              <!-- Properties -->
              <template v-if="propLines(selectedNode.properties).length">
                <div class="detail-divider"></div>
                <div class="detail-props">
                  <div
                    v-for="(line, i) in propLines(selectedNode.properties)"
                    :key="i"
                    class="prop-line"
                    :style="{ paddingLeft: (line.depth * 1.25) + 'rem' }"
                  >
                    <span v-if="line.value !== null">
                      <span class="prop-key">{{ line.key }}</span>
                      <span class="prop-sep">: </span>
                      <span class="prop-val">{{ line.value }}</span>
                    </span>
                    <span v-else class="prop-section">{{ line.key }}</span>
                  </div>
                </div>
              </template>
            </div>
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
const selectedNode = ref(null)

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

function parentName(parentId) {
  const obj = rawObjects.value.find(o => o.id === parentId)
  return obj?.name || '(unnamed)'
}

function selectById(id) {
  const node = flatNodes.value.find(n => n.id === id)
  if (node) selectedNode.value = node
}

// Flatten an arbitrary nested object/array into display lines { depth, key, value }
// value === null means it is a section header (object/array key with children below it)
function propLines(props, depth = 0) {
  if (!props || typeof props !== 'object') return []
  const lines = []
  for (const [key, val] of Object.entries(props)) {
    if (val === null || val === undefined) continue
    if (Array.isArray(val)) {
      lines.push({ depth, key, value: null })
      val.forEach((item, i) => {
        if (item && typeof item === 'object') {
          lines.push({ depth: depth + 1, key: `[${i}]`, value: null })
          lines.push(...propLines(item, depth + 2))
        } else {
          lines.push({ depth: depth + 1, key: String(i), value: String(item) })
        }
      })
    } else if (typeof val === 'object') {
      lines.push({ depth, key, value: null })
      lines.push(...propLines(val, depth + 1))
    } else {
      lines.push({ depth, key, value: String(val) })
    }
  }
  return lines
}
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
  overflow: hidden;
}

.admin-container {
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

/* ===== Two-column layout ===== */
.world-layout {
  display: flex;
  gap: 1.25rem;
  align-items: flex-start;
}

.tree-col {
  flex: 1;
  min-width: 0;
}

.detail-col {
  width: 340px;
  flex-shrink: 0;
  position: sticky;
  top: 80px;
}

/* ===== Tree ===== */
.world-tree {
  padding: 0.25rem 0;
}

.tree-node {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  padding-top: 0.3rem;
  padding-bottom: 0.3rem;
  padding-right: 1rem;
  border-bottom: 1px solid rgba(42,30,8,0.5);
  font-family: 'Crimson Text', serif;
  font-size: 0.97rem;
  line-height: 1.4;
  cursor: pointer;
  transition: background 0.1s;
}
.tree-node:last-child { border-bottom: none; }
.tree-node:hover { background: rgba(201,162,39,0.05); }
.tree-node.selected { background: rgba(201,162,39,0.1); }

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
.node-desc { color: #8a7355; font-size: 0.93rem; }

/* ===== Detail panel ===== */
.detail-empty {
  padding: 2rem 1rem;
  text-align: center;
}
.detail-empty-text {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #4a3820;
  font-size: 0.95rem;
}

.detail-panel {
  padding: 1.25rem 1.25rem 1.5rem;
}

.detail-header {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin-bottom: 0.4rem;
}

.detail-name {
  font-family: 'Cinzel', serif;
  font-size: 1.1rem;
  font-weight: 700;
  color: #c9a227;
}

.detail-type-badge {
  font-family: 'Crimson Text', serif;
  font-size: 0.78rem;
  color: #7a6115;
  border: 1px solid #3d2e10;
  border-radius: 3px;
  padding: 0.05rem 0.4rem;
  background: #1a1109;
}

.detail-desc {
  font-family: 'Crimson Text', serif;
  font-size: 0.95rem;
  color: #8a7355;
  font-style: italic;
  margin-bottom: 0.75rem;
  line-height: 1.5;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin-bottom: 0.25rem;
}

.detail-meta-row {
  display: flex;
  gap: 0.5rem;
  font-family: 'Crimson Text', serif;
  font-size: 0.88rem;
}

.meta-key {
  color: #5a4530;
  min-width: 52px;
}

.meta-val { color: #8a7355; }

.meta-val-link {
  color: #7a6115;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.meta-val-link:hover { color: #c9a227; }

.detail-divider {
  height: 1px;
  background: #2a1e08;
  margin: 0.75rem 0;
}

/* ===== Properties ===== */
.detail-props {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.prop-line {
  font-family: 'Crimson Text', serif;
  font-size: 0.9rem;
  line-height: 1.5;
}

.prop-section {
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #5a4530;
  text-transform: uppercase;
  display: block;
  margin-top: 0.35rem;
}

.prop-key { color: #7a6115; }
.prop-sep { color: #4a3820; }
.prop-val { color: #c8b67a; }
</style>
