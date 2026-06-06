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
- **Purpose / What**: Pressing F1 opens a full-screen help overlay that renders a wiki built from Markdown files rooted at `docs/help/home.md`. The wiki supports internal relative links, images, a keyword search bar, and browser-style back navigation via Backspace.
- **Usage / How**: Press F1 (or Escape to close) from anywhere in the app. The overlay renders `docs/help/home.md` as the landing page. Relative Markdown links (e.g., `[Combat](combat.md)`) navigate within the wiki. Pressing Backspace returns to the previously visited page (stack-based history); at `home.md` Backspace has no effect. Images referenced relative to `docs/help/` render inline. The search bar at the top filters across all `.md` files under `docs/help/` and lists matching pages; clicking a result opens that page.

### ESC to Close All Dialogs (Added: 2026-06-05)
- **Context / Why**: Several dialogs — CharacterSheet, LootSummary, ActionBar long-rest confirm, GameView snapshot/restore modals — have no ESC handler. WorldMap declares `@keydown.esc` on its overlay div but that div must hold DOM focus to fire, so ESC silently fails unless the user first clicks the map. The pattern must be consistent: every dismissible dialog closes on ESC without requiring mouse interaction first.
- **Purpose / What**: A global `window` keydown listener in `App.vue` dispatches ESC to whichever dialog is topmost and visible. `LevelUpDialog` is excluded — it requires the player to complete the flow before dismissing.
- **Usage / How**: Press ESC from anywhere in the app to dismiss the frontmost open dialog. Priority order (highest to lowest): HelpOverlay, WorldMap, CharacterSheet, LootSummary, ActionBar long-rest confirm, GameView snapshot modal, GameView restore confirm modal.

### Lazy Recursive LOS-Driven World Expansion (Added: 2026-06-05)
- **Context / Why**: The Phase 16 generator populates tiles on first sight, but several critical behaviors are missing. Revisiting a coordinate that was "seen but empty" re-runs generation, risking duplicates. Large containers (villages, buildings) have no mechanism to generate children lazily — their interiors spawn all at once. The world map has no persistent fog-of-war that survives across turns. These gaps break immersion and correctness.
- **Purpose / What**: Every coordinate visible via LOS that lacks any world object receives, at minimum, a `ground` object. That `ground` object is the generator's permanent "nothing here" marker — on every future visit, the presence of any object (even bare ground) prevents re-generation at that coordinate. Large parent objects (villages, dungeons, buildings) are placed as shells with `generated: false` on their interior coordinates; LOS reaching any ungenerated coordinate inside a parent triggers child-fill for that parent only, recursively expanding inward. Entering through a door object is the canonical trigger for interior child generation: crossing a door's threshold spawns the full interior layout (furniture, NPCs, containers) one level deep. The world map tracks a per-session `explored` bitfield — tiles the player has had LOS on stay fully revealed; all other tiles render as dark fog. Fixed objects (walls, terrain, furniture) are permanent; mobile objects (`mobile: true`) are exempt from the "object present = skip generation" rule and are re-simulated each turn by the World Agent.
- **Usage / How**: No player action required. Each DM turn and each WS move event: (1) compute LOS for the moving player, (2) for every visible coordinate lacking any object, call `WorldGenerator.fill_coordinate(coord, context)` which writes a `ground` or richer object to `world.yaml`, (3) for any LOS coordinate inside a `generated: false` parent, call `WorldGenerator.fill_children(parent_id)` which populates immediate children and marks the parent `generated: true`, (4) broadcast the world delta to all clients, (5) update the player's session `explored` set. The frontend `WorldMap.vue` renders the fog-of-war layer from the session `explored` set — explored tiles clear, unexplored tiles dark, partial-visibility tiles dimmed. Door-crossing detection runs in the WS move handler: if the player's new coordinates overlap a door object's bounding box, `fill_children` is called for the door's parent building.

### Procedural World Generator — On-Demand Terrain & Object Population (Added: 2026-06-05)
- **Context / Why**: The world currently relies on pre-authored YAML content. As players explore, unseen coordinates hold nothing — no terrain, no objects, no ground. This creates blank zones on the world map and breaks immersion. The world must feel infinite and fully realized the moment a player's line of sight reaches any coordinate.
- **Purpose / What**: A Python `WorldGenerator` service fills unseen coordinates on demand. Every tile within a player's LOS that has no world object is immediately populated — at minimum with a `ground` object — so no coordinate is ever empty after being seen. Large features (village, forest, dungeon) are placed as a single parent object with coordinates and bounds, but their child contents (pub interior, tree cluster, room contents) remain ungenerated until LOS reaches those child coordinates. This lazy, recursive generation ensures the pub exists and has a visible door before the player enters, but the bar stools, patrons, and bottles only exist once the player steps inside. Generated content is persisted to `world.yaml` immediately so it is stable across sessions and shared between players. Fixed objects (terrain, buildings) are permanent; mobile objects (NPCs, wandering creatures) are flagged `mobile: true` and may be re-simulated each turn.
- **Usage / How**: Generation triggers automatically server-side whenever the DM agent processes a turn or a player moves. The `get_sub_world` visibility call identifies visible coordinates; any coordinate lacking a world object is passed to `WorldGenerator.fill(coords, context)`. Results are written to `world.yaml` and pushed to clients via the existing WS broadcast. The world map in the frontend reflects newly generated tiles in the player's session fog-of-war layer — explored tiles stay revealed; unexplored tiles remain dark until LOS reaches them.

## 5. Success Criteria

1. `index-corpus` indexes all markdown files in `data/corpus/` without errors.
2. `new-campaign "Test"` creates `data/campaigns/Test/world.yaml` with four PCs and one party.
3. `turn --campaign Test` produces narrative output and updates `world.yaml`.
4. A browser at `localhost:5173` allows registration, login, campaign join, and chat.
5. The admin world tree renders all objects and supports right-click create and delete.
6. Snapshots create a nested folder structure and restore correctly.
