<template>
  <Teleport to="body">
    <div v-if="visible" class="map-overlay" @click.self="$emit('close')">
      <div class="map-dialog" @contextmenu.prevent>
        <!-- Header -->
        <div class="map-header">
          <span class="map-title">World Map</span>
          <span class="map-legend">
            <span class="legend-swatch" style="background:#6b4a20"></span>Ground/Road
            <span class="legend-swatch" style="background:#c87533"></span>Building
            <span class="legend-swatch" style="background:#3cb371"></span>Inn/Pub
            <span class="legend-swatch" style="background:#2d7a2d"></span>Forest
            <span class="legend-swatch" style="background:#1e6be0"></span>Water
            <span class="legend-swatch" style="background:#c9a227"></span>You
            <span class="legend-swatch" style="background:#93c5fd"></span>NPC
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

function onWindowKeydown(e) {
  if (!props.visible) return
  if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); emit('close') }
}

const canvasEl = ref(null)
const pan = ref({ x: 0, y: 0 })
const zoom = ref(4)
const dragging = ref(false)
const dragStart = ref({ x: 0, y: 0, panX: 0, panY: 0 })
const ctxMenu = ref({ visible: false, x: 0, y: 0 })
const tooltip = ref({ node: null, x: 0, y: 0 })

// Data from the server
const hierarchyNodes = ref([])  // abstract container objects (tree-layouted)
const tileNodes = ref([])       // concrete tile/entity objects in the local container
const playerNode = ref(null)
const localContainerId = ref(null)
const exploredSet = ref(new Set()) // "wx,wy" strings of explored world coords

// ---------------------------------------------------------------------------
// Tile color mapping
// ---------------------------------------------------------------------------
const TILE_COLORS = {
  brown:      '#6b4a20',
  orange:     '#c87533',
  green:      '#3cb371',
  dark_green: '#2d7a2d',
  blue:       '#1e6be0',
}

const TYPE_TO_TILE_COLOR = {
  // brown – ground/traversable
  ground: 'brown', floor: 'brown', road: 'brown', wall: 'brown',
  door: 'brown', entrance: 'brown', path: 'brown', plaza: 'brown',
  courtyard: 'brown', forum: 'brown', cobblestone: 'brown',
  // green – inn/pub
  inn: 'green', tavern: 'green', pub: 'green',
  // dark_green – forest/vegetation
  forest: 'dark_green', park: 'dark_green', tree: 'dark_green', vegetation: 'dark_green',
  // blue – water
  water: 'blue', river: 'blue', ocean: 'blue', lake: 'blue', swamp: 'blue', pond: 'blue',
  // orange – buildings/stores
  building: 'orange', store: 'orange', general_store: 'orange',
  magic_shop: 'orange', smithy: 'orange', market: 'orange',
  black_market: 'orange', festhall: 'orange', temple: 'orange',
  manor: 'orange', academy: 'orange', prison: 'orange',
  dungeon: 'orange', cave: 'orange', ruin: 'orange', room: 'orange',
  container: 'orange', chest: 'orange',
}

function tileColorHex(node) {
  const tc = node.tile_color || node.properties?.tile_color || TYPE_TO_TILE_COLOR[node.type]
  return TILE_COLORS[tc] || '#6b4a20'
}

// Abstract container types drawn as circles in the hierarchy tree
const ABSTRACT_TYPES = new Set([
  'system', 'planet', 'continent', 'region', 'town', 'city',
  'party', 'dungeon', 'cave', 'library_fortress', 'citadel',
  'military_outpost', 'forest', 'mountain_range', 'swamp', 'island',
  'trade_road', 'manor', 'academy', 'festhall', 'tavern', 'general_store',
  'magic_shop', 'market', 'black_market', 'temple', 'prison', 'smithy',
  'inn', 'room',
])

const ABSTRACT_CONFIG = {
  system:    { color: '#333',    radius: 3,  show: false },
  planet:    { color: '#5a4530', radius: 4,  show: false },
  continent: { color: '#5a4530', radius: 4,  show: false },
  region:    { color: '#7a6115', radius: 5,  show: true  },
  town:      { color: '#c9a227', radius: 6,  show: true  },
  city:      { color: '#c9a227', radius: 7,  show: true  },
  inn:       { color: '#3cb371', radius: 5,  show: true  },
  tavern:    { color: '#3cb371', radius: 5,  show: true  },
  dungeon:   { color: '#8a4530', radius: 5,  show: true  },
  party:     { color: '#4ade80', radius: 4,  show: false },
  _default:  { color: '#8a7355', radius: 3,  show: true  },
}

function absCfg(type) { return ABSTRACT_CONFIG[type] || ABSTRACT_CONFIG._default }

// Entity types always drawn on top as circles
const ENTITY_TYPES = new Set(['PC', 'NPC', 'monster', 'item'])
const ENTITY_CONFIG = {
  PC:      { color: '#4ade80', radius: 5 },
  NPC:     { color: '#93c5fd', radius: 4 },
  monster: { color: '#f87171', radius: 4 },
  item:    { color: '#fde68a', radius: 3 },
  _default:{ color: '#aaa',   radius: 3 },
}
function entCfg(type) { return ENTITY_CONFIG[type] || ENTITY_CONFIG._default }

// ---------------------------------------------------------------------------
// Tree layout for hierarchy nodes
// ---------------------------------------------------------------------------
const LAYOUT_RADIUS = {
  system: 2000, planet: 1200, continent: 800, region: 400,
  town: 200, city: 250, inn: 100, dungeon: 120, room: 50,
  party: 25, _default: 30,
}

function applyTreeLayout(nodes) {
  const byId = {}
  const childrenOf = {}
  nodes.forEach(n => { byId[n.id] = { ...n }; childrenOf[n.id] = [] })
  nodes.forEach(n => {
    if (n.parent != null && childrenOf[n.parent]) childrenOf[n.parent].push(n.id)
  })
  const laid = {}
  function layout(id, px, py) {
    laid[id] = { x: px, y: py }
    const kids = childrenOf[id] || []
    if (!kids.length) return
    const r = LAYOUT_RADIUS[byId[id]?.type] || LAYOUT_RADIUS._default
    const allZero = kids.every(k => byId[k] && Math.abs(byId[k].x) < 0.1 && Math.abs(byId[k].y) < 0.1)
    kids.forEach((kid, i) => {
      if (allZero) {
        const a = (i / kids.length) * Math.PI * 2 - Math.PI / 2
        layout(kid, px + Math.cos(a) * r, py + Math.sin(a) * r)
      } else {
        layout(kid, px + byId[kid].x, py + byId[kid].y)
      }
    })
  }
  nodes.filter(n => n.parent == null || !byId[n.parent]).forEach(r => layout(r.id, 0, 0))
  return nodes.map(n => ({ ...n, x: laid[n.id]?.x ?? n.x, y: laid[n.id]?.y ?? n.y }))
}

// ---------------------------------------------------------------------------
// Map loading
// ---------------------------------------------------------------------------
async function loadMap() {
  try {
    const res = await fetch(`/api/campaigns/${props.campaignId}/map`, { credentials: 'include' })
    if (!res.ok) return
    const data = await res.json()

    // Hierarchy nodes — apply tree layout
    const rawH = (data.hierarchy || []).filter(n => absCfg(n.type).show)
    hierarchyNodes.value = applyTreeLayout(rawH)

    // Tile + entity objects in the local container — use their raw local coords
    tileNodes.value = data.tiles || []

    localContainerId.value = data.local_container_id ?? null
    playerNode.value = tileNodes.value.find(n => n.is_player) || null

    // Seed explored set from the map endpoint
    if (Array.isArray(data.explored) && data.explored.length > 0) {
      const s = new Set()
      for (const pair of data.explored) s.add(`${pair[0]},${pair[1]}`)
      exploredSet.value = s
      // Also sync to the store so WS updates keep working
      store.exploredCoords = data.explored
    } else {
      // No explored coords yet — reveal everything so the player can see something
      exploredSet.value = new Set()
    }

    nextTick(() => { initCanvas(); autoFit() })
  } catch (e) {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// Coordinate transform  (world → canvas)
// ---------------------------------------------------------------------------
function w2c(wx, wy) {
  const canvas = canvasEl.value
  if (!canvas) return { cx: 0, cy: 0 }
  return {
    cx: canvas.width  / 2 + pan.value.x + wx * zoom.value,
    cy: canvas.height / 2 + pan.value.y - wy * zoom.value,  // y-up
  }
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------
function draw() {
  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Black background — unseen areas
  ctx.fillStyle = '#000'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  drawGrid(ctx, canvas)

  const noTiles = tileNodes.value.length === 0
  const noExplored = exploredSet.value.size === 0

  // --- TILE LAYER: concrete floor/wall/door/building objects ---
  if (tileNodes.value.length > 0) {
    const ts = Math.max(3, 5 * zoom.value)  // 5 ft tile in pixels
    for (const n of tileNodes.value) {
      if (ENTITY_TYPES.has(n.type)) continue   // entities drawn separately
      const { cx, cy } = w2c(n.x, n.y)
      if (cx < -ts || cx > canvas.width + ts || cy < -ts || cy > canvas.height + ts) continue
      ctx.fillStyle = tileColorHex(n)
      ctx.fillRect(cx - ts / 2, cy - ts / 2, ts, ts)
    }
  }

  // --- HIERARCHY LAYER: abstract nodes as circles ---
  ctx.strokeStyle = 'rgba(61,46,16,0.5)'
  ctx.lineWidth = 1
  for (const n of hierarchyNodes.value) {
    const cfg = absCfg(n.type)
    if (!cfg.show) continue
    if (n.parent == null) continue
    const parent = hierarchyNodes.value.find(p => p.id === n.parent)
    if (!parent || !absCfg(parent.type).show) continue
    const from = w2c(parent.x, parent.y)
    const to   = w2c(n.x, n.y)
    if (Math.abs(to.cx - from.cx) < 0.5 && Math.abs(to.cy - from.cy) < 0.5) continue
    ctx.beginPath(); ctx.moveTo(from.cx, from.cy); ctx.lineTo(to.cx, to.cy); ctx.stroke()
  }
  for (const n of hierarchyNodes.value) {
    const cfg = absCfg(n.type)
    if (!cfg.show) continue
    const { cx, cy } = w2c(n.x, n.y)
    const r = Math.max(2, cfg.radius * Math.sqrt(zoom.value))
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.fillStyle = cfg.color; ctx.fill()
  }

  // --- ENTITY LAYER: PC / NPC / item circles on top ---
  for (const n of tileNodes.value) {
    if (!ENTITY_TYPES.has(n.type)) continue
    const cfg = entCfg(n.type)
    const { cx, cy } = w2c(n.x, n.y)
    const r = Math.max(3, cfg.radius * Math.sqrt(zoom.value))
    if (n.is_player) {
      ctx.beginPath(); ctx.arc(cx, cy, r + 5, 0, Math.PI * 2)
      ctx.strokeStyle = 'rgba(201,162,39,0.6)'; ctx.lineWidth = 2; ctx.stroke()
    }
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.fillStyle = n.is_player ? '#c9a227' : cfg.color; ctx.fill()
  }

  // --- FOG OF WAR ---
  // Only apply fog when we have both tile data AND an explored set.
  // If explored is empty (new game / no movement yet), skip fog entirely
  // so the player can see tiles immediately.
  if (!noTiles && !noExplored) {
    drawFog(ctx, canvas)
  }
}

function drawFog(ctx, canvas) {
  // Build fog on an OFFSCREEN canvas so destination-out never erases
  // the tiles already drawn on the main canvas.
  const fog = document.createElement('canvas')
  fog.width  = canvas.width
  fog.height = canvas.height
  const fc = fog.getContext('2d')

  // Start fully opaque black (unexplored = dark)
  fc.fillStyle = '#000'
  fc.fillRect(0, 0, fog.width, fog.height)

  // Punch transparent holes for every explored coordinate
  const ts = Math.max(4, 5 * zoom.value)
  fc.globalCompositeOperation = 'destination-out'
  fc.fillStyle = 'rgba(0,0,0,1)'
  for (const key of exploredSet.value) {
    const [wx, wy] = key.split(',').map(Number)
    const { cx, cy } = w2c(wx, wy)
    fc.fillRect(cx - ts / 2, cy - ts / 2, ts, ts)
  }
  fc.globalCompositeOperation = 'source-over'

  // Composite fog layer onto main canvas — transparent holes reveal tiles,
  // opaque black covers unexplored areas.
  ctx.drawImage(fog, 0, 0)
}

function drawGrid(ctx, canvas) {
  const step = 50 * zoom.value
  if (step < 8) return
  ctx.strokeStyle = 'rgba(61,46,16,0.18)'
  ctx.lineWidth = 0.5
  const ox = canvas.width  / 2 + pan.value.x
  const oy = canvas.height / 2 + pan.value.y
  const sx = ((ox % step) + step) % step
  for (let x = sx; x < canvas.width;  x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke() }
  const sy = ((oy % step) + step) % step
  for (let y = sy; y < canvas.height; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke() }
}

function initCanvas() {
  const canvas = canvasEl.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  canvas.width  = rect.width  || canvas.offsetWidth  || 800
  canvas.height = rect.height || canvas.offsetHeight || 500
  draw()
}

function autoFit() {
  const canvas = canvasEl.value
  if (!canvas) return

  // If we have tile objects, center on the player tile / origin
  if (tileNodes.value.length > 0) {
    zoom.value = 12   // 12 px per foot → each 5-ft tile is 60 px
    const p = playerNode.value
    if (p) {
      pan.value.x = -(p.x * zoom.value)
      pan.value.y =  (p.y * zoom.value)
    } else {
      pan.value = { x: 0, y: 0 }
    }
    draw()
    return
  }

  // Fallback: fit the hierarchy tree
  const visible = hierarchyNodes.value
  if (!visible.length) { pan.value = { x: 0, y: 0 }; zoom.value = 10; draw(); return }
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of visible) {
    if (n.x < minX) minX = n.x; if (n.x > maxX) maxX = n.x
    if (n.y < minY) minY = n.y; if (n.y > maxY) maxY = n.y
  }
  const ww = maxX - minX || 1, wh = maxY - minY || 1
  const pad = 80
  zoom.value = Math.max(0.05, Math.min(80,
    Math.min((canvas.width - pad * 2) / ww, (canvas.height - pad * 2) / wh)
  ))
  pan.value.x = -((minX + maxX) / 2) * zoom.value
  pan.value.y =  ((minY + maxY) / 2) * zoom.value
  draw()
}

// ---------------------------------------------------------------------------
// Interaction
// ---------------------------------------------------------------------------
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
    draw(); return
  }
  const canvas = canvasEl.value; if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const mx = e.clientX - rect.left, my = e.clientY - rect.top

  // Hit-test tiles first (pixel-perfect bounding box)
  const ts = Math.max(4, 5 * zoom.value)
  let hit = null
  for (const n of [...tileNodes.value].reverse()) {
    const { cx, cy } = w2c(n.x, n.y)
    if (mx >= cx - ts/2 && mx <= cx + ts/2 && my >= cy - ts/2 && my <= cy + ts/2) { hit = n; break }
  }
  // Then hierarchy circles
  if (!hit) {
    for (const n of hierarchyNodes.value) {
      if (!absCfg(n.type).show) continue
      const { cx, cy } = w2c(n.x, n.y)
      if (Math.hypot(cx - mx, cy - my) < 14) { hit = n; break }
    }
  }
  tooltip.value = hit ? { node: hit, x: mx + 14, y: my - 10 } : { node: null, x: 0, y: 0 }
}

function onMouseUp()    { dragging.value = false }
function onMouseLeave() { dragging.value = false; tooltip.value.node = null }

function onWheel(e) {
  const f = e.deltaY < 0 ? 1.12 : 1 / 1.12
  const canvas = canvasEl.value; if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const mx = e.clientX - rect.left - canvas.width  / 2
  const my = e.clientY - rect.top  - canvas.height / 2
  pan.value.x = mx + (pan.value.x - mx) * f
  pan.value.y = my + (pan.value.y - my) * f
  zoom.value  = Math.min(40, Math.max(0.05, zoom.value * f))
  draw()
}

function onRightClick(e) {
  const rect = canvasEl.value?.getBoundingClientRect(); if (!rect) return
  ctxMenu.value = { visible: true, x: e.clientX - rect.left, y: e.clientY - rect.top }
}

function centerOnPlayer() {
  ctxMenu.value.visible = false
  const p = playerNode.value; if (!p) return
  pan.value.x = -(p.x * zoom.value); pan.value.y = (p.y * zoom.value); draw()
}
function resetView()  { ctxMenu.value.visible = false; autoFit() }
function zoomIn()     { ctxMenu.value.visible = false; zoom.value = Math.min(40, zoom.value * 1.5); draw() }
function zoomOut()    { ctxMenu.value.visible = false; zoom.value = Math.max(0.05, zoom.value / 1.5); draw() }
function onResize()   { initCanvas() }

// ---------------------------------------------------------------------------
// Reactivity
// ---------------------------------------------------------------------------
watch(() => props.visible, v => { if (v) nextTick(() => loadMap()) })

// WS explored update
watch(() => store.exploredCoords, coords => {
  if (!props.visible) return
  const s = new Set()
  for (const p of coords) s.add(`${p[0]},${p[1]}`)
  exploredSet.value = s
  nextTick(() => draw())
}, { deep: true })

// WS new tile objects — merge into tileNodes (use raw local coords)
watch(() => store.worldTileObjects, objs => {
  if (!props.visible || !objs?.length) return
  const ids = new Set(tileNodes.value.map(n => n.id))
  const toAdd = []
  for (const obj of objs) {
    if (ids.has(obj.id)) continue
    const loc = obj.location || {}
    const pr  = obj.properties || {}
    toAdd.push({
      id: obj.id, parent: obj.parent ?? null,
      type: obj.type || 'ground',
      name: obj.name || obj.type || 'Ground',
      description: obj.description || null,
      x: loc.x ?? 0, y: loc.y ?? 0,
      tile_color: pr.tile_color || null,
      properties: pr,
      is_player: false,
    })
    ids.add(obj.id)
  }
  if (toAdd.length) { tileNodes.value = tileNodes.value.concat(toAdd); nextTick(() => draw()) }
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
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.8);
  display: flex; align-items: center; justify-content: center;
  z-index: 300;
}
.map-dialog {
  position: relative;
  width: min(90vw, 1100px); height: min(85vh, 700px);
  display: flex; flex-direction: column;
  background: #000;
  border: 1px solid #3d2e10; border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 0 60px rgba(0,0,0,0.8);
}
.map-header {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.45rem 1rem;
  background: #110d05; border-bottom: 1px solid #3d2e10;
  flex-shrink: 0; flex-wrap: wrap;
}
.map-title {
  font-family: 'Cinzel', serif; font-size: 0.9rem; font-weight: 600;
  color: #c9a227; letter-spacing: 0.08em; text-transform: uppercase; flex-shrink: 0;
}
.map-legend {
  display: flex; align-items: center; gap: 0.35rem;
  font-family: 'Crimson Text', serif; font-size: 0.73rem; color: #8a7355;
  flex-wrap: wrap;
}
.legend-swatch {
  display: inline-block; width: 10px; height: 10px;
  border-radius: 2px; margin-left: 0.35rem; flex-shrink: 0;
}
.map-close-btn {
  margin-left: auto; background: transparent;
  border: 1px solid #3d2e10; color: #8a7355; cursor: pointer;
  font-size: 0.75rem; width: 24px; height: 24px; border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  transition: color 0.15s, border-color 0.15s;
}
.map-close-btn:hover { color: #c9a227; border-color: #c9a227; }
.map-canvas { flex: 1; display: block; cursor: grab; min-height: 0; }
.map-canvas:active { cursor: grabbing; }
.ctx-menu {
  position: absolute; background: #110d05;
  border: 1px solid #3d2e10; border-radius: 4px;
  padding: 0.25rem 0; min-width: 160px; z-index: 10;
  box-shadow: 0 4px 16px rgba(0,0,0,0.6);
}
.ctx-item {
  display: block; width: 100%; text-align: left;
  background: transparent; border: none; padding: 0.4rem 0.9rem;
  font-family: 'Crimson Text', serif; font-size: 0.9rem; color: #e8d5b7;
  cursor: pointer; transition: background 0.1s;
}
.ctx-item:hover { background: rgba(201,162,39,0.12); color: #c9a227; }
.map-tooltip {
  position: absolute; pointer-events: none;
  background: #110d05; border: 1px solid #3d2e10; border-radius: 4px;
  padding: 0.35rem 0.6rem; display: flex; flex-direction: column;
  gap: 0.15rem; max-width: 220px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.6); z-index: 20;
}
.tt-name { font-family: 'Cinzel', serif; font-size: 0.78rem; font-weight: 600; color: #c9a227; white-space: nowrap; }
.tt-type { font-family: 'Crimson Text', serif; font-size: 0.72rem; color: #8a7355; text-transform: capitalize; font-style: italic; }
.tt-desc { font-family: 'Crimson Text', serif; font-size: 0.8rem; color: #e8d5b7; line-height: 1.35; white-space: normal; }
</style>
