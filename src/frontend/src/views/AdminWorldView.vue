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
        <div class="admin-header">
          <div class="admin-header-left">
            <h1 class="admin-title">{{ campaignId }}</h1>
            <p class="admin-subtitle">World object tree — right-click to create</p>
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
                @click="onNodeClick(node)"
                @contextmenu.prevent="onContextMenu($event, node)"
              >
                <span class="node-name">{{ node.name || '(unnamed)' }}</span>
                <span class="node-type"> ({{ node.type }})</span>
                <span class="node-desc" v-if="node.description"> — {{ node.description }}</span>
              </div>
            </div>
          </div>

          <!-- Detail column -->
          <div class="detail-col">
            <div v-if="!selectedNode" class="detail-empty dnd-panel">
              <span class="detail-empty-text">Select an item to view details</span>
            </div>
            <div v-else class="detail-panel dnd-panel">
              <div class="detail-header">
                <span class="detail-name">{{ selectedNode.name || '(unnamed)' }}</span>
                <span class="detail-type-badge">{{ selectedNode.type }}</span>
              </div>
              <p class="detail-desc" v-if="selectedNode.description">{{ selectedNode.description }}</p>
              <div class="detail-section">
                <div class="detail-meta-row">
                  <span class="meta-key">id</span>
                  <span class="meta-val">{{ selectedNode.id }}</span>
                </div>
                <div class="detail-meta-row" v-if="selectedNode.parent != null">
                  <span class="meta-key">parent</span>
                  <span class="meta-val meta-val-link" @click="selectById(selectedNode.parent)">
                    {{ parentName(selectedNode.parent) }} (#{{ selectedNode.parent }})
                  </span>
                </div>
              </div>
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

    <!-- Context menu (fixed, outside the scroll flow) -->
    <div
      v-if="ctxMenu.visible"
      class="ctx-menu"
      :style="{ top: ctxMenu.y + 'px', left: ctxMenu.x + 'px' }"
      @click.stop
    >
      <div
        class="ctx-item ctx-has-sub"
        @mouseenter="ctxSubmenuOpen = true"
      >
        <span>Create</span>
        <span class="ctx-arrow">▶</span>
        <div v-if="ctxSubmenuOpen && ctxChildTypes.length" class="ctx-sub">
          <div
            v-for="childType in ctxChildTypes"
            :key="childType"
            class="ctx-item"
            @click="openDialog(childType)"
          >{{ childType }}</div>
        </div>
        <div v-if="ctxSubmenuOpen && !ctxChildTypes.length" class="ctx-sub">
          <div class="ctx-item ctx-disabled">No child types defined</div>
        </div>
      </div>
      <div class="ctx-divider"></div>
      <div class="ctx-item ctx-danger" @click="openDeleteDialog">
        <span>✕ Delete</span>
      </div>
    </div>

    <!-- Create dialog -->
    <div v-if="createDialog.visible" class="modal-overlay" @click.self="closeDialog">
      <div
        class="create-modal dnd-panel"
        ref="dialogRef"
        tabindex="-1"
        @keydown="onDialogKey"
      >
        <h3 class="modal-title">
          Create <span class="modal-type">{{ createDialog.type }}</span>
        </h3>

        <div class="form-group">
          <label class="form-label">Name</label>
          <input class="form-input" v-model="createDialog.name" ref="nameInputRef" />
        </div>

        <div class="form-group">
          <label class="form-label">Description</label>
          <textarea class="form-textarea" v-model="createDialog.description" rows="2"></textarea>
        </div>

        <template v-for="field in typeFields(createDialog.type)" :key="field.key">
          <div class="form-group">
            <div v-if="field.type === 'abilities'" class="abilities-block">
              <div class="abilities-label-row">
                <span class="form-label">Abilities</span>
                <button type="button" class="reroll-btn" @click="createDialog.properties.abilities = rollAbilities()">
                  Re-roll
                </button>
              </div>
              <div class="abilities-grid">
                <div v-for="stat in ['str','dex','con','int','wis','chr']" :key="stat" class="ability-cell">
                  <div class="ability-label">{{ stat.toUpperCase() }}</div>
                  <div class="ability-value">{{ createDialog.properties.abilities?.[stat] ?? '—' }}</div>
                </div>
              </div>
            </div>
            <template v-else>
              <label class="form-label">{{ field.label }}</label>
              <select
                v-if="field.type === 'select'"
                class="form-input"
                v-model="createDialog.properties[field.key]"
              >
                <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
              </select>
              <input
                v-else-if="field.type === 'number'"
                type="number"
                class="form-input"
                v-model.number="createDialog.properties[field.key]"
              />
              <input
                v-else
                class="form-input"
                v-model="createDialog.properties[field.key]"
              />
            </template>
          </div>
        </template>

        <div v-if="createError" class="error-banner" style="margin-top:0.5rem;margin-bottom:0">
          {{ createError }}
        </div>

        <div class="modal-actions">
          <button class="dnd-button-ghost" @click="closeDialog">Cancel</button>
          <button class="dnd-button" @click="saveObject" :disabled="saving">
            {{ saving ? 'Saving…' : 'Create' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation dialog -->
    <div v-if="deleteDialog.visible" class="modal-overlay" @click.self="closeDeleteDialog">
      <div
        class="create-modal dnd-panel"
        tabindex="-1"
        @keydown.esc="closeDeleteDialog"
      >
        <h3 class="modal-title">Delete <span class="modal-type">{{ deleteDialog.node?.name }}</span>?</h3>
        <p class="delete-warning">
          This will permanently delete this item and all its children. This cannot be undone.
        </p>
        <div v-if="deleteError" class="error-banner" style="margin-top:0.5rem;margin-bottom:0">
          {{ deleteError }}
        </div>
        <div class="modal-actions">
          <button class="dnd-button-ghost" @click="closeDeleteDialog">Cancel</button>
          <button class="dnd-button dnd-button-danger" @click="confirmDelete" :disabled="deleting">
            {{ deleting ? 'Deleting…' : 'Delete' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const campaignId = route.params.id

// ─── Type hierarchy ────────────────────────────────────────────────────────────
const CHILD_TYPES = {
  system:     ['planet', 'moon', 'star'],
  planet:     ['continent', 'ocean'],
  continent:  ['region', 'kingdom', 'sea'],
  kingdom:    ['region', 'city', 'keep', 'dungeon'],
  region:     ['town', 'city', 'village', 'keep', 'dungeon', 'wilderness', 'forest', 'mountain', 'ruin'],
  town:       ['inn', 'tavern', 'shop', 'temple', 'guild', 'district', 'keep', 'dungeon', 'NPC'],
  city:       ['inn', 'tavern', 'shop', 'temple', 'guild', 'district', 'keep', 'palace', 'dungeon', 'NPC'],
  village:    ['inn', 'tavern', 'shop', 'NPC'],
  keep:       ['room', 'courtyard', 'tower', 'dungeon', 'NPC'],
  palace:     ['room', 'courtyard', 'tower', 'NPC'],
  district:   ['inn', 'tavern', 'shop', 'temple', 'guild', 'market', 'NPC'],
  market:     ['shop', 'NPC'],
  inn:        ['room', 'NPC'],
  tavern:     ['room', 'NPC'],
  shop:       ['room', 'NPC'],
  temple:     ['room', 'NPC'],
  guild:      ['room', 'NPC'],
  mansion:    ['room', 'NPC'],
  dungeon:    ['room', 'corridor', 'NPC'],
  ruin:       ['room', 'NPC'],
  wilderness: ['encounter', 'ruin', 'dungeon', 'NPC'],
  forest:     ['encounter', 'ruin', 'dungeon', 'NPC'],
  mountain:   ['encounter', 'ruin', 'dungeon', 'keep', 'NPC'],
  room:       ['party', 'NPC', 'container', 'furniture'],
  corridor:   ['room'],
  courtyard:  ['NPC', 'party'],
  tower:      ['room'],
  encounter:  ['NPC'],
  party:      ['PC', 'NPC'],
  PC:         ['weapon', 'armor', 'ring', 'artifact', 'scroll', 'potion', 'shield', 'container'],
  NPC:        ['weapon', 'armor', 'ring', 'artifact', 'scroll', 'potion', 'shield', 'container'],
  container:  ['weapon', 'armor', 'ring', 'artifact', 'scroll', 'potion', 'shield'],
}

// ─── Random names ──────────────────────────────────────────────────────────────
const NAMES = {
  system:     ['Realmspace', 'Wildspace', 'The Crystal Shell', 'Astral Expanse'],
  planet:     ['Toril', 'Krynn', 'Oerth', 'Athas', 'Eberron'],
  continent:  ['Faerûn', 'Kara-Tur', 'Zakhara', 'Maztica', 'Anchorome'],
  kingdom:    ['Cormyr', 'Amn', 'Tethyr', 'Sembia', 'Aglarond'],
  region:     ['The Sword Coast', 'The Heartlands', 'The North', 'The Dalelands', 'The Moonsea'],
  town:       ['Phandalin', 'Triboar', 'Red Larch', 'Longsaddle', 'Secomber'],
  city:       ['Waterdeep', 'Baldur\'s Gate', 'Neverwinter', 'Luskan', 'Athkatla'],
  village:    ['Greenest', 'Thundertree', 'Barovia', 'Oakhurst', 'Saltmarsh'],
  keep:       ['Helm\'s Hold', 'Thornhold', 'Darkhold', 'Highcliff', 'Starmantle'],
  palace:     ['The High Hall', 'The Sea Palace', 'Grand Palace', 'The Citadel'],
  inn:        ['The Rusty Anchor', 'Stonehill Inn', 'The Yawning Portal', 'The Wandering Wyvern'],
  tavern:     ['The Drunken Dragon', 'The Leaky Cauldron', 'The Fool\'s Gold', 'The Broken Axe'],
  shop:       ['Alchemist\'s Workshop', 'Blacksmith Forge', 'Curio Emporium', 'Trader\'s Post'],
  temple:     ['Temple of Tyr', 'Shrine of Chauntea', 'House of Wonder', 'Shrine of Selûne'],
  guild:      ['Thieves\' Guild', 'Merchant\'s Guild', 'Mages\' Guild', 'Craftsmen\'s Brotherhood'],
  dungeon:    ['Cragmaw Caverns', 'Wave Echo Cave', 'Sunless Citadel', 'Undermountain'],
  district:   ['Market District', 'Harbor District', 'Noble Quarter', 'Temple District'],
  market:     ['Grand Bazaar', 'Night Market', 'Trade Square', 'The Exchange'],
  wilderness: ['Neverwinter Wood', 'The High Forest', 'Anauroch', 'The Reaching Wood'],
  forest:     ['Cormanthor', 'Forest of Wyrms', 'Methwood', 'Rawlinswood'],
  mountain:   ['Spine of the World', 'Graypeak Mountains', 'Thunder Peaks', 'Iron Hills'],
  ruin:       ['Thundertree', 'Myth Drannor', 'The Lost City', 'Xorvintroth'],
  room:       ['Common Room', 'Storage Room', 'Guard Chamber', 'Great Hall', 'Trophy Room'],
  corridor:   ['Long Passage', 'Winding Tunnel', 'Secret Corridor', 'Underground Passage'],
  courtyard:  ['Inner Courtyard', 'Training Yard', 'Castle Courtyard', 'Garden Court'],
  tower:      ['North Tower', 'Wizard\'s Spire', 'Guard Tower', 'Observation Tower'],
  encounter:  ['Goblin Ambush', 'Bandit Camp', 'Monster Lair', 'Ancient Trap'],
  party:      ['The Adventurers', 'Company of the Shield', 'The Grey Wanderers', 'Iron Circle'],
  PC:         ['Thorin', 'Aria', 'Grim', 'Elowen', 'Zara', 'Bram', 'Lyria', 'Kordan'],
  NPC:        ['Aldric', 'Sable', 'Mira', 'Grendel', 'Elara', 'Torvin', 'Sylvan', 'Nora'],
  weapon:     ['Silvered Longsword', 'Dwarven Axe', 'Shadow Dagger', 'Flaming Spear', 'Blessed Mace'],
  armor:      ['Chain Mail', 'Leather Armor', 'Plate Mail', 'Scale Mail', 'Breastplate'],
  shield:     ['Wooden Shield', 'Iron Shield', 'Kite Shield', 'Elven Buckler'],
  ring:       ['Ring of Protection', 'Ring of Fire Resistance', 'Ring of Spell Storing', 'Signet Ring'],
  artifact:   ['Crystal Orb', 'Ancient Tome', 'Cursed Idol', 'Dragon Scale', 'Astral Compass'],
  scroll:     ['Fireball Scroll', 'Cure Wounds Scroll', 'Arcane Gate Scroll', 'Detect Magic Scroll'],
  potion:     ['Healing Potion', 'Potion of Speed', 'Potion of Invisibility', 'Giant Strength Potion'],
  container:  ['Iron Chest', 'Leather Satchel', 'Barrel', 'Ornate Crate'],
  furniture:  ['Oak Table', 'Iron Bed', 'Carved Chair', 'Stone Fireplace'],
  moon:       ['Selûne', 'Ghost Moon', 'The Silver Eye', 'Pale Wanderer'],
  star:       ['The Evening Star', 'Mystra\'s Beacon', 'Torm\'s Light'],
  ocean:      ['Sea of Swords', 'The Trackless Sea', 'Dragon Sea'],
  sea:        ['The Shining Sea', 'Sea of Fallen Stars', 'Azure Sea'],
}

// ─── Type-specific dialog fields ───────────────────────────────────────────────
const RACES   = ['Human','Elf','Dwarf','Halfling','Gnome','Half-Elf','Half-Orc','Tiefling','Dragonborn']
const CLASSES = ['Fighter','Wizard','Rogue','Cleric','Ranger','Paladin','Barbarian','Bard','Druid','Monk','Sorcerer','Warlock']

const TYPE_FIELDS = {
  PC: [
    { key: 'race',       label: 'Race',      type: 'select', options: RACES },
    { key: 'class_type', label: 'Class',     type: 'select', options: CLASSES },
    { key: 'abilities',  label: 'Abilities', type: 'abilities' },
  ],
  NPC: [
    { key: 'race',        label: 'Race',        type: 'select', options: RACES },
    { key: 'personality', label: 'Personality', type: 'text' },
    { key: 'abilities',   label: 'Abilities',   type: 'abilities' },
  ],
  weapon: [
    { key: 'damage_die',  label: 'Damage Die',  type: 'select', options: ['1d4','1d6','1d8','1d10','1d12','2d6'] },
    { key: 'damage_type', label: 'Damage Type', type: 'select', options: ['slashing','piercing','bludgeoning'] },
  ],
  armor: [
    { key: 'armor_class', label: 'Armor Class', type: 'number' },
    { key: 'armor_type',  label: 'Armor Type',  type: 'select', options: ['light','medium','heavy'] },
  ],
  shield: [
    { key: 'armor_class_bonus', label: 'AC Bonus', type: 'number' },
  ],
  potion: [
    { key: 'effect', label: 'Effect', type: 'text' },
    { key: 'uses',   label: 'Uses',   type: 'number' },
  ],
  scroll: [
    { key: 'spell_name',  label: 'Spell',       type: 'text' },
    { key: 'spell_level', label: 'Spell Level', type: 'number' },
  ],
  artifact: [
    { key: 'power',      label: 'Power',      type: 'text' },
    { key: 'attunement', label: 'Attunement', type: 'select', options: ['required','not required'] },
  ],
  ring: [
    { key: 'power',      label: 'Power',      type: 'text' },
    { key: 'attunement', label: 'Attunement', type: 'select', options: ['required','not required'] },
  ],
}

function typeFields(type) { return TYPE_FIELDS[type] || [] }

// ─── Random helpers ────────────────────────────────────────────────────────────
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)] }

function randomName(type) {
  return pick(NAMES[type] || ['Item'])
}

function rollAbilities() {
  const roll = () => {
    const d = Array.from({ length: 4 }, () => Math.floor(Math.random() * 6) + 1)
    d.sort((a, b) => a - b)
    d.shift()
    return d.reduce((s, v) => s + v, 0)
  }
  return { str: roll(), dex: roll(), con: roll(), int: roll(), wis: roll(), chr: roll() }
}

function randomDefaults(type) {
  switch (type) {
    case 'PC':      return { race: pick(RACES), class_type: pick(CLASSES), abilities: rollAbilities() }
    case 'NPC':     return { race: pick(RACES), personality: pick(['Friendly','Gruff','Cautious','Cunning','Boisterous','Mysterious']), abilities: rollAbilities() }
    case 'weapon':  return { damage_die: pick(['1d6','1d8','1d10']), damage_type: pick(['slashing','piercing','bludgeoning']) }
    case 'armor':   return { armor_class: 12 + Math.floor(Math.random() * 5), armor_type: pick(['light','medium','heavy']) }
    case 'shield':  return { armor_class_bonus: 2 }
    case 'potion':  return { effect: pick(['Heals 2d4+2 HP','Grants invisibility for 1 hour','Increases speed by 30ft']), uses: 1 }
    case 'scroll':  return { spell_name: pick(['Magic Missile','Fireball','Cure Wounds','Shield','Detect Magic']), spell_level: pick([1,2,3]) }
    case 'artifact':return { power: pick(['Grants +1 to saving throws','Emits light in 30ft','Allows telepathy']), attunement: 'required' }
    case 'ring':    return { power: pick(['Protection +1','Fire resistance','Water breathing','Feather fall']), attunement: 'not required' }
    default:        return {}
  }
}

// ─── State ─────────────────────────────────────────────────────────────────────
const rawObjects   = ref([])
const loading      = ref(false)
const error        = ref(null)
const selectedNode = ref(null)
const saving       = ref(false)
const createError  = ref(null)

const ctxMenu          = ref({ visible: false, x: 0, y: 0, node: null })
const ctxSubmenuOpen   = ref(false)
const createDialog     = ref({ visible: false, type: '', name: '', description: '', properties: {}, parentId: null })
const deleteDialog     = ref({ visible: false, node: null })
const deleting         = ref(false)
const deleteError      = ref(null)

const dialogRef    = ref(null)
const nameInputRef = ref(null)

// ─── Computed ──────────────────────────────────────────────────────────────────
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

const ctxChildTypes = computed(() => CHILD_TYPES[ctxMenu.value.node?.type] || [])

// ─── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await fetchWorld()
  document.addEventListener('click', onGlobalClick)
  document.addEventListener('keydown', onGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', onGlobalClick)
  document.removeEventListener('keydown', onGlobalKeydown)
})

watch(() => createDialog.value.visible, async (visible) => {
  if (visible) {
    await nextTick()
    dialogRef.value?.focus()
    nameInputRef.value?.focus()
  }
})

// ─── World fetch ───────────────────────────────────────────────────────────────
async function fetchWorld() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`/api/admin/world/${campaignId}`, { credentials: 'include' })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      throw new Error(d.detail || 'Failed to load world')
    }
    rawObjects.value = (await res.json()).objects
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// ─── Tree interaction ──────────────────────────────────────────────────────────
function onNodeClick(node) {
  closeCtxMenu()
  selectedNode.value = node
}

function parentName(parentId) {
  return rawObjects.value.find(o => o.id === parentId)?.name || '(unnamed)'
}

function selectById(id) {
  const node = flatNodes.value.find(n => n.id === id)
  if (node) selectedNode.value = node
}

// ─── Context menu ──────────────────────────────────────────────────────────────
function onContextMenu(e, node) {
  ctxSubmenuOpen.value = false
  ctxMenu.value = {
    visible: true,
    x: Math.min(e.clientX, window.innerWidth - 320),
    y: Math.min(e.clientY, window.innerHeight - 200),
    node,
  }
  selectedNode.value = node
}

function closeCtxMenu() {
  ctxMenu.value.visible = false
  ctxSubmenuOpen.value = false
}

// ─── Create dialog ─────────────────────────────────────────────────────────────
function openDialog(type) {
  closeCtxMenu()
  createError.value = null
  createDialog.value = {
    visible: true,
    type,
    name: randomName(type),
    description: '',
    properties: randomDefaults(type),
    parentId: ctxMenu.value.node?.id ?? null,
  }
}

function closeDialog() {
  createDialog.value.visible = false
  createError.value = null
}

function onDialogKey(e) {
  if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
    e.preventDefault()
    saveObject()
  }
  if (e.key === 'Escape') closeDialog()
}

async function saveObject() {
  if (saving.value) return
  saving.value = true
  createError.value = null
  try {
    const body = {
      parent: createDialog.value.parentId,
      type:   createDialog.value.type,
      name:   createDialog.value.name.trim(),
      description: createDialog.value.description.trim() || null,
      properties: createDialog.value.properties,
    }
    const res = await fetch(`/api/admin/world/${campaignId}/objects`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      throw new Error(d.detail || 'Failed to create object')
    }
    const newObj = await res.json()
    rawObjects.value = [...rawObjects.value, newObj]
    selectedNode.value = flatNodes.value.find(n => n.id === newObj.id) || null
    closeDialog()
  } catch (e) {
    createError.value = e.message
  } finally {
    saving.value = false
  }
}

// ─── Delete dialog ─────────────────────────────────────────────────────────────
function openDeleteDialog() {
  const node = ctxMenu.value.node
  closeCtxMenu()
  deleteError.value = null
  deleteDialog.value = { visible: true, node }
}

function closeDeleteDialog() {
  deleteDialog.value = { visible: false, node: null }
  deleteError.value = null
}

async function confirmDelete() {
  if (deleting.value || !deleteDialog.value.node) return
  deleting.value = true
  deleteError.value = null
  try {
    const id = deleteDialog.value.node.id
    const res = await fetch(`/api/admin/world/${campaignId}/objects/${id}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      throw new Error(d.detail || 'Failed to delete object')
    }
    const data = await res.json()
    const deletedIds = new Set([data.deleted_id, ...data.deleted_descendants])
    rawObjects.value = rawObjects.value.filter(o => !deletedIds.has(o.id))
    if (selectedNode.value && deletedIds.has(selectedNode.value.id)) {
      selectedNode.value = null
    }
    closeDeleteDialog()
  } catch (e) {
    deleteError.value = e.message
  } finally {
    deleting.value = false
  }
}

// ─── Global event handlers ─────────────────────────────────────────────────────
function onGlobalClick() { closeCtxMenu() }
function onGlobalKeydown(e) {
  if (e.key === 'Escape') { closeCtxMenu(); closeDialog(); closeDeleteDialog() }
}

// ─── Detail panel helpers ──────────────────────────────────────────────────────
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

/* ── Sidebar ── */
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
.sidebar-link:hover { background: rgba(201,162,39,0.06); color: #c9a227; }
.sidebar-link.active { background: rgba(201,162,39,0.1); color: #c9a227; border-right: 2px solid #c9a227; }

/* ── Main ── */
.admin-main { flex: 1; min-width: 0; padding-bottom: 3rem; overflow: hidden; }
.admin-container { padding: 2rem 1.5rem; }
.admin-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
.admin-header-left { flex: 1; }
.admin-title { font-family: 'Cinzel', serif; font-size: 1.8rem; font-weight: 700; color: #c9a227; margin-bottom: 0.2rem; }
.admin-subtitle { font-family: 'Crimson Text', serif; font-style: italic; color: #8a7355; font-size: 1rem; }

.error-banner { background: rgba(139,26,26,0.2); border: 1px solid #7f1d1d; color: #f87171; font-family: 'Crimson Text', serif; padding: 0.75rem 1rem; border-radius: 5px; margin-bottom: 1.5rem; }
.loading-state { display: flex; align-items: center; gap: 0.75rem; color: #8a7355; font-family: 'Crimson Text', serif; font-style: italic; padding: 2rem 0; }
.spinner { width: 20px; height: 20px; border: 2px solid #3d2e10; border-top-color: #c9a227; border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
.empty-state { color: #5a4530; font-family: 'Crimson Text', serif; font-style: italic; text-align: center; padding: 3rem 0; }

/* ── Two-column layout ── */
.world-layout { display: flex; gap: 1.25rem; align-items: flex-start; }
.tree-col { flex: 1; min-width: 0; }
.detail-col { width: 340px; flex-shrink: 0; position: sticky; top: 80px; }

/* ── Tree ── */
.world-tree { padding: 0.25rem 0; }
.tree-node {
  display: flex; align-items: baseline; flex-wrap: wrap;
  padding: 0.3rem 1rem 0.3rem 0;
  border-bottom: 1px solid rgba(42,30,8,0.5);
  font-family: 'Crimson Text', serif; font-size: 0.97rem; line-height: 1.4;
  cursor: pointer; transition: background 0.1s; user-select: none;
}
.tree-node:last-child { border-bottom: none; }
.tree-node:hover  { background: rgba(201,162,39,0.05); }
.tree-node.selected { background: rgba(201,162,39,0.1); }
.node-name { font-family: 'Cinzel', serif; font-size: 0.82rem; font-weight: 700; color: #c9a227; }
.node-type { font-family: 'Crimson Text', serif; font-size: 0.85rem; color: #7a6115; }
.node-desc { color: #8a7355; font-size: 0.93rem; }

/* ── Detail panel ── */
.detail-empty { padding: 2rem 1rem; text-align: center; }
.detail-empty-text { font-family: 'Crimson Text', serif; font-style: italic; color: #4a3820; font-size: 0.95rem; }
.detail-panel { padding: 1.25rem 1.25rem 1.5rem; }
.detail-header { display: flex; align-items: baseline; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.4rem; }
.detail-name { font-family: 'Cinzel', serif; font-size: 1.1rem; font-weight: 700; color: #c9a227; }
.detail-type-badge { font-family: 'Crimson Text', serif; font-size: 0.78rem; color: #7a6115; border: 1px solid #3d2e10; border-radius: 3px; padding: 0.05rem 0.4rem; background: #1a1109; }
.detail-desc { font-family: 'Crimson Text', serif; font-size: 0.95rem; color: #8a7355; font-style: italic; margin-bottom: 0.75rem; line-height: 1.5; }
.detail-section { display: flex; flex-direction: column; gap: 0.2rem; margin-bottom: 0.25rem; }
.detail-meta-row { display: flex; gap: 0.5rem; font-family: 'Crimson Text', serif; font-size: 0.88rem; }
.meta-key { color: #5a4530; min-width: 52px; }
.meta-val { color: #8a7355; }
.meta-val-link { color: #7a6115; cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
.meta-val-link:hover { color: #c9a227; }
.detail-divider { height: 1px; background: #2a1e08; margin: 0.75rem 0; }
.detail-props { display: flex; flex-direction: column; gap: 0.1rem; }
.prop-line { font-family: 'Crimson Text', serif; font-size: 0.9rem; line-height: 1.5; }
.prop-section { font-family: 'Cinzel', serif; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em; color: #5a4530; text-transform: uppercase; display: block; margin-top: 0.35rem; }
.prop-key { color: #7a6115; }
.prop-sep { color: #4a3820; }
.prop-val { color: #c8b67a; }

/* ── Context menu ── */
.ctx-menu {
  position: fixed;
  z-index: 500;
  background: linear-gradient(to bottom, #1a1109, #150f06);
  border: 1px solid #7a6115;
  border-radius: 5px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.75);
  min-width: 140px;
}
.ctx-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  font-family: 'Cinzel', serif;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #c9a227;
  cursor: pointer;
  white-space: nowrap;
  position: relative;
  gap: 0.75rem;
}
.ctx-item:hover { background: rgba(201,162,39,0.1); color: #e8d5b7; }
.ctx-disabled { color: #4a3820; cursor: default; }
.ctx-disabled:hover { background: none; color: #4a3820; }
.ctx-arrow { font-size: 0.55rem; color: #7a6115; flex-shrink: 0; }
.ctx-divider { height: 1px; background: #2a1e08; margin: 0.2rem 0; }
.ctx-danger { color: #c05050; }
.ctx-danger:hover { background: rgba(192,80,80,0.12); color: #e87878; }

.ctx-has-sub { position: relative; }
.ctx-sub {
  position: absolute;
  left: 100%;
  top: -1px;
  background: linear-gradient(to bottom, #1a1109, #150f06);
  border: 1px solid #7a6115;
  border-radius: 5px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.75);
  min-width: 160px;
  max-height: 320px;
  overflow-y: auto;
  z-index: 501;
}

/* ── Create dialog ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 300;
  padding: 1rem;
}
.create-modal {
  width: 100%;
  max-width: 420px;
  padding: 1.75rem 2rem 1.5rem;
  max-height: 90vh;
  overflow-y: auto;
  outline: none;
}
.modal-title {
  font-family: 'Cinzel', serif;
  font-size: 1.1rem;
  font-weight: 700;
  color: #c9a227;
  margin-bottom: 1.25rem;
}
.modal-type { text-transform: capitalize; }
.modal-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.25rem; }

.form-group { margin-bottom: 0.875rem; }
.form-label {
  display: block;
  font-family: 'Cinzel', serif;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #7a6115;
  margin-bottom: 0.3rem;
}
.form-input, .form-textarea {
  width: 100%;
  background: #0a0703;
  border: 1px solid #3d2e10;
  border-radius: 4px;
  padding: 0.45rem 0.6rem;
  font-family: 'Crimson Text', serif;
  font-size: 1rem;
  color: #e8d5b7;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s;
}
.form-input:focus, .form-textarea:focus {
  border-color: #7a6115;
  box-shadow: 0 0 0 2px rgba(201,162,39,0.12);
}
.form-textarea { resize: vertical; min-height: 56px; }
select.form-input { cursor: pointer; }

/* ── Delete button ── */
.dnd-button-danger {
  background: rgba(139,26,26,0.3);
  border-color: #7f1d1d;
  color: #f87171;
}
.dnd-button-danger:hover:not(:disabled) {
  background: rgba(139,26,26,0.5);
  border-color: #ef4444;
  color: #fca5a5;
}

/* ── Delete warning ── */
.delete-warning {
  font-family: 'Crimson Text', serif;
  font-size: 1rem;
  color: #c08080;
  line-height: 1.5;
  margin-bottom: 1rem;
}

/* ── Abilities grid ── */
.abilities-block { margin-top: 0.25rem; }
.abilities-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.4rem;
}
.reroll-btn {
  font-family: 'Cinzel', serif;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: transparent;
  border: 1px solid #3d2e10;
  border-radius: 3px;
  color: #7a6115;
  padding: 0.2rem 0.55rem;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.reroll-btn:hover { border-color: #7a6115; color: #c9a227; }
.abilities-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 0.4rem;
}
.ability-cell {
  background: #0a0703;
  border: 1px solid #3d2e10;
  border-radius: 4px;
  padding: 0.35rem 0.2rem;
  text-align: center;
}
.ability-label {
  font-family: 'Cinzel', serif;
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #5a4530;
  text-transform: uppercase;
  margin-bottom: 0.15rem;
}
.ability-value {
  font-family: 'Crimson Text', serif;
  font-size: 1.15rem;
  font-weight: 700;
  color: #c9a227;
  line-height: 1;
}
</style>
