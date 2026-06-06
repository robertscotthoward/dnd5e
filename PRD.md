# Product Requirements Document (PRD): D&D 5e Agentic Campaign Engine

## 1. Overview

This application is a multi-agent Dungeons & Dragons 5e campaign engine. A local LLM (`qwen2.5:14b` via Ollama) drives a Dungeon Master agent and individual player agents through a persistent, rule-driven world. The world is modeled as a YAML object hierarchy spanning geography, characters, and items. A Vue.js web frontend provides a multi-player chat interface, character creation, and admin tooling.

## 2. Technical Stack

- **Language:** Python 3.12
- **Package Manager:** `uv`
- **CLI Framework:** Typer
- **AI / RAG:** LlamaIndex, ChromaDB, Ollama (`qwen2.5:14b`)
- **Graph DB:** Memgraph (`bolt://localhost:7687`)
- **Data / NLP:** networkx, spacy, pyvis, pydantic, markdown-it-py
- **Frontend:** Vue 3, Vite, PrimeVue, Tailwind CSS
- **Auth:** username/password (salted+hashed), HTTP-only JWT cookie
- **Realtime:** WebSocket chat
- **Persistence:** YAML campaign files under `data/campaigns/`

## 3. Functional Requirements

### 3.1 CLI Commands

```
python -m src.backend.main index-corpus
python -m src.backend.main new-campaign "MyAdventure"
python -m src.backend.main turn --campaign "MyAdventure.yaml"
```

- `index-corpus` — Ingests `data/corpus/` D&D 5e markdown files into ChromaDB.
- `new-campaign` — Generates four PCs, a party, a world YAML, and seeds Memgraph.
- `turn` — Advances the campaign one game round through the DM agent.

### 3.2 World Model

The world is a YAML file with `name`, `max_id`, `delete_ids`, and `objects` (dict keyed by int ID). Every object has: `id`, `parent`, `type`, `name`, `description`, `location [x,y,z]`, `size [l,w,h]`, `weight`, `cost`, `is_moveable`, `is_virtual`. Only tools may mutate world state.

**Object tools:**
- `create_object(type, parent_id, **args)`
- `move_object(id, parent_id)`
- `set_object_property(id, name, value)`
- `add_hp(id, delta)`
- `delete_object(id, cascade: bool)`
- `get_object(id)`

**Library functions:**
- `get_sub_world(world, id)` — Returns a filtered world visible to a character.

### 3.3 Agents

- **DM Agent** — Orchestrates events, enforces rules, calls tools to mutate state.
- **PC Agent** — Acts in the player's best interest given personality and disposition.
- **NPC Agent** — Controls monsters and townfolk; responds to DM directives.
- **World Agent** — Autonomous world events (weather, theft, NPC movement).

### 3.4 Game Modes (Pillars of Adventure)

- Exploration — Party queries DM about surroundings.
- Social Interaction — Party talks with NPCs.
- Travel — Automatic movement between locations.
- Combat — Initiative order; attack rolls; saving throws; hp tracking.

### 3.5 Web Application

**Authentication:**
- Register (username + password stored in `cache/users.json`, salted+hashed).
- Login with persistent HTTP-only cookie.

**Campaign Lobby:**
- List available campaigns; join as a new or returning character.
- Character creation: choose region, race, class, name; AI-generated background; dice roll for attributes with re-roll and bonus point allocation.
- Returning players receive a DM narrative recap.

**Game View:**
- Campaign name, party member list with hp/encumbrance/health bars (green→yellow→red).
- Real-time WebSocket chat visible to all party members.
- Chat lines prefixed with speaker name; DM lines prefixed `DM:`.
- Context-sensitive action buttons (Attack, Cast Spell, Dash, etc.) disabled based on character state with tooltips.
- Combat enforces turn order; DM only processes the active player's command.

**Snapshots (Save/Restore):**
- Any party member can snapshot the campaign folder.
- Snapshots form a parent–child tree under `campaigns/<name>/campaigns/`.

**Admin (`/admin`):**
- Accessible only to users with `admin: true`.
- Lists all campaigns with delete (zip-before-delete) and player management.
- Left nav bar with "Console" link.
- World tree view at `/admin/world/<name>`: expandable tree, click to inspect object details in a side panel, right-click context menu to create child objects or delete.
- Character creation from admin rolls attributes automatically.

**Profile Dropdown:**
- Admin link (admin users only).
- Logout.

### 3.6 Other Requirements

- Fixed seed per campaign for reproducible runs; seed logged each turn and major random events.
- Visibility: LOS, range, occlusion, light/dark; perception checks (passive and active).
- Currency: cp=1, sp=10, ep=50, gp=100, pp=1000; 50 coins = 1 lb.

## 4. User Stories

- **As a player**, I want to create a character with rolled attributes so I can join a campaign immediately.
- **As a player**, I want a real-time chat window so I can interact with the DM and other players.
- **As a player**, I want context-sensitive action buttons so I know what I can do on my turn.
- **As the DM (AI)**, I want a filtered world snapshot so I only process what is visible to the party.
- **As an admin**, I want to inspect and edit the world tree so I can fix corrupt campaign state.

## Ad-hoc & Experimental Features

### F1 Help Wiki (Added: 2026-06-05)
- **Context / Why**: Players need in-game guidance on controls, rules, and interface features without leaving the app. A keyboard shortcut makes help instantly accessible from any screen.
- **Purpose / What**: Pressing F1 opens a full-screen help overlay that renders a wiki built from Markdown files rooted at `docs/help/home.md`. The wiki supports internal relative links, images, and a keyword search bar. Players can click through topic pages or search for specific content.
- **Usage / How**: Press F1 (or Escape to close) from anywhere in the app. The overlay renders `docs/help/home.md` as the landing page. Relative Markdown links (e.g., `[Combat](combat.md)`) navigate within the wiki. Images referenced relative to `docs/help/` render inline. The search bar at the top filters across all `.md` files under `docs/help/` and lists matching pages; clicking a result opens that page.

## 5. Success Criteria

1. `index-corpus` indexes all markdown files in `data/corpus/` without errors.
2. `new-campaign "Test"` creates `data/campaigns/Test/world.yaml` with four PCs and one party.
3. `turn --campaign Test` produces narrative output and updates `world.yaml`.
4. A browser at `localhost:5173` allows registration, login, campaign join, and chat.
5. The admin world tree renders all objects and supports right-click create and delete.
6. Snapshots create a nested folder structure and restore correctly.
