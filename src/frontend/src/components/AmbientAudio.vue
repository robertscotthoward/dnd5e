<template>
  <div class="ambient-audio">
    <button
      class="ambient-btn"
      :class="{ active: enabled }"
      @click="toggle"
      :title="enabled ? `Ambient: ${currentLabel} (click to mute)` : 'Enable ambient audio'"
    >
      <span class="ambient-icon">{{ enabled ? '&#x1F50A;' : '&#x1F507;' }}</span>
      <span class="ambient-label">{{ enabled ? currentLabel : 'Muted' }}</span>
    </button>
  </div>
</template>

<script setup>
import { ref, watch, computed, onUnmounted } from 'vue'

const props = defineProps({
  locationName: { type: String, default: '' },
  locationDescription: { type: String, default: '' },
})

// Infer ambient track from location name/description keywords
const LOCATION_TRACKS = {
  tavern:   { label: 'Tavern',   file: '/audio/tavern.mp3' },
  inn:      { label: 'Tavern',   file: '/audio/tavern.mp3' },
  dungeon:  { label: 'Dungeon',  file: '/audio/dungeon.mp3' },
  cave:     { label: 'Dungeon',  file: '/audio/dungeon.mp3' },
  crypt:    { label: 'Dungeon',  file: '/audio/dungeon.mp3' },
  mine:     { label: 'Dungeon',  file: '/audio/dungeon.mp3' },
  forest:   { label: 'Forest',   file: '/audio/forest.mp3' },
  wood:     { label: 'Forest',   file: '/audio/forest.mp3' },
  grove:    { label: 'Forest',   file: '/audio/forest.mp3' },
  swamp:    { label: 'Forest',   file: '/audio/forest.mp3' },
  road:     { label: 'Outdoor',  file: '/audio/outdoor.mp3' },
  plains:   { label: 'Outdoor',  file: '/audio/outdoor.mp3' },
  field:    { label: 'Outdoor',  file: '/audio/outdoor.mp3' },
  mountain: { label: 'Outdoor',  file: '/audio/outdoor.mp3' },
  city:     { label: 'Outdoor',  file: '/audio/outdoor.mp3' },
  town:     { label: 'Outdoor',  file: '/audio/outdoor.mp3' },
  village:  { label: 'Outdoor',  file: '/audio/outdoor.mp3' },
}

function inferTrack(name, desc) {
  const text = `${name} ${desc}`.toLowerCase()
  for (const [keyword, track] of Object.entries(LOCATION_TRACKS)) {
    if (text.includes(keyword)) return track
  }
  return { label: 'Outdoor', file: '/audio/outdoor.mp3' }
}

const enabled = ref(false)
const audio = ref(null)

const currentTrack = computed(() => inferTrack(props.locationName, props.locationDescription))
const currentLabel = computed(() => currentTrack.value.label)

function startAudio(src) {
  stopAudio()
  const el = new Audio(src)
  el.loop = true
  el.volume = 0.3
  el.play().catch(() => {})
  audio.value = el
}

function stopAudio() {
  if (audio.value) {
    audio.value.pause()
    audio.value.src = ''
    audio.value = null
  }
}

function toggle() {
  enabled.value = !enabled.value
  if (enabled.value) {
    startAudio(currentTrack.value.file)
  } else {
    stopAudio()
  }
}

// When the location changes while audio is playing, switch to new track
watch(currentTrack, (newTrack) => {
  if (enabled.value) {
    startAudio(newTrack.file)
  }
})

onUnmounted(() => {
  stopAudio()
})
</script>

<style scoped>
.ambient-audio {
  display: inline-flex;
  align-items: center;
}

.ambient-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: transparent;
  border: 1px solid #3d2e10;
  color: #8a7355;
  cursor: pointer;
  font-family: 'Cinzel', serif;
  font-size: 0.6rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 0.2rem 0.55rem;
  border-radius: 3px;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
  white-space: nowrap;
}

.ambient-btn:hover {
  color: #c9a227;
  border-color: #c9a227;
}

.ambient-btn.active {
  color: #c9a227;
  border-color: #7a6115;
  background: rgba(201, 162, 39, 0.1);
}

.ambient-icon {
  font-size: 0.75rem;
  line-height: 1;
}

.ambient-label {
  max-width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
