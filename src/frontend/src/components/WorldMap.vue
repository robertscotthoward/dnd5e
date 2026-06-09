<template>
  <Teleport to="body">
    <div v-if="visible" class="map-overlay" @click.self="$emit('close')">
      <div class="map-dialog" :style="dialogStyle" @contextmenu.prevent>
        <!-- Resize handles — one per edge/corner -->
        <div class="rs rs-n"  @mousedown.stop="startResize($event,'n')"></div>
        <div class="rs rs-s"  @mousedown.stop="startResize($event,'s')"></div>
        <div class="rs rs-e"  @mousedown.stop="startResize($event,'e')"></div>
        <div class="rs rs-w"  @mousedown.stop="startResize($event,'w')"></div>
        <div class="rs rs-ne" @mousedown.stop="startResize($event,'ne')"></div>
        <div class="rs rs-nw" @mousedown.stop="startResize($event,'nw')"></div>
        <div class="rs rs-se" @mousedown.stop="startResize($event,'se')"></div>
        <div class="rs rs-sw" @mousedown.stop="startResize($event,'sw')"></div>
        <!-- Header -->
        <div class="map-header">
          <span class="map-title">World Map</span>
          <span class="map-legend">
            <span class="legend-swatch" style="background:#5a3e18"></span>Ground
            <span class="legend-swatch" style="background:#8a6a40"></span>Floor
            <span class="legend-swatch" style="background:#9aa0a8"></span>Wall
            <span class="legend-swatch" style="background:#b07040"></span>Door
            <span class="legend-swatch" style="background:#c87533"></span>Room/Building
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
          <span v-if="dimsLabel(tooltip.node)" class="tt-dims">{{ dimsLabel(tooltip.node) }}</span>
          <span v-if="tooltip.node.description" class="tt-desc">{{ tooltip.node.description }}</span>
          <div v-if="tooltip.ancestry && tooltip.ancestry.length" class="tt-ancestry">
            <span
              v-for="(anc, i) in tooltip.ancestry"
              :key="i"
              class="tt-anc-item"
            >{{ anc.name }} <em>({{ anc.type }})</em><span v-if="anc.dims" class="tt-anc-dims"> {{ anc.dims }}</span></span>
          </div>
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
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
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
const tooltip = ref({ node: null, ancestry: [], x: 0, y: 0 })

// ---------------------------------------------------------------------------
// Resizable dialog
// ---------------------------------------------------------------------------
const LS_KEY = 'worldmap-size'
const MIN_W = 400, MIN_H = 300

function _loadSize() {
  try {
    const s = JSON.parse(localStorage.getItem(LS_KEY) || 'null')
    if (s && s.w > MIN_W && s.h > MIN_H) return s
  } catch {}
  return null
}

const dialogSize = ref(_loadSize())

const dialogStyle = computed(() => {
  if (!dialogSize.value) return {}
  return { width: dialogSize.value.w + 'px', height: dialogSize.value.h + 'px' }
})

const resizing = ref(null) // { dir, startX, startY, startW, startH, origRect }

function startResize(e, dir) {
  if (e.button !== 0) return
  const dialog = e.currentTarget.closest('.map-dialog')
  const rect = dialog.getBoundingClientRect()
  resizing.value = { dir, startX: e.clientX, startY: e.clientY,
                     startW: rect.width, startH: rect.height }
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup',   onResizeUp)
}

function onResizeMove(e) {
  if (!resizing.value) return
  const { dir, startX, startY, startW, startH } = resizing.value
  const dx = e.clientX - startX
  const dy = e.clientY - startY
  const maxW = window.innerWidth  * 0.95
  const maxH = window.innerHeight * 0.95

  let w = startW, h = startH
  if (dir.includes('e'))  w = Math.min(maxW, Math.max(MIN_W, startW + dx))
  if (dir.includes('w'))  w = Math.min(maxW, Math.max(MIN_W, startW - dx))
  if (dir.includes('s'))  h = Math.min(maxH, Math.max(MIN_H, startH + dy))
  if (dir.includes('n'))  h = Math.min(maxH, Math.max(MIN_H, startH - dy))

  dialogSize.value = { w, h }
}

function onResizeUp() {
  if (dialogSize.value) {
    localStorage.setItem(LS_KEY, JSON.stringify(dialogSize.value))
  }
  resizing.value = null
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup',   onResizeUp)
  nextTick(() => initCanvas())
}

// Data from the server
const hierarchyNodes = ref([])       // abstract container objects (tree-layouted, display-filtered)
const allHierarchyNodes = ref([])    // all hierarchy nodes including hidden ones — used for ancestry lookups
const tileNodes = ref([])            // concrete tile/entity objects in the local container
const playerNode = ref(null)
const localContainerId = ref(null)
const exploredSet = ref(new Set()) // "wx,wy" strings of explored world coords

// ---------------------------------------------------------------------------
// Tile color mapping — unique hex per type so wall ≠ floor ≠ ground
// ---------------------------------------------------------------------------

// Legacy named-color fallback for tiles that still carry tile_color:"brown" etc.
const TILE_COLORS = {
  brown:      '#6b4a20',
  orange:     '#c87533',
  green:      '#3cb371',
  dark_green: '#2d7a2d',
  blue:       '#1e6be0',
}

const TYPE_COLOR = {
  // ground/traversable — earthy browns, each channel ≥ 15 apart from its neighbors
  ground:     '#5a3e18',  // darkest bare dirt
  cobblestone:'#7a6a50',  // warm gray-tan
  floor:      '#8a6a40',  // lighter interior tan
  road:       '#9a7a50',  // worn path, lighter still
  path:       '#6e5230',  // dim trail
  wall:       '#9aa0a8',  // cool structural gray
  door:       '#b07040',  // amber-brown threshold
  entrance:   '#c08850',  // brighter than door
  plaza:      '#a08860',  // sandy paving
  courtyard:  '#7a6848',  // greenish-tan
  forum:      '#887058',  // mid-earth

  // inn / pub — greens
  inn:        '#3cb371',
  tavern:     '#2a9060',
  pub:        '#50c890',

  // forest / vegetation — dark greens
  forest:     '#2d7a2d',
  park:       '#3a8a3a',
  tree:       '#1e6020',
  vegetation: '#4a9040',

  // water — blues
  water:      '#1e6be0',
  river:      '#3080f0',
  ocean:      '#0a50c0',
  lake:       '#2870d0',
  swamp:      '#3a6848',
  pond:       '#4878b0',

  // buildings — each has its own character
  room:          '#c87533',  // base orange interior
  building:      '#b86020',  // darker brick
  store:         '#d48840',
  general_store: '#d48840',
  magic_shop:    '#9060c8',  // purple — magical
  smithy:        '#b04828',  // rust-red
  market:        '#d89050',  // sandy stall
  black_market:  '#503048',  // dark purple
  festhall:      '#c860a8',  // pink-magenta
  temple:        '#d4b870',  // pale gold-stone
  manor:         '#a07050',  // earthy estate
  academy:       '#7088b0',  // scholarly blue-gray
  prison:        '#484848',  // dark gray
  dungeon:       '#602020',  // deep blood red
  cave:          '#806050',  // rocky brown
  cave_entrance: '#806050',
  ruin:          '#706858',  // ashy rubble
  container:     '#c8a020',  // treasure gold
  chest:         '#c8a020',
}

const TILE_TYPES = new Set([
  'ground', 'floor', 'cobblestone', 'road', 'path', 'plaza', 'courtyard', 'forum',
  'wall', 'door', 'entrance',
])
const ENTITY_DIM_TYPES = new Set(['PC', 'NPC', 'monster', 'item'])

function dimsLabel(node) {
  if (ENTITY_DIM_TYPES.has(node.type)) return ''
  // Individual tiles are always one 5-ft grid cell
  if (TILE_TYPES.has(node.type)) return '5×5 ft'
  // Container/structure objects — use explicit size when set
  const s = node.size
  if (!s) return ''
  const [l, w, h] = Array.isArray(s) ? s : [s.length || 0, s.width || 0, s.height || 0]
  if (!l && !w && !h) return ''
  if (!h) return `${l}×${w} ft`
  return `${l}×${w}×${h} ft`
}

function tileColorHex(node) {
  // TYPE_COLOR wins — prevents legacy "tile_color: brown" on walls/floors from masking type-specific hues
  if (TYPE_COLOR[node.type]) return TYPE_COLOR[node.type]
  // Fallback: honour an explicit tile_color property for unknown types
  const override = node.tile_color || node.properties?.tile_color
  if (override && TILE_COLORS[override]) return TILE_COLORS[override]
  return '#6b4a20'
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

// Z-order priority for draw pass (lower number = drawn first = behind)
const TILE_Z = {
  // ground layer — paint first
  ground: 0, floor: 0, cobblestone: 0, path: 0, plaza: 0, courtyard: 0, forum: 0,
  // structural layer
  wall: 1, door: 1, entrance: 1, road: 1,
  // feature/building layer
  building: 2, store: 2, general_store: 2, magic_shop: 2, smithy: 2,
  market: 2, black_market: 2, festhall: 2, temple: 2, manor: 2,
  academy: 2, prison: 2, dungeon: 2, cave: 2, ruin: 2,
  inn: 2, tavern: 2, pub: 2,
  forest: 2, tree: 2, vegetation: 2, park: 2, water: 2, river: 2, ocean: 2,
  // furniture / loose items
  chest: 3, container: 3, item: 3,
  // entities
  NPC: 4, monster: 4,
  // player always on top
  PC: 5,
}
function tileZ(type) { return TILE_Z[type] ?? 2 }

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

    // Hierarchy nodes — keep full set for ancestry lookups; filter for display
    const rawH = data.hierarchy || []
    allHierarchyNodes.value = rawH
    hierarchyNodes.value = applyTreeLayout(rawH.filter(n => absCfg(n.type).show))

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

  // --- TILE + ENTITY LAYER: sorted by z so floors paint under walls under players ---
  const ts = Math.max(3, 5 * zoom.value)
  const sortedTiles = [...tileNodes.value].sort((a, b) => tileZ(a.type) - tileZ(b.type))
  for (const n of sortedTiles) {
    const { cx, cy } = w2c(n.x, n.y)
    if (cx < -ts * 2 || cx > canvas.width + ts * 2 || cy < -ts * 2 || cy > canvas.height + ts * 2) continue

    if (ENTITY_TYPES.has(n.type)) {
      const cfg = entCfg(n.type)
      const r = Math.max(3, cfg.radius * Math.sqrt(zoom.value))
      if (n.is_player) {
        ctx.beginPath(); ctx.arc(cx, cy, r + 5, 0, Math.PI * 2)
        ctx.strokeStyle = 'rgba(201,162,39,0.6)'; ctx.lineWidth = 2; ctx.stroke()
      }
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.fillStyle = n.is_player ? '#c9a227' : cfg.color; ctx.fill()
    } else {
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

  // Hit-test: iterate tiles sorted by z descending so highest-z (player/entity) wins
  const ts = Math.max(4, 5 * zoom.value)
  let hit = null
  const sortedDesc = [...tileNodes.value].sort((a, b) => tileZ(b.type) - tileZ(a.type))
  for (const n of sortedDesc) {
    const { cx, cy } = w2c(n.x, n.y)
    if (ENTITY_TYPES.has(n.type)) {
      const r = Math.max(3, entCfg(n.type).radius * Math.sqrt(zoom.value)) + 5
      if (Math.hypot(cx - mx, cy - my) <= r) { hit = n; break }
    } else {
      if (mx >= cx - ts/2 && mx <= cx + ts/2 && my >= cy - ts/2 && my <= cy + ts/2) { hit = n; break }
    }
  }
  // Then hierarchy circles
  if (!hit) {
    for (const n of hierarchyNodes.value) {
      if (!absCfg(n.type).show) continue
      const { cx, cy } = w2c(n.x, n.y)
      if (Math.hypot(cx - mx, cy - my) < 14) { hit = n; break }
    }
  }

  if (hit) {
    // Build ancestry chain: use unfiltered hierarchy + tiles so virtual nodes (party, etc.) resolve
    const allById = {}
    for (const n of allHierarchyNodes.value) allById[n.id] = n
    for (const n of tileNodes.value)         allById[n.id] = n
    const ancestry = []
    let pid = hit.parent
    while (pid != null && ancestry.length < 8) {
      const p = allById[pid]
      if (!p) break
      ancestry.push({ name: p.name || p.type, type: p.type, dims: dimsLabel(p) })
      pid = p.parent
    }
    tooltip.value = { node: hit, ancestry, x: mx + 14, y: my - 10 }
  } else {
    tooltip.value = { node: null, ancestry: [], x: 0, y: 0 }
  }
}

function onMouseUp()    { dragging.value = false }
function onMouseLeave() { dragging.value = false; tooltip.value = { node: null, ancestry: [], x: 0, y: 0 } }

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
      size: obj.size ?? [0, 0, 0],
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
  width: min(90vw, 1100px); height: min(85vh, 700px); /* overridden by inline style when resized */
  display: flex; flex-direction: column;
  background: #000;
  border: 1px solid #3d2e10; border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 0 60px rgba(0,0,0,0.8);
  user-select: none;
}

/* Resize handles */
.rs {
  position: absolute; z-index: 50;
}
.rs-n  { top: 0;    left: 6px;  right: 6px;  height: 6px; cursor: n-resize; }
.rs-s  { bottom: 0; left: 6px;  right: 6px;  height: 6px; cursor: s-resize; }
.rs-e  { right: 0;  top: 6px;   bottom: 6px; width: 6px;  cursor: e-resize; }
.rs-w  { left: 0;   top: 6px;   bottom: 6px; width: 6px;  cursor: w-resize; }
.rs-ne { top: 0;    right: 0;   width: 10px; height: 10px; cursor: ne-resize; }
.rs-nw { top: 0;    left: 0;    width: 10px; height: 10px; cursor: nw-resize; }
.rs-se { bottom: 0; right: 0;   width: 10px; height: 10px; cursor: se-resize; }
.rs-sw { bottom: 0; left: 0;    width: 10px; height: 10px; cursor: sw-resize; }
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
.tt-dims { font-family: 'Crimson Text', serif; font-size: 0.7rem; color: #7a6848; letter-spacing: 0.04em; }
.tt-desc { font-family: 'Crimson Text', serif; font-size: 0.8rem; color: #e8d5b7; line-height: 1.35; white-space: normal; }
.tt-ancestry {
  display: flex; flex-direction: column; gap: 0.1rem;
  border-top: 1px solid #2a1e08; margin-top: 0.3rem; padding-top: 0.3rem;
}
.tt-anc-item {
  font-family: 'Crimson Text', serif; font-size: 0.72rem; color: #5a4530;
  white-space: nowrap;
}
.tt-anc-item em { font-style: italic; color: #4a3820; }
.tt-anc-dims { color: #5a4830; font-size: 0.68rem; margin-left: 0.25rem; }
</style>
