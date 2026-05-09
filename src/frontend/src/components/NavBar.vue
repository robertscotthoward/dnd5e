<template>
  <nav class="navbar">
    <!-- Left: Logo + Title -->
    <div class="navbar-left">
      <RouterLink to="/" class="navbar-brand">
        <svg class="d20-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
          <polygon
            points="20,3 37,14 37,26 20,37 3,26 3,14"
            stroke="#c9a227"
            stroke-width="1.5"
            fill="none"
          />
          <line x1="20" y1="3"  x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="37" y1="14" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="37" y1="26" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="20" y1="37" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="3"  y1="26" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
          <line x1="3"  y1="14" x2="20" y2="15" stroke="#c9a227" stroke-width="1" opacity="0.6"/>
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

        <!-- Profile dropdown -->
        <div class="profile-menu" ref="profileMenuRef">
          <button class="profile-trigger" @click.stop="toggleDropdown" :class="{ active: dropdownOpen }">
            <div class="user-avatar">{{ userInitial }}</div>
            <span class="user-name">{{ authStore.user?.username }}</span>
            <span class="chevron" :class="{ open: dropdownOpen }">▾</span>
          </button>

          <div v-if="dropdownOpen" class="profile-dropdown">
            <RouterLink
              v-if="authStore.isAdmin"
              to="/admin"
              class="dropdown-item"
              @click="dropdownOpen = false"
            >
              ⚙ Admin
            </RouterLink>
            <div v-if="authStore.isAdmin" class="dropdown-divider"></div>
            <button class="dropdown-item dropdown-item-logout" @click="handleLogout">
              ↩ Logout
            </button>
          </div>
        </div>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const router = useRouter()

const dropdownOpen = ref(false)
const profileMenuRef = ref(null)

const userInitial = computed(() => {
  return authStore.user?.username?.charAt(0)?.toUpperCase() || '?'
})

function toggleDropdown() {
  dropdownOpen.value = !dropdownOpen.value
}

function closeDropdown(e) {
  if (profileMenuRef.value && !profileMenuRef.value.contains(e.target)) {
    dropdownOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', closeDropdown))
onUnmounted(() => document.removeEventListener('click', closeDropdown))

async function handleLogout() {
  dropdownOpen.value = false
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

/* ===== Profile dropdown ===== */
.profile-menu {
  position: relative;
}

.profile-trigger {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: none;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 0.25rem 0.5rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.profile-trigger:hover,
.profile-trigger.active {
  border-color: #3d2e10;
  background: rgba(201,162,39,0.06);
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
  flex-shrink: 0;
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

.chevron {
  font-size: 0.75rem;
  color: #7a6115;
  line-height: 1;
  transition: transform 0.2s ease;
  display: inline-block;
}
.chevron.open {
  transform: rotate(180deg);
}

.profile-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 160px;
  background: linear-gradient(to bottom, #1a1109, #150f06);
  border: 1px solid #7a6115;
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6), 0 0 0 1px rgba(201,162,39,0.08);
  overflow: hidden;
  z-index: 200;
}

.dropdown-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 0.6rem 1rem;
  font-family: 'Cinzel', serif;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #c9a227;
  text-decoration: none;
  background: none;
  border: none;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
  text-align: left;
}
.dropdown-item:hover {
  background: rgba(201,162,39,0.1);
  color: #e8d5b7;
}

.dropdown-divider {
  height: 1px;
  background: #3d2e10;
  margin: 0;
}

.dropdown-item-logout {
  color: #f87171;
}
.dropdown-item-logout:hover {
  background: rgba(248,113,113,0.1);
  color: #fca5a5;
}

/* ===== Login button ===== */
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
