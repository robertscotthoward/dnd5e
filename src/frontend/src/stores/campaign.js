import { defineStore } from 'pinia'
import { ref } from 'vue'

// D&D 5e XP thresholds (index = level)
const XP_THRESHOLDS = [
  0, 0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
  85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000,
]
export function xpLevelFor(totalXp) {
  let level = 1
  for (let lvl = 20; lvl >= 1; lvl--) {
    if (totalXp >= XP_THRESHOLDS[lvl]) { level = lvl; break }
  }
  return level
}
export function xpToNextLevel(totalXp) {
  const cur = xpLevelFor(totalXp)
  if (cur >= 20) return 0
  return XP_THRESHOLDS[cur + 1] - totalXp
}

export const useCampaignStore = defineStore('campaign', () => {
  const campaigns = ref([])
  const currentMeta = ref(null)
  const players = ref([])
  const chat = ref([])
  const gameMode = ref('Exploration')
  const activeTurn = ref(null)
  const dmThinking = ref(false)
  const snapshots = ref([])
  const loading = ref(false)
  const error = ref(null)
  const ws = ref(null)
  const wsStatus = ref('disconnected')
  const joinResult = ref(null)  // { needs_character, player, summary }
  const pendingLevelUp = ref(null)  // { character_id, character_name, old_level, new_level, hit_die, class_type, has_asi }
  const pendingDiceRoll = ref(null) // { die: 'd20', result: 15, queued_message: {...} }
  const initiativeOrder = ref([])   // [{ id, name, initiative }] sorted highest first
  const pendingLoot = ref(null)     // { enemies_defeated, coins, items, loot_container_id }

  async function fetchCampaigns() {
    loading.value = true
    try {
      const res = await fetch('/api/campaigns', { credentials: 'include' })
      campaigns.value = await res.json()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createCampaign(name, seed = null) {
    loading.value = true
    try {
      const res = await fetch('/api/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, seed }),
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to create campaign')
      return data
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function joinCampaign(id) {
    loading.value = true
    try {
      const res = await fetch(`/api/campaigns/${id}/join`, {
        method: 'POST',
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to join')
      joinResult.value = data
      return data
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function generateBackground(campaignId, { name, race, class_type, region }) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/campaigns/${campaignId}/generate-background`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, race, class_type, region }),
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to generate background')
      return data.background
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function createCharacter(campaignId, charData) {
    loading.value = true
    try {
      const res = await fetch(`/api/campaigns/${campaignId}/characters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(charData),
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to create character')
      return data
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  async function loadState(id) {
    loading.value = true
    try {
      const res = await fetch(`/api/campaigns/${id}/state`, { credentials: 'include' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to load state')
      currentMeta.value = data.meta
      players.value = data.players || []
      chat.value = data.chat || []
      gameMode.value = data.meta?.game_mode || 'Exploration'
      activeTurn.value = data.meta?.active_player_turn || null
      if (data.initiative_order) initiativeOrder.value = data.initiative_order
      else if (data.meta?.game_mode !== 'Combat') initiativeOrder.value = []
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  function connectWs(campaignId) {
    if (ws.value) disconnectWs()
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/api/ws/${campaignId}`
    wsStatus.value = 'connecting'
    const socket = new WebSocket(url)
    ws.value = socket

    socket.onopen = () => {
      wsStatus.value = 'connected'
    }

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        handleWsMessage(msg)
      } catch (e) {
        // ignore parse errors
      }
    }

    socket.onclose = () => {
      wsStatus.value = 'disconnected'
      ws.value = null
    }

    socket.onerror = () => {
      wsStatus.value = 'error'
    }
  }

  function disconnectWs() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    wsStatus.value = 'disconnected'
  }

  function handleWsMessage(msg) {
    switch (msg.type) {
      case 'joined':
        currentMeta.value = msg.campaign
        break
      case 'chat':
        chat.value.push(msg.message)
        break
      case 'dm_thinking':
        dmThinking.value = true
        break
      case 'dm_response':
        dmThinking.value = false
        // Check if the message contains a dice roll result to animate
        if (msg.dice_roll) {
          pendingDiceRoll.value = {
            die: msg.dice_roll.die || 'd20',
            result: msg.dice_roll.result,
            queued_message: msg.message,
          }
        } else {
          chat.value.push(msg.message)
        }
        break
      case 'dice_roll':
        pendingDiceRoll.value = {
          die: msg.die || 'd20',
          result: msg.result,
          queued_message: msg.message || null,
        }
        break
      case 'player_list':
        players.value = msg.players
        break
      case 'hp_update': {
        const p = players.value.find(pl => pl.character_object_id === msg.character_object_id)
        if (p) {
          p.hp_current = msg.hp.current
          p.hp_max = msg.hp.max
          // Auto-sync unconscious condition based on HP
          if (!p.conditions) p.conditions = []
          if (p.hp_current <= 0 && p.hp_max > 0) {
            if (!p.conditions.includes('unconscious')) p.conditions.push('unconscious')
          } else {
            p.conditions = p.conditions.filter(c => c !== 'unconscious')
          }
        }
        break
      }
      case 'combat_state':
        activeTurn.value = msg.active_turn
        if (msg.initiative_order) {
          initiativeOrder.value = msg.initiative_order
        }
        break
      case 'mode_change':
        gameMode.value = msg.game_mode
        if (msg.initiative_order) {
          initiativeOrder.value = msg.initiative_order
          activeTurn.value = msg.initiative_order[0]?.id ?? null
        }
        if (msg.game_mode !== 'Combat') initiativeOrder.value = []
        break
      case 'turn_change':
        activeTurn.value = msg.active_player_turn
        break
      case 'snapshot_created':
        snapshots.value.push(msg.snapshot)
        break
      case 'xp_awarded': {
        const xpData = msg.data
        const xpPlayer = players.value.find(p => p.character_object_id === xpData?.id)
        if (xpPlayer) {
          xpPlayer.experience = xpData.new_xp
        }
        if (msg.message) chat.value.push(msg.message)
        break
      }
      case 'level_up':
        pendingLevelUp.value = msg.level_up
        break
      case 'death_save_result': {
        const diceInfo = msg.dice_roll || (msg.data?.roll !== undefined ? { die: 'd20', result: msg.data.roll } : null)
        if (diceInfo && msg.message) {
          pendingDiceRoll.value = {
            die: diceInfo.die || 'd20',
            result: diceInfo.result,
            queued_message: msg.message,
          }
        } else if (msg.message) {
          chat.value.push(msg.message)
        }
        break
      }
      case 'loot_summary':
        pendingLoot.value = msg.loot
        if (msg.message) chat.value.push(msg.message)
        break
      case 'loot_taken': {
        if (msg.message) chat.value.push(msg.message)
        // Mark the item as taken in pendingLoot
        if (pendingLoot.value) {
          const item = pendingLoot.value.items.find(i => i.id === msg.item_id)
          if (item) item.taken_by = msg.character_name
        }
        break
      }
    }
  }

  function sendChat(text) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'chat', text }))
    }
  }

  function sendAction(action, targetId = null) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'action', action, target_id: targetId }))
    }
  }

  function sendSnapshot(label) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'snapshot', label }))
    }
  }

  function sendAwardXp(characterId, amount, reason = '') {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'award_xp', character_id: characterId, amount, reason }))
    }
  }

  async function awardXp(campaignId, characterId, amount, reason = '') {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/campaigns/${campaignId}/award-xp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ character_id: characterId, amount, reason }),
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to award XP')
      if (data.level_up) pendingLevelUp.value = data.level_up
      return data
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  function clearLevelUp() {
    pendingLevelUp.value = null
  }

  function clearDiceRoll() {
    if (pendingDiceRoll.value?.queued_message) {
      chat.value.push(pendingDiceRoll.value.queued_message)
    }
    pendingDiceRoll.value = null
  }

  function sendTakeLoot(itemId, characterId) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(JSON.stringify({ type: 'take_loot', item_id: itemId, character_id: characterId }))
    }
  }

  function clearLoot() {
    pendingLoot.value = null
  }

  async function fetchSnapshots(id) {
    try {
      const res = await fetch(`/api/campaigns/${id}/snapshots`, { credentials: 'include' })
      snapshots.value = await res.json()
    } catch (e) {
      // ignore
    }
  }

  async function restoreSnapshot(campaignId, snapshotId) {
    loading.value = true
    error.value = null
    try {
      const res = await fetch(`/api/campaigns/${campaignId}/snapshots/${snapshotId}/restore`, {
        method: 'POST',
        credentials: 'include',
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Restore failed')
      // Reload campaign state to reflect restored world
      await loadState(campaignId)
      return data
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      loading.value = false
    }
  }

  return {
    campaigns, currentMeta, players, chat, gameMode, activeTurn,
    dmThinking, snapshots, loading, error, ws, wsStatus, joinResult,
    pendingLevelUp, pendingDiceRoll, initiativeOrder, pendingLoot,
    fetchCampaigns, createCampaign, joinCampaign, generateBackground, createCharacter,
    loadState, connectWs, disconnectWs, sendChat, sendAction, sendSnapshot,
    fetchSnapshots, restoreSnapshot, sendAwardXp, awardXp, clearLevelUp, clearDiceRoll,
    sendTakeLoot, clearLoot,
  }
})
