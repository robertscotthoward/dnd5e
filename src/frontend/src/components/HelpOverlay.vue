<template>
  <Teleport to="body">
    <div v-if="visible" class="help-backdrop" @click.self="close">
      <div class="help-overlay" role="dialog" aria-label="Help Wiki">
        <!-- Header -->
        <div class="help-header">
          <button
            class="help-back"
            :disabled="!canGoBack"
            title="Back (Backspace)"
            @click="goBack"
          >&#8592;</button>
          <div class="help-title">Help &amp; Wiki</div>
          <div class="help-search-wrap">
            <input
              ref="searchInput"
              v-model="searchQuery"
              class="help-search"
              type="search"
              placeholder="Search wiki..."
              @input="onSearch"
            />
          </div>
          <button class="help-close" title="Close (Escape)" @click="close">✕</button>
        </div>

        <!-- Search results -->
        <div v-if="searchQuery && searchResults !== null" class="help-search-results">
          <div v-if="searchResults.length === 0" class="help-no-results">No pages match "{{ searchQuery }}".</div>
          <ul v-else class="help-result-list">
            <li
              v-for="result in searchResults"
              :key="result.path"
              class="help-result-item"
              @click="navigateTo(result.path)"
            >
              {{ result.title }}
            </li>
          </ul>
        </div>

        <!-- Markdown content -->
        <div v-else class="help-body">
          <div v-if="loading" class="help-loading">Loading...</div>
          <div v-else-if="error" class="help-error">{{ error }}</div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div v-else class="help-markdown" @click="onContentClick" v-html="renderedMarkdown"></div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['update:visible'])

const currentPath = ref('home.md')
const historyStack = ref([])
const rawMarkdown = ref('')
const renderedMarkdown = ref('')
const loading = ref(false)
const error = ref('')
const searchQuery = ref('')
const searchResults = ref(null)
const searchTimeout = ref(null)
const searchInput = ref(null)

const canGoBack = computed(() => historyStack.value.length > 0)

function onWindowKeydown(event) {
  if (!props.visible) return
  if (event.key === 'Escape') { event.preventDefault(); close(); return }
  if (event.key === 'Backspace' && document.activeElement !== searchInput.value) {
    event.preventDefault()
    goBack()
  }
}

window.addEventListener('keydown', onWindowKeydown)
onUnmounted(() => window.removeEventListener('keydown', onWindowKeydown))

function close() {
  emit('update:visible', false)
}

async function loadPage(path) {
  if (!path.endsWith('.md')) path = path + '.md'
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/help/${path}`)
    if (!res.ok) throw new Error(`Page not found: ${path}`)
    rawMarkdown.value = await res.text()
    renderedMarkdown.value = marked.parse(rawMarkdown.value)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function navigateTo(path) {
  searchQuery.value = ''
  searchResults.value = null
  historyStack.value.push(currentPath.value)
  currentPath.value = path
  loadPage(path)
}

function goBack() {
  if (!canGoBack.value) return
  const prev = historyStack.value.pop()
  currentPath.value = prev
  searchQuery.value = ''
  searchResults.value = null
  loadPage(prev)
}

function onContentClick(event) {
  const anchor = event.target.closest('a')
  if (!anchor) return
  const href = anchor.getAttribute('href')
  if (!href || href.startsWith('http')) return
  event.preventDefault()
  navigateTo(href)
}

function onSearch() {
  clearTimeout(searchTimeout.value)
  if (!searchQuery.value.trim()) {
    searchResults.value = null
    return
  }
  searchTimeout.value = setTimeout(async () => {
    try {
      const res = await fetch(`/api/help/search?q=${encodeURIComponent(searchQuery.value)}`)
      const data = await res.json()
      searchResults.value = data.results
    } catch {
      searchResults.value = []
    }
  }, 300)
}

watch(
  () => props.visible,
  async (val) => {
    if (val) {
      searchQuery.value = ''
      searchResults.value = null
      historyStack.value = []
      currentPath.value = 'home.md'
      await loadPage(currentPath.value)
    }
  }
)
</script>

<style scoped>
.help-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  z-index: 9000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.help-overlay {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  width: min(900px, 95vw);
  height: min(80vh, 700px);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-gold-lg);
  overflow: hidden;
}

.help-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--card);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.help-title {
  font-family: 'Cinzel', serif;
  color: var(--gold);
  font-size: 1rem;
  white-space: nowrap;
}

.help-search-wrap {
  flex: 1;
}

.help-search {
  width: 100%;
  background: var(--dark);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--parchment);
  padding: 0.35rem 0.6rem;
  font-size: 0.95rem;
  outline: none;
}

.help-search:focus {
  border-color: var(--gold-dim);
}

.help-back {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 1.2rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  line-height: 1;
  flex-shrink: 0;
}

.help-back:hover:not(:disabled) {
  color: var(--parchment);
  background: var(--border);
}

.help-back:disabled {
  opacity: 0.3;
  cursor: default;
}

.help-close {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 1.1rem;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  line-height: 1;
}

.help-close:hover {
  color: var(--parchment);
  background: var(--border);
}

.help-search-results {
  padding: 0.75rem 1rem;
  overflow-y: auto;
  flex: 1;
}

.help-result-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.help-result-item {
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  border-radius: 4px;
  color: var(--parchment-dim);
  font-size: 0.95rem;
}

.help-result-item:hover {
  background: var(--card);
  color: var(--gold);
}

.help-no-results {
  color: var(--muted);
  font-size: 0.9rem;
}

.help-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
}

.help-loading,
.help-error {
  color: var(--muted);
  font-style: italic;
}

.help-error {
  color: var(--red);
}

/* Markdown typography */
.help-markdown :deep(h1) {
  font-family: 'Cinzel', serif;
  color: var(--gold);
  font-size: 1.5rem;
  margin: 0 0 0.75rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.4rem;
}

.help-markdown :deep(h2) {
  font-family: 'Cinzel', serif;
  color: var(--gold-light);
  font-size: 1.15rem;
  margin: 1.25rem 0 0.5rem;
}

.help-markdown :deep(h3) {
  color: var(--parchment);
  font-size: 1rem;
  margin: 1rem 0 0.4rem;
}

.help-markdown :deep(p) {
  color: var(--parchment-dim);
  line-height: 1.65;
  margin: 0.5rem 0;
}

.help-markdown :deep(a) {
  color: var(--gold);
  text-decoration: underline;
  cursor: pointer;
}

.help-markdown :deep(a:hover) {
  color: var(--gold-light);
}

.help-markdown :deep(ul),
.help-markdown :deep(ol) {
  padding-left: 1.5rem;
  color: var(--parchment-dim);
}

.help-markdown :deep(li) {
  margin: 0.25rem 0;
}

.help-markdown :deep(code) {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 0.1rem 0.35rem;
  font-size: 0.88em;
  color: var(--parchment);
}

.help-markdown :deep(strong) {
  color: var(--parchment);
}

.help-markdown :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.75rem 0;
}

.help-markdown :deep(th) {
  background: var(--card);
  color: var(--gold);
  border: 1px solid var(--border);
  padding: 0.4rem 0.75rem;
  text-align: left;
}

.help-markdown :deep(td) {
  border: 1px solid var(--border);
  padding: 0.35rem 0.75rem;
  color: var(--parchment-dim);
}

.help-markdown :deep(tr:nth-child(even) td) {
  background: rgba(255, 255, 255, 0.02);
}

.help-markdown :deep(img) {
  max-width: 100%;
  border-radius: 4px;
  margin: 0.5rem 0;
}

.help-markdown :deep(blockquote) {
  border-left: 3px solid var(--gold-dim);
  margin: 0.75rem 0;
  padding: 0.25rem 0 0.25rem 1rem;
  color: var(--muted);
  font-style: italic;
}

.help-markdown :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1rem 0;
}
</style>
