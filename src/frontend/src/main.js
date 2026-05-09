import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import router from './router'
import App from './App.vue'
import './assets/css/main.css'
import 'primeicons/primeicons.css'

import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: 'html',
    },
  },
})

// Restore the session BEFORE installing the router.
// Navigation guards run on the first mount, so auth state must be
// populated before then — otherwise direct links to guarded routes
// like /admin see isLoggedIn=false and redirect to /login.
const authStore = useAuthStore()
authStore.fetchMe().then(() => {
  app.use(router)
  app.mount('#app')
})
