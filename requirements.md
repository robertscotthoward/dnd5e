# Requirements: D&D 5e Agentic Campaign Engine

## Core Goal

Build a multi-agent D&D 5e campaign engine driven by a local LLM. The system uses a D&D 5e corpus (markdown) as a knowledge base, a persistent YAML world model, and a set of agents (DM, PC, NPC, World) to simulate a living campaign.

## CLI

- `index-corpus` — Index `data/corpus/` markdown files into ChromaDB.
- `new-campaign <name>` — Create a new campaign: four PCs, one party, a world YAML seeded with canonical D&D geography.
- `turn --campaign <file>` — Advance one turn through the DM agent; persist world state after each turn.

## World Model

- World stored as `data/campaigns/<name>/world.yaml`.
- All objects in a flat dict keyed by integer ID; parent/child hierarchy via `parent` field.
- Object schema: `id`, `parent`, `type`, `name`, `description`, `location`, `size`, `weight`, `cost`, `is_moveable`, `is_virtual`.
- Player schema adds: `race`, `classes`, `abilities` (str/int/wis/dex/con/chr), `hp`, `mana`, `health`.
- Only tool calls mutate world state; no direct dict writes from agent prose.
- `get_sub_world(world, id)` filters the world to only visible objects for a given character.

## Agents

- **DM** — Drives the narrative; calls tools to apply all state changes.
- **PC** — Responds as a character with personality and disposition.
- **NPC** — Monsters and townfolk controlled by DM directives.
- **World** — Background events (weather, NPC movement, items disappearing).

## Game Modes

- Exploration, Social Interaction, Travel, Combat.
- Combat enforces initiative order, attack rolls, saving throws.

## AI Stack

- LlamaIndex for RAG over corpus.
- ChromaDB as the vector store.
- Ollama `qwen2.5:14b` for tool-calling.
- Memgraph (`bolt://localhost:7687`) for graph relationships.
- networkx, spacy, pyvis for analysis and visualization.

## Web Frontend

- Vue 3 + Vite + PrimeVue + Tailwind CSS.
- Auth: register/login with salted+hashed passwords in `cache/users.json`; HTTP-only JWT cookie.
- Campaign lobby: list campaigns, join, character creation (dice roll, re-roll, bonus allocation, AI background).
- Game view: party health bars, WebSocket chat, speaker-prefixed messages, context-sensitive action buttons.
- Snapshots: save/restore campaign state; snapshots form a nested folder tree.
- Admin page (`/admin`, admin-only): campaign management, world tree inspector, right-click create/delete, character attribute rolling.

## Non-Functional

- Fixed seed per campaign; log seed each turn.
- Visibility: LOS, range, occlusion, light/dark, perception checks.
- Currency system: cp/sp/ep/gp/pp with weight rules.
