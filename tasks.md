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
  - [x] Backend route `GET /api/help/{path}` — serves `.md` file content from `docs/help/`
  - [x] Backend route `GET /api/help/search?q=` — searches all `.md` files under `docs/help/` and returns matching page list
  - [x] Search bar in overlay header — calls search endpoint, lists results, click navigates to page
  - [x] Add robust error handling & tests
  - [x] Verify functionality & update documentation

## Phase 13: Quality & Deployment

* [x] **`dev.bat` Typer CLI mode** — Update `dev.bat` to also support running `python -m src.backend.main` CLI commands alongside the Vite/FastAPI servers.
* [x] **Integration smoke test** — Script that runs `index-corpus` → `new-campaign TestRun` → `turn --campaign TestRun` and asserts a non-empty narrative and updated world.yaml.
* [x] **Frontend production build** — Confirm `npm run build` outputs to `dist/` and FastAPI serves it correctly at `/`.
