# Tasks: D&D 5e Agentic Campaign Engine

## Phase 1: CLI Entry Point

* [x] **main.py as Typer CLI** — `src/backend/main.py` is a FastAPI app entry; it needs a Typer CLI with `index-corpus`, `new-campaign`, and `turn` commands.
* [x] **`index-corpus` command** — Ingest all markdown files under `data/corpus/` into ChromaDB via LlamaIndex. Report file count and chunk count on completion.
* [x] **`new-campaign <name>` command** — Generate four D&D 5e PCs (randomized race/class/stats), a party, and a seeded world YAML at `data/campaigns/<name>/world.yaml`. Seed is fixed and logged.
* [x] **`turn --campaign <name>` command** — Run one DM agent turn: query rules, update visible world, produce narrative output, persist updated world YAML.

## Phase 2: Agent System

* [x] **DM Agent** — Full tool-calling loop using `qwen2.5:14b` via Ollama. DM receives filtered world, calls tools, produces narrative. Currently `ai_client.generate_dm_response` calls `llm.complete` (no tool loop); upgrade to ReAct agent.
* [x] **PC Agent** — Per-character agent with personality and disposition driving decisions. Currently `generate_player_action` uses bare `complete`; upgrade to an agent that can also call tools.
* [x] **NPC Agent** — Reuse PC agent pattern for monsters/townfolk; controlled by DM directives.
* [x] **World Agent** — Background event generator (weather, NPC movement, item theft) that runs each turn before the DM agent.

## Phase 3: World & Combat

* [x] **Corpus seed data** — Populate `data/corpus/` with D&D 5e markdown files (basic rules: combat, spells, classes, races).
* [x] **Combat mode** — Initiative rolling, turn order enforcement, attack/damage resolution, saving throws. DM agent must queue turns and only advance on current player's tool call.
* [x] **Visibility / `get_sub_world`** — Refine LOS/range/occlusion rules; currently only ancestry+siblings are visible. Add light/dark state and perception check filtering.
* [x] **Seed logging** — Log campaign seed and per-turn random seeds to a `data/campaigns/<name>/seeds.log` file.

## Phase 4: Web — Authentication & Lobby

* [x] **Register / login routes** — Auth routes exist in `auth_routes.py`.
* [x] **Campaign list and join** — `campaign_routes.py` handles listing and joining.
* [x] **Character creation wizard** — `CharacterCreator.vue` implements a multi-step wizard (name, region, race, class, attributes, background).
* [x] **AI-generated background** — Step in CharacterCreator that calls backend to generate a background narrative using the LLM based on region and race. Backend endpoint needed.
* [x] **Returning player DM recap** — On re-join, trigger DM agent to generate a narrative recap of the player's last session. Surface in lobby view.
* [x] **Attribute dice roll UI** — Verify re-roll and bonus point allocation work end-to-end; confirm save persists correct attributes to world.yaml.

## Phase 5: Web — Game View

* [x] **Game layout** — `GameView.vue` has party sidebar, chat area, and action bar.
* [x] **WebSocket chat** — `ws_routes.py` + `ChatWindow.vue` implement real-time multi-player chat.
* [x] **PlayerCard with HP bars** — `PlayerCard.vue` renders hp/encumbrance/health as color-gradient bars.
* [x] **ActionBar** — `ActionBar.vue` renders context-sensitive action buttons per game mode.
* [x] **DM chat integration** — When a player submits a message, the WS handler should invoke the DM agent and broadcast its response as a `DM:` message.
* [x] **Combat turn enforcement** — WS handler must check `activeTurn`; only process the active player's action command during Combat mode; broadcast "waiting for X" to others.
* [x] **Button disable states** — Action buttons should be disabled (with tooltip) based on character state (silenced, unconscious, etc.) pulled from world object properties.

## Phase 6: Web — Snapshots & Admin

* [x] **Snapshot create/list backend** — `campaign_manager.py` has `create_snapshot` / `list_snapshots`.
* [x] **Admin routes** — `admin_routes.py` has campaign list, delete, player remove, world tree.
* [x] **Admin world tree view** — `AdminWorldView.vue` renders expandable tree with detail panel and right-click create/delete.
* [x] **Snapshot restore** — Backend endpoint to restore a campaign to a snapshot state (copy snapshot files back to campaign root). Frontend restore button in snapshot list.
* [x] **Snapshot tree UI** — Display snapshots as a branching tree (parent→child) rather than a flat list.
* [x] **Admin character attribute roll** — When creating a PC from admin, auto-roll attributes and show results in the create-object dialog.
* [x] **Admin left nav** — Verify "Console" nav link is present and links to `/admin`; add "World" nav section if missing.

## Phase 7: Backend — Memgraph Integration

* [x] **Memgraph seed on new-campaign** — After creating world.yaml, mirror the object graph into Memgraph (nodes = objects, edges = parent relationships).
* [x] **Memgraph sync on tool calls** — Each world-mutating tool call (`create_object`, `move_object`, `delete_object`) must also update the Memgraph graph.
* [x] **Graph query helpers** — Implement `get_path_between(id1, id2)` and `get_nearby_objects(id, radius)` using Memgraph Cypher for LOS and social graph queries.

## Phase 9: Progression & Character Depth

* [x] **Experience points and level-up flow** — Award XP after combat encounters and story milestones via a new `award_xp(id, amount)` tool. When XP crosses a level threshold, trigger a level-up dialog in the frontend with new ability choices (hit die roll, ASI, class features).
* [x] **Death saves panel** — When a PC's HP hits 0, display three success/fail checkbox pips on their PlayerCard. Each turn the player rolls a d20; success ≥ 10, fail < 10, two failures = dead, three successes = stable. DM agent drives the rolls via tool calls.
* [x] **Character sheet side panel** — In-game slide-out panel (toggle button in GameView) showing full ability scores, modifiers, class features, proficiencies, and equipped items pulled from the world object's `properties`.
* [x] **Spell slot tracker** — For caster classes, render a row of pip icons (filled/empty) per spell level on the character sheet panel. `Cast Spell` action decrements the correct slot; long rest restores all slots.
* [x] **Inventory / equipment panel** — Scrollable list of the PC's carried items (children of their world object) with weight total vs. carry capacity. Show equipped vs. stowed state; clicking equips/unequips via `set_object_property`.

## Phase 10: Combat UX

* [x] **Visual dice roll animation** — Before posting a roll result in chat, display a brief spinning die animation (d4/d6/d8/d10/d12/d20 SVG based on die type) then reveal the number. Pure tactile satisfaction.
* [x] **Initiative order tracker** — Persistent strip in the game sidebar listing combatants in initiative order with a highlight on the active turn. Updated via WS broadcast whenever the DM advances the turn queue.
* [x] **Conditions badge system** — Render condition tags (`Poisoned`, `Prone`, `Restrained`, `Blinded`, etc.) on each PlayerCard, read from the world object's `properties.conditions` list. DM agent sets conditions via `set_object_property`.
* [x] **Loot summary after combat** — When the DM kills the last enemy (all enemy HP ≤ 0), auto-generate a loot card listing coin and item drops. Each player can click "Take" to move an item to their inventory via `move_object`.

## Phase 11: World, Story & Exploration

* [x] **Campaign journal** — Auto-written narrative log: after each turn the DM agent generates a one-paragraph summary and appends it to `data/campaigns/<name>/journal.md`. Frontend shows a scrollable "Journal" tab in the game view.
* [x] **Quest / objective tracker** — Small panel listing active quests with checkbox milestones. Add a `add_quest(title, milestones[])` DM tool and a `complete_milestone(quest_id, milestone_idx)` tool. Quest state stored in world properties.
* [x] **NPC relationship tracker** — Track per-NPC disposition (`friendly`, `neutral`, `hostile`, `allied`) toward the party in world object properties. DM agent updates via `set_object_property`. Display a "Known NPCs" panel in the game sidebar.
* [x] **Random encounter roll during Travel** — Each travel segment triggers a hidden d20 roll against a location-appropriate encounter table (loaded from corpus). On a hit, mode switches to Combat and DM spawns enemies.
* [x] **Day/night cycle** — Track in-game time (hours) in campaign meta. Advance time each turn. Night imposes `disadvantage` on perception checks for non-darkvision races. Display current time and light state in the game header.

## Phase 12: Quality of Life

* [x] **Short rest / long rest buttons** — Buttons visible during Exploration mode. Short rest: player rolls hit dice to recover HP. Long rest: restore all HP, spell slots, and abilities. DM agent narrates the rest sequence.
* [x] **Ambient sound toggle** — Settings toggle to play looped ambient audio matching current location type (tavern, dungeon, forest, outdoor). Audio files stored under `src/frontend/public/audio/`. Location type inferred from the party's parent object type.

## Phase 14: F1 Help Wiki

- [x] Feature: F1 Help Wiki
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Scaffold `docs/help/home.md` and supporting wiki pages (combat, controls, character, spells)
  - [x] Create `HelpOverlay.vue` component — full-screen modal, renders Markdown, internal link navigation, image support
  - [x] Wire F1 keydown listener in `App.vue` (and Escape to close)
  - [x] Implement page history stack in `HelpOverlay.vue`; Backspace pops stack to previous page (no-op at `home.md`)
  - [x] Backend route `GET /api/help/{path}` — serves `.md` file content from `docs/help/`
  - [x] Backend route `GET /api/help/search?q=` — searches all `.md` files under `docs/help/` and returns matching page list
  - [x] Search bar in overlay header — calls search endpoint, lists results, click navigates to page
  - [x] Add robust error handling & tests
  - [x] Verify functionality & update documentation

## Phase 15: ESC to Close All Dialogs

- [x] Feature: ESC closes all dismissible dialogs
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Extend global `window` keydown handler in `App.vue` to dispatch ESC to visible dialogs in priority order: HelpOverlay, WorldMap, CharacterSheet, LootSummary, ActionBar long-rest confirm, GameView snapshot modal, GameView restore confirm modal
  - [x] Fix `WorldMap.vue` — replace `@keydown.esc` on overlay div (requires focus) with the global handler so ESC works without clicking first
  - [x] Add ESC close to `CharacterSheet.vue`
  - [x] Add ESC close to `LootSummary.vue`
  - [x] Add ESC close to ActionBar long-rest confirm overlay in `ActionBar.vue`
  - [x] Add ESC close to snapshot modal in `GameView.vue`
  - [x] Add ESC close to restore confirm modal in `GameView.vue`
  - [x] Verify `LevelUpDialog.vue` intentionally blocks ESC (no change needed)
  - [x] Verify functionality across all dialogs

## Phase 16: Procedural World Generator

- [x] Feature: On-demand terrain and object population
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Design `WorldGenerator` class in `src/backend/world/generator.py` — accepts visible coordinates + campaign context, returns list of new world objects to persist
  - [x] Implement ground-tile fallback — any LOS coordinate with no existing object receives a `ground` object (type, terrain variant, coordinates) so no tile is ever empty after being seen
  - [x] Implement biome/region context resolver — derives terrain type (grassland, dungeon stone, cobblestone street, etc.) from the player's current parent region object
  - [x] Implement large-feature placement — probabilistic placement of villages, ruins, forests, caves as bounded parent objects within an open region; children left ungenerated (`generated: false` flag)
  - [x] Implement recursive child generation — when LOS hits coordinates inside a parent object whose `generated` flag is false, trigger child-fill for that parent (doors, walls, interior layout); set `generated: true` on the parent when complete
  - [x] Implement interior entry trigger — crossing the threshold of a building (entering via a door object) triggers child-object generation for that building's interior
  - [x] Persist all generated objects to `world.yaml` immediately after generation; broadcast world-state delta to all connected clients via WS
  - [x] Mobile-object flagging — generated NPCs and creatures carry `mobile: true`; the World Agent re-simulates their position each turn rather than treating them as fixed
  - [x] Integrate generator call into the DM turn pipeline (`turn` command and WS move handler) — after computing LOS, pass unseen coords to `WorldGenerator.fill()`
  - [x] Frontend: update `WorldMap.vue` fog-of-war layer — explored tiles (player has had LOS) stay revealed; unvisited tiles render dark until LOS reaches them
  - [x] Add robust error handling and tests for generator edge cases (boundary coords, re-entry of existing tiles, nested parent generation)
  - [x] Verify end-to-end: player moves, new tiles generate, world map updates, re-visit produces no duplicate objects

## Phase 17: Lazy Recursive LOS-Driven World Expansion

- [x] Feature: Lazy recursive LOS-driven world expansion
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Ground-as-marker: ensure `WorldGenerator.fill_coordinate` writes a `ground` object (not nothing) for every empty LOS tile, so any object's presence — even bare ground — permanently suppresses re-generation at that coordinate. A large area, like "park", or "forum", or "road" and be used to cover a lot of LOS tiles. It is okay to convert areas that are not LOS, but all LOS tiles should be covered in some manner.
  - [x] Skip-if-occupied guard: at the top of `fill_coordinate`, query `world.yaml` for any object at the target coordinate; return early if one exists (prevents duplicates on re-visit)
  - [x] Parent-shell lazy fill: when LOS reaches a coordinate inside a parent object whose `generated` flag is `false`, call `WorldGenerator.fill_children(parent_id)` to populate immediate children only; set `generated: true` on the parent when complete
  - [x] Door-crossing trigger: in the WS move handler, detect when the player's new coordinates overlap a `door` object's bounding box; call `fill_children` on the door's parent building to spawn interior layout (furniture, NPCs, containers)
  - [x] Mobile-object exemption: objects with `mobile: true` are excluded from the skip-if-occupied guard — their position is re-simulated each turn by the World Agent regardless of prior generation
  - [x] Per-session fog-of-war persistence: maintain a per-player-session `explored` set (coordinate list); update it after every LOS computation; expose it via the WS session state so the frontend can reconstruct it on reconnect
  - [x] Frontend `WorldMap.vue` fog-of-war layer: render explored tiles clear, unexplored tiles as dark fog, boundary tiles (partial visibility) dimmed; source data from the session `explored` set broadcast by the backend
  - [x] Integration: wire `fill_coordinate` and `fill_children` calls into the DM turn pipeline and WS move handler after the LOS step; broadcast world-state delta to all connected clients
  - [x] Add error handling and tests: re-entry of occupied tiles produces no duplicates, door-crossing generates exactly one set of children, mobile objects regenerate correctly, `explored` set survives session reconnect
  - [x] Verify end-to-end: player moves into open terrain → ground tiles appear, player approaches village → village shell exists with `generated: false` children, player enters door → interior populates, revisit produces no new objects

## Phase 19: Server-Down Toast Notification

- [ ] Feature: Server-down toast notification
  - [x] Integrate into PRD.md (Why/What/How)
  - [ ] Add `serverDown` ref to campaign store; set true on WS `error`/`close`, false on WS `open`
  - [ ] Show toast in `App.vue` whenever `serverDown` is true or an action is attempted while disconnected
  - [ ] `sendChat`, `sendAction`, `sendSnapshot` set `serverDown` flag and surface message when WS is not open
  - [ ] Wrap all `fetch` calls in campaign store with a shared helper that catches `TypeError` (network failure) and sets `serverDown`
  - [ ] Toast auto-dismisses 3 seconds after WS reconnects
  - [ ] Toast includes a manual reconnect button that calls `connectWs`
  - [ ] Verify: disconnect server → attempt action → toast appears; restart server → toast fades

## Phase 18: Build Info Tooltip on Nav Title

- [ ] Feature: Build info tooltip on nav title
  - [x] Integrate into PRD.md (Why/What/How)
  - [ ] Backend: extend `GET /api/build-info` to also run `git log -5 --format="%h|%s"` and return `recent_commits: [{hash, subject}]`
  - [ ] Frontend: fetch `/api/build-info` on `NavBar.vue` mount; store result
  - [ ] Frontend: wrap `.navbar-brand` in a `<div>` with `@mouseenter`/`@mouseleave` to toggle tooltip visibility
  - [ ] Frontend: render tooltip — HEAD line (hash · date · author), divider, then 5 recent commit rows each showing short hash + subject
  - [ ] Frontend: style tooltip to match the dark navbar theme
  - [ ] Verify functionality

## Phase 26: Resizable World Map Dialog

- [ ] Feature: Resizable world map dialog with localStorage persistence
  - [x] Integrate into requirements.md (Why/What/How)
  - [ ] Add resize handles (8-direction: N, S, E, W, NE, NW, SE, SW) as absolutely-positioned divs around the map-dialog
  - [ ] Implement mousedown/mousemove/mouseup resize logic in WorldMap.vue; clamp to min 400×300 and max 95vw×95vh
  - [ ] On resize end, save `{width, height}` to `localStorage` under key `worldmap-size`
  - [ ] On dialog open, read `worldmap-size` from localStorage and apply to map-dialog dimensions
  - [ ] Verify: resize each edge and corner → size persists after close/reopen; respects min/max clamps

## Phase 20: BSP World Partitioning and Map Coloring

- [ ] Feature: BSP-driven child placement and colored tile map
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Implement `src/backend/world/bsp.py` — `BspPartitioner` class with `partition(parent, player_pos, radius, world)` returning a list of placement rects; respects parent boundaries and radius limit
  - [x] Integrate BSP into `WorldGenerator.fill_children` — replace naive perimeter-wall loop with BSP-placed building shells (inns, taverns, stores, roads, parks) appropriate to parent type; added `fill_children_bsp(parent_id, player_pos, radius)` for on-demand radius-limited expansion
  - [x] Add `tile_color` property to generated objects: brown=road/ground/door, orange=building/store, green=inn/pub, dark_green=forest, blue=water
  - [x] Frontend `WorldMap.vue` — switch node rendering from circle-dot to filled tile squares sized by zoom; apply color from `tile_color` property (or type-based lookup) instead of static TYPE_CONFIG colors
  - [x] Frontend — fog-of-war: explored tiles never go dark again; current LOS tiles fully lit; unseen tiles are black (pure black background + destination-out punch-through)
  - [ ] Verify: open map (F4) after movement → tiles display in correct colors; unexplored areas are black; explored-but-not-current-LOS areas are visible (memory)

## Phase 23: Map Z-Order and Tooltip Ancestry

- [ ] Feature: Map z-order rendering and tooltip ancestry chain
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Add `TILE_Z` priority map in `WorldMap.vue`; sort tileNodes by z before draw pass
  - [x] Reverse hit-test iteration so frontmost (highest-z) object wins tooltip
  - [x] Build parent ancestry chain in tooltip from allNodes (hierarchy + tiles)
  - [x] Add `location_ancestry` field to `CampaignPlayer` model (user.py)
  - [x] Populate `location_ancestry` in `get_players()` by walking world parent chain
  - [x] Display ancestry chain on each `PlayerCard.vue` beneath character name
  - [ ] Verify: hovering player shows player tooltip; hovering floor shows floor + ancestry; player cards show ancestry chain

- [ ] Feature: Player icon map tooltip ancestry
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Keep unfiltered `allHierarchyNodes` ref in `WorldMap.vue` for ancestry lookups
  - [x] Use unfiltered map when building tooltip ancestry chain so virtual parents (party, planet, etc.) resolve correctly
  - [ ] Verify: hovering player circle shows full ancestry chain on map tooltip

- [ ] Feature: Unique per-type tile colors on world map
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Replace `TILE_COLORS` + `TYPE_TO_TILE_COLOR` with direct `TYPE_COLOR` map in `WorldMap.vue`
  - [x] Assign unique hex to each type: wall=gray, floor=tan, ground=dark dirt, door=amber, cobblestone=gray-tan, building subtypes each distinct
  - [x] Update map legend to include Wall and Door swatches
  - [ ] Verify: F4 map shows walls gray, floor tan, ground darker; building types render distinct colors

## Phase 22: DM ReAct Silent Tool Execution

- [ ] Feature: DM ReAct tool execution — silent action loop
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Replace `ReActAgent` in `ai_client.py` with a manual loop: prompt → parse Action/Action Input → dispatch tool → inject Observation → repeat until Final Answer
  - [x] Strip all Thought/Action/Observation lines; broadcast only the Final Answer text
  - [x] Apply same fix to PC agent and World agent loops
  - [ ] Verify: player sends message → DM narrates cleanly → world.yaml mutates (object created, HP changed, etc.)

## Phase 21: Admin World Reset

- [ ] Feature: Admin world reset (keep players)
  - [x] Integrate into PRD.md (Why/What/How)
  - [x] Backend: `POST /api/admin/campaigns/{campaign_id}/reset-world` — extract all PC objects, rebuild hierarchy via `create_default_world()`, re-insert PCs under a new party, save
  - [x] Frontend: "Reset World" button per campaign card in `AdminView.vue` using existing `dialog` confirm pattern
  - [ ] Verify: reset triggers dialog → confirm → world hierarchy rebuilt → players preserved

## Phase 25: World Map Tooltip Dimensions

- [ ] Feature: Dimension display in world map tooltip
  - [x] Integrate into requirements.md (Why/What/How)
  - [x] Backend: include `size` (as `[l, w, h]`) in map node serialization in `campaign_routes.py` `get_map`
  - [x] Frontend: parse `size` from each node in `WorldMap.vue`; render `LxWxH ft` beneath the type label; skip if all dimensions are zero
  - [x] Frontend: include `size` when building ancestry chain; annotate each ancestor line with its dimensions when non-zero
  - [ ] Verify: hover a wall tile → dimensions shown; hover player → player has no size → no dimension line; ancestry chain shows room size above, building size above that

## Phase 24: /requirement Slash Command

- [ ] Feature: /requirement slash command in chat
  - [x] Integrate into requirements.md (Why/What/How)
  - [ ] Backend: `POST /api/requirements` — appends requirement text to `docs/requirements.md` under `## Ad-hoc & Experimental Features` and appends a `- [ ] **Requirement**: <text>` entry to `tasks.md`; broadcasts `{type: "requirement_added", text: <text>}` to all WS sessions
  - [ ] Frontend: intercept `/requirement <text>` in `ChatWindow.vue` before sending to DM — call `POST /api/requirements` with the text, suppress normal chat submission
  - [ ] Frontend: handle `requirement_added` WS message in `ChatWindow.vue` — display a system notification line (e.g. `[Requirement added: <text>]`) visible to all players
  - [ ] Add robust error handling & tests
  - [ ] Verify: player types `/requirement fix the fog` → requirement appended to docs → all players see system notification in chat

## Phase 13: Quality & Deployment

* [x] **`dev.bat` Typer CLI mode** — Update `dev.bat` to also support running `python -m src.backend.main` CLI commands alongside the Vite/FastAPI servers.
* [x] **Integration smoke test** — Script that runs `index-corpus` → `new-campaign TestRun` → `turn --campaign TestRun` and asserts a non-empty narrative and updated world.yaml.
* [x] **Frontend production build** — Confirm `npm run build` outputs to `dist/` and FastAPI serves it correctly at `/`.

- [ ] **Requirement (player-submitted)**: we need an Inn to be much large than is shown.
