<template>
  <div class="quest-tracker">
    <div v-if="quests.length === 0" class="quest-empty">
      No active quests.
    </div>
    <div v-else class="quest-list">
      <div v-for="quest in quests" :key="quest.id" class="quest-card">
        <div class="quest-title">{{ quest.title }}</div>
        <ul class="milestone-list">
          <li
            v-for="(ms, idx) in quest.milestones"
            :key="idx"
            class="milestone-item"
            :class="{ completed: ms.completed }"
            @click="toggleMilestone(quest.id, idx, ms.completed)"
            :title="ms.completed ? 'Completed' : 'Click to complete'"
          >
            <span class="milestone-check">{{ ms.completed ? '☑' : '☐' }}</span>
            <span class="milestone-text">{{ ms.text }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useCampaignStore } from '../stores/campaign'

const campaignStore = useCampaignStore()
const quests = computed(() => campaignStore.quests)

function toggleMilestone(questId, milestoneIdx, alreadyCompleted) {
  if (alreadyCompleted) return
  campaignStore.sendCompleteMilestone(questId, milestoneIdx)
}
</script>

<style scoped>
.quest-tracker {
  display: flex;
  flex-direction: column;
}

.quest-empty {
  font-family: 'Crimson Text', serif;
  font-style: italic;
  color: #5a4530;
  font-size: 0.82rem;
}

.quest-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.quest-card {
  background: #1a1109;
  border: 1px solid #3d2e10;
  border-left: 3px solid #7a6115;
  border-radius: 3px;
  padding: 0.5rem 0.6rem;
}

.quest-title {
  font-family: 'Cinzel', serif;
  font-size: 0.72rem;
  font-weight: 600;
  color: #c9a227;
  letter-spacing: 0.04em;
  margin-bottom: 0.4rem;
}

.milestone-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.milestone-item {
  display: flex;
  align-items: flex-start;
  gap: 0.35rem;
  cursor: pointer;
  border-radius: 2px;
  padding: 0.15rem 0.2rem;
  transition: background 0.1s;
}

.milestone-item:hover:not(.completed) {
  background: rgba(201, 162, 39, 0.07);
}

.milestone-item.completed {
  cursor: default;
  opacity: 0.55;
}

.milestone-check {
  font-size: 0.75rem;
  color: #c9a227;
  flex-shrink: 0;
  line-height: 1.4;
}

.milestone-text {
  font-family: 'Crimson Text', serif;
  font-size: 0.82rem;
  color: #e8d5b7;
  line-height: 1.35;
}

.milestone-item.completed .milestone-text {
  text-decoration: line-through;
  color: #8a7355;
}
</style>
