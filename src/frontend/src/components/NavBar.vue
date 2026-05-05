<template>
  <nav class="navbar">
    <!-- Left: Logo + Title -->
    <div class="navbar-left">
      <RouterLink to="/" class="navbar-brand">
        <svg class="d20-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
          <!-- Outer pentagon / icosahedron face -->
          <polygon
            points="20,3 37,14 37,26 20,37 3,26 3,14"
            stroke="#c9a227"
            stroke-width="1.5"
            fill="none"
          />
          <!-- Inner lines creating facets -->
          <line x1="20" y1="3"  x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="37" y1="14" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="37" y1="26" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="20" y1="37" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="3"  y1="26" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="3"  y1="14" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <!-- "20" text -->
          <text x="20" y="21" text-anchor="middle" dominant-baseline="middle"
                fill="#c9a227" font-size="9" font-family="Cinzel, serif" font-weight="700">20</text>
        </svg>
        <div class="navbar-title-group">
          <span class="navbar-title">D&amp;D 5e</span>
          <span class="navbar-subtitle">AI Game Engine</span>
        </div>
      </RouterLink>
    </div>

    <!-- Right: Nav links + auth -->
    <div class="navbar-right">
      <template v-if="authStore.isLoggedIn">
        <RouterLink to="/campaigns" class="nav-link">Campaigns</RouterLink>
        <div class="nav-user">
          <div class="user-avatar">{{ userInitial }}</div>
          <span class="user-name">{{ authStore.user?.username }}</span>
        </div>
        <button class="dnd-button-ghost nav-logout-btn" @click="handleLogout">
          Logout
        </button>
      </template>
      <template v-else>
        <RouterLink to="/login" class="dnd-button nav-login-btn">
          Enter Realm
        </RouterLink>
      </template>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const userInitial = computed(() => {
  return authStore.user?.username?.charAt(0)?.toUpperCase() || '?'
})

async function handleLogout() {
  await authStore.logout(router)
}
</script>

<style scoped>
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  height: 64px;
  background: linear-gradient(to bottom, #110d05, #0d0a06);
  border-bottom: 1px solid #7a6115;
  box-shadow: 0 2px 16px rgba(0,0,0,0.6), 0 1px 0 rgba(201,162,39,0.15);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem;
}

.navbar-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
}

.d20-icon {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  filter: drop-shadow(0 0 6px rgba(201,162,39,0.4));
  transition: filter 0.3s ease;
}
.navbar-brand:hover .d20-icon {
  filter: drop-shadow(0 0 12px rgba(201,162,39,0.8));
}

.navbar-title-group {
  display: flex;
  flex-direction: column;
  line-height: 1;
}

.navbar-title {
  font-family: 'Cinzel', serif;
  font-weight: 700;
  font-size: 1.15rem;
  color: #c9a227;
  letter-spacing: 0.06em;
}

.navbar-subtitle {
  font-family: 'Crimson Text', serif;
  font-size: 0.72rem;
  color: #8a7355;
  letter-spacing: 0.04em;
  margin-top: 1px;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.nav-link {
  font-family: 'Cinzel', serif;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #8a7355;
  text-decoration: none;
  text-transform: uppercase;
  transition: color 0.2s ease;
  padding: 0.25rem 0.5rem;
}
.nav-link:hover,
.nav-link.router-link-active {
  color: #c9a227;
}

.nav-user {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #7a6115, #c9a227);
  color: #1a0e00;
  font-family: 'Cinzel', serif;
  font-weight: 700;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #c9a227;
  box-shadow: 0 0 8px rgba(201,162,39,0.3);
}

.user-name {
  font-family: 'Crimson Text', serif;
  font-size: 0.95rem;
  color: #e8d5b7;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-logout-btn {
  font-size: 0.75rem;
  padding: 0.35rem 0.875rem;
}

.nav-login-btn {
  font-size: 0.8rem;
  padding: 0.4rem 1rem;
  text-decoration: none;
}

.navbar-left {
  display: flex;
  align-items: center;
}

@media (max-width: 640px) {
  .navbar-subtitle { display: none; }
  .user-name { display: none; }
  .navbar { padding: 0 1rem; }
}
</style>
