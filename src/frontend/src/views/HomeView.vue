<template>
  <div class="home-page">
    <!-- ===================== HERO SECTION ===================== -->
    <section class="hero-section stars-bg">
      <div class="hero-content">
        <!-- D20 Icon -->
        <div class="hero-d20-wrapper">
          <svg
            class="hero-d20 d20-slow-spin"
            viewBox="0 0 80 80"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <polygon
              points="40,5 73,22 73,58 40,75 7,58 7,22"
              stroke="#c9a227"
              stroke-width="2"
              fill="none"
              opacity="0.9"
            />
            <line x1="40" y1="5"  x2="40" y2="32" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
            <line x1="73" y1="22" x2="40" y2="32" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
            <line x1="73" y1="58" x2="40" y2="32" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
            <line x1="40" y1="75" x2="40" y2="32" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
            <line x1="7"  y1="58" x2="40" y2="32" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
            <line x1="7"  y1="22" x2="40" y2="32" stroke="#c9a227" stroke-width="1.2" opacity="0.5"/>
            <text
              x="40" y="36"
              text-anchor="middle"
              dominant-baseline="middle"
              fill="#c9a227"
              font-size="18"
              font-family="Cinzel, serif"
              font-weight="700"
            >20</text>
          </svg>
        </div>

        <!-- Title -->
        <h1 class="hero-title">D&amp;D 5e AI Game Engine</h1>
        <p class="hero-subtitle">
          Forge your legend. An AI Dungeon Master awaits.
        </p>

        <!-- CTA Buttons -->
        <div class="hero-ctas">
          <RouterLink
            :to="authStore.isLoggedIn ? '/campaigns' : '/login'"
            class="dnd-button hero-cta-primary"
          >
            ⚔ Enter the Realm
          </RouterLink>
          <a href="#features" class="dnd-button-ghost hero-cta-secondary">
            Learn More ↓
          </a>
        </div>
      </div>

      <!-- Decorative bottom divider -->
      <div class="hero-divider"></div>
    </section>

    <!-- ===================== FEATURES SECTION ===================== -->
    <section id="features" class="features-section">
      <h2 class="section-title">What Awaits You</h2>
      <div class="gold-divider"></div>

      <div class="features-grid">
        <div class="feature-card dnd-panel">
          <div class="feature-icon">🧙</div>
          <h3 class="feature-title">AI Dungeon Master</h3>
          <p class="feature-desc">
            An intelligent DM narrates your story, responds to your actions,
            and breathes life into NPCs. No two adventures are the same.
          </p>
        </div>

        <div class="feature-card dnd-panel">
          <div class="feature-icon">🌍</div>
          <h3 class="feature-title">Living World</h3>
          <p class="feature-desc">
            A dynamic world that evolves with each turn. Weather changes, NPCs
            move, events unfold organically based on your party's choices.
          </p>
        </div>

        <div class="feature-card dnd-panel">
          <div class="feature-icon">⚔</div>
          <h3 class="feature-title">Real-time Adventure</h3>
          <p class="feature-desc">
            Multiple players, live chat, and instant combat resolution. Your
            party's fate unfolds in real time across exploration, social, and combat.
          </p>
        </div>
      </div>
    </section>

    <!-- ===================== HOW TO PLAY SECTION ===================== -->
    <section class="how-section">
      <h2 class="section-title">How to Play</h2>
      <div class="gold-divider"></div>

      <div class="steps-flow">
        <div class="how-step">
          <div class="how-step-number">1</div>
          <div class="how-step-icon">🔑</div>
          <h4 class="how-step-title">Register &amp; Login</h4>
          <p class="how-step-desc">Create your account and enter the realm.</p>
        </div>

        <div class="how-arrow">→</div>

        <div class="how-step">
          <div class="how-step-number">2</div>
          <div class="how-step-icon">🗺</div>
          <h4 class="how-step-title">Create or Join a Campaign</h4>
          <p class="how-step-desc">Start a new adventure or join an existing one.</p>
        </div>

        <div class="how-arrow">→</div>

        <div class="how-step">
          <div class="how-step-number">3</div>
          <div class="how-step-icon">🛡</div>
          <h4 class="how-step-title">Create Your Character</h4>
          <p class="how-step-desc">Choose race, class, and let the AI craft your backstory.</p>
        </div>

        <div class="how-arrow">→</div>

        <div class="how-step">
          <div class="how-step-number">4</div>
          <div class="how-step-icon">⚔</div>
          <h4 class="how-step-title">Begin Your Adventure</h4>
          <p class="how-step-desc">Step into the world and let destiny unfold.</p>
        </div>
      </div>

      <div class="how-cta">
        <RouterLink
          :to="authStore.isLoggedIn ? '/campaigns' : '/login'"
          class="dnd-button"
          style="font-size: 1rem; padding: 0.75rem 2.5rem;"
        >
          Begin Your Adventure
        </RouterLink>
      </div>
    </section>

    <!-- ===================== FOOTER ===================== -->
    <footer class="site-footer">
      <div class="footer-d20">
        <svg viewBox="0 0 30 30" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:24px;height:24px;opacity:0.5">
          <polygon points="15,2 28,9 28,21 15,28 2,21 2,9" stroke="#c9a227" stroke-width="1.5" fill="none"/>
          <text x="15" y="17" text-anchor="middle" dominant-baseline="middle" fill="#c9a227" font-size="7" font-family="Cinzel, serif" font-weight="700">20</text>
        </svg>
      </div>
      <p class="footer-text">
        D&amp;D 5e AI Game Engine &bull; Built with FastAPI + Vue.js
      </p>
      <p class="footer-sub">
        An AI-powered tabletop RPG experience
      </p>
    </footer>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
</script>

<style scoped>
.home-page {
  min-height: 100vh;
}

/* ===== HERO ===== */
.hero-section {
  min-height: 85vh;
  background: radial-gradient(ellipse at center top, #1a0e00 0%, #120a00 40%, #0d0a06 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  position: relative;
  padding: 4rem 2rem 5rem;
}

.hero-content {
  position: relative;
  z-index: 1;
  max-width: 700px;
  margin: 0 auto;
}

.hero-d20-wrapper {
  margin-bottom: 1.5rem;
  display: flex;
  justify-content: center;
}

.hero-d20 {
  width: 80px;
  height: 80px;
  filter: drop-shadow(0 0 16px rgba(201,162,39,0.7));
}

.hero-title {
  font-family: 'Cinzel', serif;
  font-size: clamp(1.8rem, 5vw, 3.2rem);
  font-weight: 700;
  color: #c9a227;
  margin-bottom: 0.75rem;
  text-shadow: 0 0 30px rgba(201,162,39,0.4), 0 2px 4px rgba(0,0,0,0.8);
  letter-spacing: 0.03em;
  line-height: 1.15;
}

.hero-subtitle {
  font-family: 'Crimson Text', serif;
  font-size: 1.35rem;
  color: #e8d5b7;
  font-style: italic;
  margin-bottom: 2.5rem;
  opacity: 0.9;
}

.hero-ctas {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

.hero-cta-primary {
  font-size: 1rem;
  padding: 0.75rem 2rem;
  text-decoration: none;
}

.hero-cta-secondary {
  font-size: 1rem;
  padding: 0.75rem 2rem;
  text-decoration: none;
}

.hero-divider {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(to right, transparent, #7a6115, #c9a227, #7a6115, transparent);
}

/* ===== FEATURES ===== */
.features-section {
  padding: 5rem 2rem;
  max-width: 1100px;
  margin: 0 auto;
}

.section-title {
  font-family: 'Cinzel', serif;
  font-size: 2rem;
  font-weight: 700;
  color: #c9a227;
  text-align: center;
  margin-bottom: 0.5rem;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  margin-top: 2rem;
}
@media (max-width: 768px) {
  .features-grid { grid-template-columns: 1fr; }
}

.feature-card {
  text-align: center;
  padding: 2rem 1.5rem;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 0 24px rgba(201,162,39,0.35);
}

.feature-icon {
  font-size: 2.5rem;
  margin-bottom: 1rem;
  display: block;
}

.feature-title {
  font-family: 'Cinzel', serif;
  font-size: 1.15rem;
  font-weight: 600;
  color: #c9a227;
  margin-bottom: 0.75rem;
}

.feature-desc {
  color: #e8d5b7;
  font-size: 1rem;
  line-height: 1.6;
}

/* ===== HOW TO PLAY ===== */
.how-section {
  padding: 4rem 2rem 5rem;
  background: linear-gradient(to bottom, #0d0a06, #110d05);
}

.steps-flow {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 0;
  flex-wrap: wrap;
  max-width: 1000px;
  margin: 2rem auto 0;
}

.how-step {
  flex: 1;
  min-width: 160px;
  max-width: 200px;
  text-align: center;
  padding: 1.5rem 1rem;
  position: relative;
}

.how-step-number {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #7a6115, #c9a227);
  color: #1a0e00;
  font-family: 'Cinzel', serif;
  font-weight: 700;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 0.75rem;
  box-shadow: 0 0 12px rgba(201,162,39,0.4);
}

.how-step-icon {
  font-size: 2rem;
  display: block;
  margin-bottom: 0.5rem;
}

.how-step-title {
  font-family: 'Cinzel', serif;
  font-size: 0.9rem;
  font-weight: 600;
  color: #c9a227;
  margin-bottom: 0.5rem;
}

.how-step-desc {
  font-size: 0.9rem;
  color: #8a7355;
  line-height: 1.5;
}

.how-arrow {
  font-size: 1.5rem;
  color: #7a6115;
  display: flex;
  align-items: center;
  padding-top: 2rem;
  flex-shrink: 0;
}
@media (max-width: 640px) {
  .how-arrow { display: none; }
}

.how-cta {
  display: flex;
  justify-content: center;
  margin-top: 3rem;
}

/* ===== FOOTER ===== */
.site-footer {
  background: #0a0703;
  border-top: 1px solid #3d2e10;
  padding: 2rem;
  text-align: center;
}

.footer-d20 {
  display: flex;
  justify-content: center;
  margin-bottom: 0.5rem;
}

.footer-text {
  font-family: 'Cinzel', serif;
  font-size: 0.8rem;
  color: #8a7355;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.footer-sub {
  font-family: 'Crimson Text', serif;
  font-size: 0.85rem;
  color: #5a4530;
  font-style: italic;
  margin: 0;
}
</style>
