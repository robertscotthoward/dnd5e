import { defineStore } from 'pinia'
import { ref } from 'vue'

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
        chat.value.push(msg.message)
        break
      case 'player_list':
        players.value = msg.players
        break
      case 'hp_update': {
        const p = players.value.find(pl => pl.character_object_id === msg.character_object_id)
        if (p) { p.hp_current = msg.hp.current; p.hp_max = msg.hp.max }
        break
      }
      case 'mode_change':
        gameMode.value = msg.game_mode
        if (msg.initiative_order) activeTurn.value = msg.initiative_order[0]
        break
      case 'turn_change':
        activeTurn.value = msg.active_player_turn
        break
      case 'snapshot_created':
        snapshots.value.push(msg.snapshot)
        break
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

  async function fetchSnapshots(id) {
    try {
      const res = await fetch(`/api/campaigns/${id}/snapshots`, { credentials: 'include' })
      snapshots.value = await res.json()
    } catch (e) {
      // ignore
    }
  }

  return {
    campaigns, currentMeta, players, chat, gameMode, activeTurn,
    dmThinking, snapshots, loading, error, ws, wsStatus, joinResult,
    fetchCampaigns, createCampaign, joinCampaign, createCharacter,
    loadState, connectWs, disconnectWs, sendChat, sendAction, sendSnapshot,
    fetchSnapshots,
  }
})
