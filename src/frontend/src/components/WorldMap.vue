<template>
  <Teleport to="body">
    <div v-if="visible" class="map-overlay" @click.self="$emit('close')">
      <div class="map-dialog" @contextmenu.prevent>
        <!-- Header -->
        <div class="map-header">
          <span class="map-title">World Map</span>
          <span class="map-legend">
            <span class="legend-dot dot-location"></span>Location
            <span class="legend-dot dot-pc"></span>PC
            <span class="legend-dot dot-npc"></span>NPC
            <span class="legend-dot dot-item"></span>Item
          </span>
          <button class="map-close-btn" @click="$emit('close')" title="Close (Esc)">✕</button>
        </div>

        <!-- Canvas -->
        <canvas
          ref="canvasEl"
          class="map-canvas"
          @mousedown="onMouseDown"
          @mousemove="onMouseMove"
          @mouseup="onMouseUp"
          @mouseleave="onMouseLeave"
          @wheel.prevent="onWheel"
          @contextmenu.prevent="onRightClick"
        ></canvas>

        <!-- Hover tooltip -->
        <div
          v-if="tooltip.node"
          class="map-tooltip"
          :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
        >
          <span class="tt-name">{{ tooltip.node.name }}</span>
          <span class="tt-type">{{ tooltip.node.type }}</span>
          <span v-if="tooltip.node.description" class="tt-desc">{{ tooltip.node.description }}</span>
        </div>

        <!-- Right-click context menu -->
        <div
          v-if="ctxMenu.visible"
          class="ctx-menu"
          :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
          @mouseleave="ctxMenu.visible = false"
        >
          <button class="ctx-item" @click="centerOnPlayer">Center on Player</button>
          <button class="ctx-item" @click="resetView">Reset View</button>
          <button class="ctx-item" @click="zoomIn">Zoom In</button>
          <button class="ctx-item" @click="zoomOut">Zoom Out</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useCampaignStore } from '../stores/campaign'

const props = defineProps({
  visible: { type: Boolean, default: false },
  campaignId: { type: String, required: true },
})
const emit = defineEmits(['close'])

const store = useCampaignStore()

function onWindowKeydown(event) {
  if (!props.visible) return
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopImmediatePropagation()
    emit('close')
  }
}

const canvasEl = ref(null)

// Pan / zoom state
const pan = ref({ x: 0, y: 0 })
const zoom = ref(1)
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0, panX: 0, panY: 0 })

// Map data
const nodes = ref([])
const playerNode = ref(null)

// Context menu
const ctxMenu = ref({ visible: false, x: 0, y: 0 })

// Hover tooltip
const tooltip = ref({ node: null, x: 0, y: 0 })

// Type → render config
const TYPE_CONFIG = {
  system:    { color: '#444', radius: 3, show: false },
  planet:    { color: '#5a4530', radius: 4, show: false },
  continent: { color: '#5a4530', radius: 4, show: false },
  region:    { color: '#7a6115', radius: 5, show: true },
  town:      { color: '#c9a227', radius: 6, show: true },
  city:      { color: '#c9a227', radius: 7, show: true },
  inn:       { color: '#e8d5b7', radius: 5, show: true },
  room:      { color: '#8a7355', radius: 4, show: true },
  dungeon:   { color: '#8a4530', radius: 6, show: true },
  party:     { color: '#4ade80', radius: 4, show: false },
  PC:        { color: '#4ade80', radius: 6, show: true },
  NPC:       { color: '#93c5fd', radius: 5, show: true },
  monster:   { color: '#f87171', radius: 5, show: true },
  item:      { color: '#fde68a', radius: 3, show: true },
  _default:  { color: '#8a7355', radius: 3, show: true },
}

function typeConfig(type) {
  return TYPE_CONFIG[type] || TYPE_CONFIG._default
}

// Spacing radius per type for the tree layout.
// When all siblings are at [0,0,0] relative to their parent, we spread them
// in a circle of this radius (world units = feet) around the parent.
const LAYOUT_RADIUS = {
  system: 2000, planet: 1200, continent: 800, region: 400,
  town: 200, city: 250, inn: 100, dungeon: 120,
  room: 50, party: 25, _default: 30,
}

function applyTreeLayout(rawNodes) {
  const byId = {}
  const childrenOf = {}
  rawNodes.forEach(n => {
    byId[n.id] = { ...n }
    childrenOf[n.id] = []
  })
  rawNodes.forEach(n => {
    if (n.parent != null && childrenOf[n.parent]) {
      childrenOf[n.parent].push(n.id)
    }
  })

  const laid = {}  // id -> { x, y }

  function layout(id, px, py) {
    laid[id] = { x: px, y: py }
    const kids = childrenOf[id] || []
    if (kids.length === 0) return

    const parentType = byId[id]?.type || '_default'
    const radius = LAYOUT_RADIUS[parentType] || LAYOUT_RADIUS._default

    // If ALL children have zero relative offset, spread in a circle.
    // If some have real offsets, honour them as-is (relative to parent layout pos).
    const allZero = kids.every(kidId => {
      const k = byId[kidId]
      return k && Math.abs(k.x) < 0.1 && Math.abs(k.y) < 0.1
    })

    kids.forEach((kidId, i) => {
      const kid = byId[kidId]
      if (allZero) {
        const angle = (i / kids.length) * Math.PI * 2 - Math.PI / 2
        layout(kidId, px + Math.cos(angle) * radius, py + Math.sin(angle) * radius)
      } else {
        layout(kidId, px + kid.x, py + kid.y)
      }
    })
  }

  // Find roots: nodes whose parent is absent from the set
  rawNodes
    .filter(n => n.parent == null || !byId[n.parent])
    .forEach(r => layout(r.id, 0, 0))

  // Return nodes with layout coordinates substituted for x/y
  return rawNodes.map(n => ({
    ...n,
    x: laid[n.id]?.x ?? n.x,
    y: laid[n.id]?.y ?? n.y,
  }))
}

async function loadMap() {
  try {
    const res = await fetch(`/api/campaigns/${props.campaignId}/map`, { credentials: 'include' })
    if (!res.ok) return
    const data = await res.json()
    nodes.value = applyTreeLayout(data.nodes || [])
    playerNode.value = nodes.value.find(n => n.is_player) || null
    nextTick(() => {
      initCanvas()
      autoFit()
    })
  } catch (e) {
    // ignore
  }
}

function worldToCanvas(wx, wy) {
  const canvas = canvasEl.value
  if (!canvas) return { cx: 0, cy: 0 }
  const cx = canvas.width / 2 + pan.value.x + wx * zoom.value
  const cy = canvas.height / 2 + pan.value.y - wy * zoom.value  // y flipped: up = +y
  return { cx, cy }
}

// Build a fast lookup of explored coords from the store
function buildExploredSet() {
  const s = new Set()
  for (const pair of store.exploredCoords) {
    s.add(`${pair[0]},${pair[1]}`)
  }
  return s
}

function drawFogOfWar(ctx, canvas, exploredSet) {
  // Fill entire canvas with dark fog first
  ctx.fillStyle = 'rgba(0, 0, 0, 0.72)'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  if (exploredSet.size === 0) return

  // For each explored coordinate punch a clear hole
  const tileSize = Math.max(4, 5 * zoom.value)  // 5 ft tile in canvas pixels
  ctx.globalCompositeOperation = 'destination-out'
  for (const key of exploredSet) {
    const [wx, wy] = key.split(',').map(Number)
    const { cx, cy } = worldToCanvas(wx, wy)
    ctx.fillStyle = 'rgba(0, 0, 0, 1)'
    ctx.fillRect(cx - tileSize / 2, cy - tileSize / 2, tileSize, tileSize)
  }
  ctx.globalCompositeOperation = 'source-over'
}

function draw() {
  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Background
  ctx.fillStyle = '#0a0806'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  // Grid (50ft = one square)
  drawGrid(ctx, canvas)

  const visibleNodes = nodes.value.filter(n => typeConfig(n.type).show)

  // Draw edges (parent → child) for location types
  ctx.strokeStyle = 'rgba(61,46,16,0.5)'
  ctx.lineWidth = 1
  for (const n of visibleNodes) {
    if (n.parent == null) continue
    const parent = visibleNodes.find(p => p.id === n.parent)
    if (!parent) continue
    const from = worldToCanvas(parent.x, parent.y)
    const to = worldToCanvas(n.x, n.y)
    const dx = to.cx - from.cx
    const dy = to.cy - from.cy
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) continue
    ctx.beginPath()
    ctx.moveTo(from.cx, from.cy)
    ctx.lineTo(to.cx, to.cy)
    ctx.stroke()
  }

  // Draw nodes
  for (const n of visibleNodes) {
    const cfg = typeConfig(n.type)
    const { cx, cy } = worldToCanvas(n.x, n.y)
    const r = Math.max(2, cfg.radius * Math.sqrt(zoom.value))

    if (n.is_player) {
      // Glow ring for the player
      ctx.beginPath()
      ctx.arc(cx, cy, r + 4, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(201,162,39,0.5)'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.fillStyle = n.is_player ? '#c9a227' : cfg.color
    ctx.fill()
  }

  // Fog-of-war layer: dark except explored tiles
  drawFogOfWar(ctx, canvas, buildExploredSet())
}

function drawGrid(ctx, canvas) {
  const gridFeet = 50  // 1 square = 50 feet
  const step = gridFeet * zoom.value
  if (step < 8) return  // skip grid when too zoomed out

  ctx.strokeStyle = 'rgba(61,46,16,0.25)'
  ctx.lineWidth = 0.5

  const originX = canvas.width / 2 + pan.value.x
  const originY = canvas.height / 2 + pan.value.y

  // Vertical lines
  const startX = ((originX % step) + step) % step
  for (let x = startX; x < canvas.width; x += step) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, canvas.height)
    ctx.stroke()
  }

  // Horizontal lines
  const startY = ((originY % step) + step) % step
  for (let y = startY; y < canvas.height; y += step) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(canvas.width, y)
    ctx.stroke()
  }
}

function initCanvas() {
  const canvas = canvasEl.value
  if (!canvas) return
  // Use the canvas's own CSS layout size (it fills flex parent)
  const rect = canvas.getBoundingClientRect()
  canvas.width = rect.width || canvas.offsetWidth || 800
  canvas.height = rect.height || canvas.offsetHeight || 500
  draw()
}

function autoFit() {
  const canvas = canvasEl.value
  if (!canvas) return
  const visible = nodes.value.filter(n => typeConfig(n.type).show)
  if (visible.length === 0) {
    pan.value = { x: 0, y: 0 }
    zoom.value = 10
    draw()
    return
  }
  // Compute world bounding box of visible nodes
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of visible) {
    if (n.x < minX) minX = n.x
    if (n.x > maxX) maxX = n.x
    if (n.y < minY) minY = n.y
    if (n.y > maxY) maxY = n.y
  }
  const worldW = maxX - minX || 1
  const worldH = maxY - minY || 1
  const padding = 80 // pixels
  const fitZoom = Math.min(
    (canvas.width - padding * 2) / worldW,
    (canvas.height - padding * 2) / worldH,
    80   // cap zoom so small worlds don't become 1 giant blob
  )
  zoom.value = Math.max(0.05, fitZoom)
  // Center the bounding box
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  pan.value.x = -cx * zoom.value
  pan.value.y = cy * zoom.value
  draw()
}

// --- Interaction ---

function onMouseDown(e) {
  if (e.button !== 0) return
  ctxMenu.value.visible = false
  dragging.value = true
  dragStart.value = { x: e.clientX, y: e.clientY, panX: pan.value.x, panY: pan.value.y }
}

function onMouseMove(e) {
  if (dragging.value) {
    pan.value.x = dragStart.value.panX + (e.clientX - dragStart.value.x)
    pan.value.y = dragStart.value.panY + (e.clientY - dragStart.value.y)
    tooltip.value.node = null
    draw()
    return
  }

  // Hover: find nearest visible node within hit radius
  const canvas = canvasEl.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top

  const HIT_RADIUS = 14  // px
  let closest = null
  let closestDist = Infinity

  for (const n of nodes.value) {
    if (!typeConfig(n.type).show) continue
    const { cx, cy } = worldToCanvas(n.x, n.y)
    const d = Math.hypot(cx - mx, cy - my)
    if (d < HIT_RADIUS && d < closestDist) {
      closestDist = d
      closest = n
    }
  }

  if (closest) {
    // Offset tooltip so it doesn't sit under the cursor
    tooltip.value = { node: closest, x: mx + 14, y: my - 10 }
  } else {
    tooltip.value.node = null
  }
}

function onMouseUp() {
  dragging.value = false
}

function onMouseLeave() {
  dragging.value = false
  tooltip.value.node = null
}

function onWheel(e) {
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
  const canvas = canvasEl.value
  if (!canvas) return

  // Zoom toward mouse cursor
  const rect = canvas.getBoundingClientRect()
  const mx = e.clientX - rect.left - canvas.width / 2
  const my = e.clientY - rect.top - canvas.height / 2

  pan.value.x = mx + (pan.value.x - mx) * factor
  pan.value.y = my + (pan.value.y - my) * factor
  zoom.value = Math.min(20, Math.max(0.05, zoom.value * factor))
  draw()
}

function onRightClick(e) {
  const rect = canvasEl.value?.getBoundingClientRect()
  if (!rect) return
  ctxMenu.value = {
    visible: true,
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
}

// --- Controls ---

function centerOnPlayer() {
  ctxMenu.value.visible = false
  const p = playerNode.value
  if (!p) return
  // Keep current zoom but re-center on player world coords
  pan.value.x = -p.x * zoom.value
  pan.value.y = p.y * zoom.value
  draw()
}

function resetView() {
  ctxMenu.value.visible = false
  autoFit()
}

function zoomIn() {
  ctxMenu.value.visible = false
  zoom.value = Math.min(20, zoom.value * 1.5)
  draw()
}

function zoomOut() {
  ctxMenu.value.visible = false
  zoom.value = Math.max(0.05, zoom.value / 1.5)
  draw()
}

function onResize() {
  const canvas = canvasEl.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  canvas.width = rect.width || canvas.offsetWidth || 800
  canvas.height = rect.height || canvas.offsetHeight || 500
  draw()
}

watch(() => props.visible, (val) => {
  if (val) {
    nextTick(() => {
      loadMap()
    })
  }
})

// Redraw when fog-of-war explored set changes
watch(() => store.exploredCoords, () => {
  if (props.visible) nextTick(() => draw())
}, { deep: true })

// When new tiles arrive via WebSocket, merge them into the node list and redraw.
// New objects arrive as raw world Object dicts; we normalise them into the same
// shape used by nodes (id, parent, type, name, x, y from location).
watch(() => store.worldTileObjects, (tileObjs) => {
  if (!props.visible || !tileObjs || tileObjs.length === 0) return
  const existingIds = new Set(nodes.value.map(n => n.id))
  const toAdd = []
  for (const obj of tileObjs) {
    if (existingIds.has(obj.id)) continue
    const loc = obj.location || {}
    toAdd.push({
      id: obj.id,
      parent: obj.parent ?? null,
      type: obj.type || 'ground',
      name: obj.name || obj.type || 'Ground',
      description: obj.description || null,
      x: loc.x ?? 0,
      y: loc.y ?? 0,
      is_player: false,
    })
    existingIds.add(obj.id)
  }
  if (toAdd.length > 0) {
    nodes.value = nodes.value.concat(toAdd)
    nextTick(() => draw())
  }
}, { deep: true })

onMounted(() => {
  window.addEventListener('resize', onResize)
  window.addEventListener('keydown', onWindowKeydown)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('keydown', onWindowKeydown)
})
</script>

<style scoped>
.map-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
}

.map-dialog {
  position: relative;
  width: min(90vw, 1100px);
  height: min(85vh, 700px);
  display: flex;
  flex-direction: column;
  background: #0a0806;
  border: 1px solid #3d2e10;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 0 60px rgba(0, 0, 0, 0.8);
}

.map-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.5rem 1rem;
  background: #110d05;
  border-bottom: 1px solid #3d2e10;
  flex-shrink: 0;
}

.map-title {
  font-family: 'Cinzel', serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: #c9a227;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.map-legend {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: 'Crimson Text', serif;
  font-size: 0.78rem;
  color: #8a7355;
  margin-left: 0.5rem;
}

.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-left: 0.5rem;
}
.dot-location { background: #c9a227; }
.dot-pc       { background: #4ade80; }
.dot-npc      { background: #93c5fd; }
.dot-item     { background: #fde68a; }

.map-close-btn {
  margin-left: auto;
  background: transparent;
  border: 1px solid #3d2e10;
  color: #8a7355;
  cursor: pointer;
  font-size: 0.75rem;
  width: 24px;
  height: 24px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s, border-color 0.15s;
}
.map-close-btn:hover {
  color: #c9a227;
  border-color: #c9a227;
}

.map-canvas {
  flex: 1;
  display: block;
  cursor: grab;
  min-height: 0;
}
.map-canvas:active {
  cursor: grabbing;
}

/* Right-click context menu */
.ctx-menu {
  position: absolute;
  background: #110d05;
  border: 1px solid #3d2e10;
  border-radius: 4px;
  padding: 0.25rem 0;
  min-width: 160px;
  z-index: 10;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
}

.ctx-item {
  display: block;
  width: 100%;
  text-align: left;
  background: transparent;
  border: none;
  padding: 0.4rem 0.9rem;
  font-family: 'Crimson Text', serif;
  font-size: 0.9rem;
  color: #e8d5b7;
  cursor: pointer;
  transition: background 0.1s;
}
.ctx-item:hover {
  background: rgba(201, 162, 39, 0.12);
  color: #c9a227;
}

/* Hover tooltip */
.map-tooltip {
  position: absolute;
  pointer-events: none;
  background: #110d05;
  border: 1px solid #3d2e10;
  border-radius: 4px;
  padding: 0.35rem 0.6rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  max-width: 220px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6);
  z-index: 20;
}

.tt-name {
  font-family: 'Cinzel', serif;
  font-size: 0.78rem;
  font-weight: 600;
  color: #c9a227;
  white-space: nowrap;
}

.tt-type {
  font-family: 'Crimson Text', serif;
  font-size: 0.72rem;
  color: #8a7355;
  text-transform: capitalize;
  font-style: italic;
}

.tt-desc {
  font-family: 'Crimson Text', serif;
  font-size: 0.8rem;
  color: #e8d5b7;
  line-height: 1.35;
  white-space: normal;
}
</style>
