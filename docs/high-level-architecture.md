# D&D 5e AI Game Engine - Architecture Overview

A CLI-based agentic system that simulates D&D 5e gameplay using AI agents for the Dungeon Master, Players, and World. This document explains the architecture for developers learning agentic system design.

## Core Concept: Agents + Tools + State

The system follows a fundamental agentic pattern:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   AGENTS    │────▶│    TOOLS    │────▶│    STATE    │
│  (LLM-based)│     │ (Functions) │     │   (World)   │
└─────────────┘     └─────────────┘     └─────────────┘
      │                                        │
      └────────────── reads ◀──────────────────┘
```

**Agents** observe state, reason about it, and decide which **tools** to call. **Tools** are the only way to mutate **state**. This separation ensures:
- Deterministic state changes (tools are pure functions)
- Auditable actions (every change traces to a tool call)
- Reproducibility (same state + same tool calls = same outcome)

## The World Model

Everything is an **Object**. The entire game state lives in a single data structure:

```yaml
world:
  objects:
    1: {type: system, name: Realmspace, parent: null}
    2: {type: planet, name: Toril, parent: 1}
    ...
    8: {type: party, name: The Adventurers, parent: 7}
    9: {type: PC, name: Thorin, parent: 8, properties: {hp: {...}, abilities: {...}}}
```

### Why This Design?

1. **Single source of truth** - No separate `players`, `items`, `locations` tables to sync
2. **Uniform API** - `get_object(id)` works for everything
3. **Natural hierarchy** - Parent/child relationships model containment (sword in bag, bag on elf, elf in room)
4. **Visibility is traversal** - What can a player see? Walk up to ancestors, across to siblings

```python
# A PC's location is determined by walking up the parent chain
pc.parent = 8        # party
party.parent = 7     # Common Room
room.parent = 6      # Stonehill Inn
inn.parent = 5       # Phandalin (town)
```

## Agent Architecture

Three agent types, each with a specific role:

### 1. Dungeon Master Agent
- **Role**: Narrator, referee, world coordinator
- **Input**: Current situation, visible world state, relevant rules
- **Output**: Narrative text + tool calls (damage, item creation, etc.)
- **Tools**: All world manipulation tools

```python
def generate_dm_response(campaign, situation, world_tools):
    # Query vector DB for relevant D&D rules
    rules_context = query_rules(situation)

    # Build prompt with world state + rules + player info
    prompt = f"""You are the DM for "{campaign.name}"...

    VISIBLE WORLD STATE: {visible_world}
    RELEVANT RULES: {rules_context}
    PLAYERS: {pc_summaries}

    Narrate what happens. Use tools to modify game state."""

    return llm.complete(prompt)
```

### 2. Player Agents (one per PC)
- **Role**: Act in character based on personality/goals
- **Input**: Character sheet, visible world, current situation
- **Output**: Action description (in first person)
- **Tools**: None (players declare intent; DM resolves)

```python
def generate_player_action(campaign, player_id, situation):
    pc = world.get_object(player_id)
    visible_world = world.get_visible_world(player_id)

    prompt = f"""You are {pc.name}, a {race} {class}.

    Personality: {pc.properties['personality']}
    Goals: {pc.properties['goals']}

    What do you do? Respond in first person."""
```

### 3. World Agent
- **Role**: Environmental changes, NPC behavior, random events
- **Input**: Time passed, current world state
- **Output**: Description of world changes
- **Tools**: Could have tools for weather, NPC movement (not yet implemented)

## Tool System

Tools are the **only** way agents can modify state. This is critical for agentic systems:

```python
class WorldTools:
    def __init__(self, world: World):
        self.world = world

    def create_object(self, type, parent_id, **properties) -> ToolResult:
        """Create a new object in the world."""
        obj = Object(id=world.next_id(), parent=parent_id, type=type, ...)
        world.add_object(obj)
        return ToolResult(success=True, data={"id": obj.id})

    def add_hp(self, id, delta) -> ToolResult:
        """Modify HP. Returns death status."""
        obj = world.get_object(id)
        hp = obj.properties["hp"]
        hp["current"] = max(0, min(hp["max"], hp["current"] + delta))
        return ToolResult(success=True, data={"new_hp": hp["current"], "is_dead": hp["current"] <= 0})
```

### Tool Definitions for LLM

Tools are exposed to the LLM with JSON schemas:

```python
TOOL_DEFINITIONS = [
    {
        "name": "add_hp",
        "description": "Modify a player's HP (negative for damage, positive for healing)",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Object ID of the player"},
                "delta": {"type": "integer", "description": "Amount to add (negative for damage)"},
            },
            "required": ["id", "delta"],
        },
    },
    # ... more tools
]
```

## RAG: Rules as Context

The D&D rules corpus (Player's Handbook, Monster Manual, etc.) is indexed in ChromaDB:

```python
# Indexing (one-time)
for chunk in split_markdown_into_chunks(rules_file):
    collection.add(ids=[chunk_id], documents=[chunk_text], metadatas=[{source, section}])

# Retrieval (every DM turn)
def query_rules(situation: str) -> str:
    results = collection.query(query_texts=[situation], n_results=3)
    return format_as_context(results)
```

This gives the DM agent access to actual D&D rules without fine-tuning:

```
RELEVANT D&D RULES:
[5e Basic Rules: Combat]
Combat Step by Step: 1. Determine surprise. 2. Establish positions...

[Player's Handbook: Actions in Combat]
When you take your action, you can take one of the actions presented here...
```

## Turn Flow

```
┌──────────────────────────────────────────────────────────┐
│                      GAME TURN                           │
├──────────────────────────────────────────────────────────┤
│  1. World Agent                                          │
│     └─▶ Generate environmental updates                   │
│                                                          │
│  2. Player Agents (for each living PC)                   │
│     └─▶ Generate action based on personality             │
│                                                          │
│  3. DM Agent                                             │
│     ├─▶ Query rules corpus for relevant mechanics        │
│     ├─▶ Observe all player actions                       │
│     ├─▶ Generate narrative + call tools                  │
│     └─▶ Resolve outcomes (dice rolls, damage, etc.)      │
│                                                          │
│  4. Persist                                              │
│     └─▶ Save world state to YAML                         │
└──────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Stateless CLI, Stateful Files
Each CLI invocation loads state from YAML, runs, and saves. No daemon process.

```bash
python -m src.backend.main turn --campaign MyCampaign.yaml
```

### 2. Reproducibility via Seeds
```python
campaign = Campaign(name="Quest", seed=12345, ...)
```
Fixed seeds enable replay and debugging of random events.

### 3. Visibility = Hierarchy Traversal
Instead of complex spatial calculations:
```python
def get_visible_world(observer_id):
    visible = {observer_id}
    visible |= ancestors(observer_id)  # Can see where you are
    visible |= siblings(observer_id)   # Can see what's nearby
    return World(objects={id: objects[id] for id in visible})
```

### 4. Properties Bag for Flexibility
Rather than rigid schemas per object type:
```python
class Object:
    type: str           # "PC", "sword", "room"
    properties: dict    # Anything else: hp, abilities, enchantments...
```

## File Structure

```
src/backend/
├── main.py              # Typer CLI: new-campaign, turn, status, query
├── core/
│   ├── config.py        # Settings (Ollama URL, ChromaDB path)
│   ├── tools.py         # WorldTools class + TOOL_DEFINITIONS
│   ├── vector_store.py  # ChromaDB: index_corpus(), search()
│   └── ai_client.py     # Ollama/LlamaIndex: generate_dm_response(), etc.
└── models/
    ├── world.py         # Object, World classes
    ├── game.py          # Campaign, GameState
    └── player.py        # Constants: RACE_MODIFIERS, CLASS_HIT_DICE
```

## What Makes This "Agentic"?

1. **Autonomous decision-making** - Agents choose actions based on goals/personality
2. **Tool use** - LLM decides which functions to call and with what arguments
3. **Multi-agent coordination** - DM, players, and world interact through shared state
4. **Grounded in external knowledge** - RAG retrieves rules; agents don't hallucinate mechanics
5. **Persistent state** - Actions have consequences across turns

## Extending the System

### Add a new tool
```python
# In tools.py
def cast_spell(self, caster_id: int, spell_name: str, target_id: int) -> ToolResult:
    # Look up spell in corpus, apply effects
    ...

# Add to TOOL_DEFINITIONS for LLM visibility
```

### Add a new agent type
```python
# In ai_client.py
def generate_merchant_dialogue(self, npc_id: int, customer_id: int) -> str:
    npc = world.get_object(npc_id)
    prompt = f"You are {npc.name}, a merchant. A customer approaches..."
```

### Add new object types
Just create objects with new `type` values and relevant `properties`:
```python
Object(type="trap", properties={"damage": "2d6", "dc": 15, "triggered": False})
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `llama-index` + `llama-index-llms-ollama` | LLM orchestration with local Ollama |
| `chromadb` | Vector database for rules corpus |
| `pydantic` | Data validation and serialization |
| `typer` + `rich` | CLI framework with nice output |
| `pyyaml` | World state persistence |
| `markdown-it-py` | Parse rules markdown for indexing |

## Running It

```bash
# Install
uv sync

# Index rules (one-time)
python -m src.backend.main index-corpus

# Create campaign
python -m src.backend.main new-campaign "MyQuest" --seed 42

# Run a turn (requires Ollama with qwen2.5:14b)
python -m src.backend.main turn --campaign MyQuest.yaml

# Query rules
python -m src.backend.main query "how does sneak attack work"
```
