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

### Server-Down Toast Notification (Added: 2026-06-05)
- **Context / Why**: When the backend goes offline, user actions (chat, Investigate, Attack, snapshots) silently fail with no feedback. Players have no idea whether their command was received or dropped.
- **Purpose / What**: A persistent toast banner appears at the top of the screen whenever the WebSocket is disconnected or in error state, or when any HTTP fetch fails with a network error. Any user action attempted while the server is down shows the toast immediately. The toast auto-dismisses 3 seconds after the connection is restored.
- **Usage / How**: No player action required. The toast appears automatically on disconnect and on any failed action. It reads "Server unreachable — your action was not sent. Reconnecting…" with a reconnect button. Once the WS reconnects successfully the banner fades out.

### Build Info Tooltip on Nav Title (Added: 2026-06-05)
- **Context / Why**: Developers and players need a quick way to confirm which build is running without opening a terminal or checking git. Surfacing this on the logo hover keeps it discoverable without cluttering the UI. Adding the last 5 commit messages gives immediate changelog context without leaving the app.
- **Purpose / What**: Hovering the upper-left title/logo in the navbar shows a tooltip with the first 10 characters of the last git commit hash, the commit date/time, the committer's name, and a list of the last 5 commit messages (each prefixed with its short hash). The backend `/api/build-info` endpoint returns all of this in a single cached response.
- **Usage / How**: Hover over the "D&D 5e / AI Game Engine" logo in the top-left navbar. A tooltip appears below showing the HEAD commit line followed by a divider and the 5 most recent commit subjects, e.g. `53e19affd1 · 2026-06-05 21:15 · Rob Howard` then a list of recent commits. No interaction required beyond hover.

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

### DM ReAct Tool Execution — Silent Action Loop (Added: 2026-06-06)
- **Context / Why**: The LlamaIndex `ReActAgent` with Ollama outputs its internal `Thought / Action / Action Input` reasoning chain as raw chat text. Players see the DM's unexecuted tool calls instead of world mutations happening silently and a clean narration being delivered. The world never updates because the tools are never actually called — they are only described.
- **Purpose / What**: Replace the LlamaIndex `ReActAgent` with a hand-rolled ReAct loop that drives the Ollama LLM directly. The loop parses `Action:` / `Action Input:` blocks from the model's output, dispatches them as real Python tool calls on `WorldTools`, feeds `Observation:` results back into the prompt, and iterates until the model emits a `Final Answer:` with no further actions. Only the final answer text reaches the chat broadcast — all intermediate reasoning is suppressed.
- **Usage / How**: Transparent to players. The DM chat message contains only narrative prose. World state (new objects, HP changes, moved items) updates immediately after each tool call within the loop. If the model loops more than 10 iterations without a final answer, the last narration fragment is broadcast with a `[DM]` prefix.

### Admin World Reset — Keep Players (Added: 2026-06-06)
- **Context / Why**: During development the procedurally generated world accumulates stale or broken state (misplaced tiles, bad BSP trees, corrupted layout). Deleting the entire campaign loses player progress. A targeted reset is needed that wipes generated terrain and world objects while leaving player characters — their stats, inventory, and progression — completely intact.
- **Purpose / What**: A single admin action in `/admin` regenerates the campaign's world hierarchy from scratch (system → planet → continent → region → town → inn → common room), then re-attaches all existing PC objects under a new party in the common room. The original seed, turn number, and campaign metadata are preserved. Existing players.json entries are untouched.
- **Usage / How**: In the Admin Console, each campaign card has a "Reset World" button (amber/orange, distinct from the red delete button). Clicking it opens a confirmation dialog: "Reset world for '{name}'? All generated terrain, items, and locations will be erased. Player characters will be preserved." Confirming POSTs to `/api/admin/campaigns/{id}/reset-world`, which performs the rebuild server-side and returns the new world object count. The UI refreshes the campaign list after success.

### Player Card Location Ancestry (Added: 2026-06-07)
- **Context / Why**: Player cards in the game sidebar show name, HP, and conditions but give no indication of where a character physically is in the world. Without location context, players can't tell if party members are in the same room, a different building, or on a different continent.
- **Purpose / What**: Each player card shows a compact ancestry chain beneath the character name — e.g. "Common Room (room) → Stonehill Inn (inn) → Phandalin (town)" — built by walking the PC's parent chain in the world hierarchy. The chain is populated server-side in `get_players()` and flows through `CampaignPlayer` to the frontend with no extra API round-trip.
- **Usage / How**: Visible automatically on every player card in the game sidebar. Updates whenever the player list refreshes (state poll, WS `players_update` broadcast).

### Map Z-Order and Tooltip Ancestry (Added: 2026-06-07)
- **Context / Why**: The canvas draws all tiles in the order they appear in the server response array. Floors and ground tiles end up on top of walls, walls on top of furniture, and entities underneath ground tiles. The hover hit-test finds the last-painted (topmost-in-array) object — which is the floor — rather than the player circle or furniture that visually appears on top. Additionally, the tooltip shows only `name` and `type`, with no spatial context, making it impossible to tell where in the world hierarchy an object lives.
- **Purpose / What**: Sort the tile draw pass by a defined z-order (ground < floor < wall/door < furniture/NPC/item < player) so top-down rendering matches visual intuition. Reverse the hit-test iteration so the frontmost drawn object wins. Extend the tooltip to walk the parent chain from the full node list and display it as "Common Room (room) → Stonehill Inn (inn) → Phandalin (town)".
- **Usage / How**: Transparent — hovering any tile shows the enriched tooltip automatically. No controls or settings needed.

### Player Icon Map Tooltip Ancestry (Added: 2026-06-07)
- **Context / Why**: Player icons on the world map show no ancestry chain when hovered, while every terrain tile already shows a full location path. The gap exists because the `party` container is stripped from `hierarchyNodes` (it has `show: false`) so the ancestry walk stops immediately when it hits the PC's parent. Players cannot tell from the tooltip where in the world hierarchy their character stands.
- **Purpose / What**: Retain an unfiltered `allHierarchyNodes` lookup in `WorldMap.vue` alongside the display-filtered `hierarchyNodes`. The ancestry chain walk at hover time uses the unfiltered map, so virtual containers (party, system, planet) contribute to the chain without ever being drawn on the canvas.
- **Usage / How**: Hover a player icon (gold circle) on the world map. The tooltip shows the character name and type plus the full ancestry chain — e.g. "Common Room (room) → Stonehill Inn (inn) → Phandalin (town)" — identical to the chain shown for terrain tiles.

### Unique Per-Type Tile Colors on World Map (Added: 2026-06-07)
- **Context / Why**: All traversable tiles (`ground`, `floor`, `wall`, `cobblestone`, `road`, `door`) shared a single brown hex `#6b4a20`, making it impossible to visually distinguish a structural wall from the floor a player stands on. All building types similarly shared one orange. Players had no spatial intuition from the map color alone.
- **Purpose / What**: Replace the 5-color named-palette with a direct `TYPE_COLOR` map that assigns a unique hex to every tile type. Walls become cool gray (`#9aa0a8`), floors warm tan (`#8a6a40`), ground dark dirt (`#5a3e18`), doors amber (`#b07040`). Building subtypes each get a distinct color (temple = pale gold, magic shop = purple, smithy = rust-red, etc.). The map legend gains Wall and Door swatches.
- **Usage / How**: Transparent — open the world map (F4) and each tile type renders its own distinct color. No player action required.

## 5. Success Criteria

1. `index-corpus` indexes all markdown files in `data/corpus/` without errors.
2. `new-campaign "Test"` creates `data/campaigns/Test/world.yaml` with four PCs and one party.
3. `turn --campaign Test` produces narrative output and updates `world.yaml`.
4. A browser at `localhost:5173` allows registration, login, campaign join, and chat.
5. The admin world tree renders all objects and supports right-click create and delete.
6. Snapshots create a nested folder structure and restore correctly.
