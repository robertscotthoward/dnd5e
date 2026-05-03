# D&D 5e AI Game Engine — Project Overview

---

## 1. High-Level Mission

An agentic AI system that autonomously simulates Dungeons & Dragons 5e campaigns, where LLM-powered agents act as the Dungeon Master, player characters, and the world itself—all grounded in actual D&D rules.

---

## 2. Executive Summary

This project demonstrates how to build a multi-agent AI system using a real-world, rule-bound domain as its proving ground. The core problem it solves is coordinating multiple autonomous agents (DM, players, environment) that must reason, act, and interact within a shared persistent state—without hallucinating rules—by grounding every decision in a semantically-indexed D&D 5e rules corpus. The primary audience is AI/ML engineers interested in agentic system design patterns: tool calling, RAG, multi-agent coordination, and reproducible simulation.

---

## 3. Key Features

- **Multi-Agent Coordination**: Three distinct agent roles (Dungeon Master, Player Characters, World) operate autonomously each turn, sharing a single persistent world state.
- **Rules-Grounded Reasoning (RAG)**: A ChromaDB vector store indexes 7 D&D 5e source books; the DM agent queries it each turn to ground decisions in actual game mechanics.
- **Unified Object Model**: Every entity—characters, items, locations, parties—is represented as a single `Object` type with a flexible property bag, forming a spatial hierarchy.
- **Tool-Only World Mutation**: World state can only be changed via explicit tools (`create_object`, `add_hp`, `move_object`, etc.), ensuring auditability and reproducibility.
- **Reproducible Campaigns**: Campaigns are seeded with a fixed integer; identical seeds produce identical event sequences, enabling deterministic simulation and testing.

---

## 4. Architecture & Logic

### Technical Stack

| Layer | Technology | Role |
|---|---|---|
| Language | Python 3.12+ | Core application |
| CLI Framework | Typer + Rich | Command-line interface and display |
| LLM Orchestration | LlamaIndex + Ollama | Agent reasoning and tool calling |
| LLM Backend | Ollama (`qwen2.5:14b`) | Local inference (no cloud dependency) |
| Vector Database | ChromaDB | Semantic search over D&D rules corpus |
| Data Models | Pydantic v2 | Type-safe world state |
| Persistence | YAML | Campaign save/load |

### Data Flow: One Game Turn

```
┌─────────────────────────────────────────────────────────┐
│  YAML Campaign File  ──────────────────▶  World State   │
└─────────────────────────────────────────────────────────┘
          │
          ▼
  1. World Agent         Generates environmental events (weather, NPC movement)
          │
          ▼
  2. Player Agents       Each PC declares an action based on personality + goals
  (one per PC)
          │
          ▼
  3. DM Agent            Queries rules corpus (ChromaDB RAG)
          │              Receives all player actions
          │              Generates narrative
          └────────────▶ Calls Tools to mutate world state
                         (damage, movement, item creation, etc.)
          │
          ▼
  4. Persist             Updated World State ──▶ YAML Campaign File
```

### Object Hierarchy

Everything in the world is an `Object` node in a parent/child tree:

```
System (Realmspace)
 └─ Planet (Toril)
     └─ Continent (Faerûn)
         └─ Region (Sword Coast)
             └─ Town (Neverwinter)
                 └─ Location (The Rusty Flagon Inn)
                     └─ Room (Common Room)
                         └─ Party (The Adventurers)  [virtual]
                             ├─ PC (Thorin, Dwarf Fighter)
                             ├─ PC (Elara, Elf Wizard)
                             ├─ PC (Mira, Halfling Rogue)
                             └─ PC (Aldric, Human Cleric)
```

Visibility is hierarchy-based: an object can see itself, its ancestors, and its siblings. Agents only receive the world sub-tree visible to them.

---

## 5. File Structure

```
/
├── src/backend/
│   ├── main.py             # Typer CLI entry point; all user-facing commands
│   ├── core/
│   │   ├── config.py       # Settings (Ollama URL, ChromaDB path, model name)
│   │   ├── ai_client.py    # LlamaIndex + Ollama agent and tool-calling setup
│   │   ├── tools.py        # World manipulation tools (the only way to mutate state)
│   │   └── vector_store.py # ChromaDB integration; corpus indexing and querying
│   └── models/
│       ├── world.py        # Object and World models; hierarchy, visibility, serialization
│       ├── game.py         # Campaign and GameState models; turn tracking, event log
│       └── player.py       # D&D constants (race modifiers, class hit dice, ability helpers)
│
├── data/
│   ├── corpus/             # 7 D&D 5e source markdown files (rules, monsters, spells)
│   ├── chromadb/           # ChromaDB vector store (auto-generated on first index)
│   └── worlds/             # Saved campaign YAML files (auto-generated)
│
├── docs/
│   ├── requirements.md             # Feature specifications and use case definitions
│   └── high-level-architecture.md  # Agentic system design narrative
│
├── pyproject.toml          # Python dependencies and project metadata
├── config.yaml             # Runtime configuration (Ollama, ChromaDB settings)
├── CLAUDE.md               # Guidance for Claude Code AI assistant
└── dev.bat                 # Development convenience script
```

---

## 6. Getting Started

### Prerequisites

- Python 3.12+
- [`uv`](https://github.com/astral-sh/uv) (Python package manager)
- [Ollama](https://ollama.com/) running locally with `qwen2.5:14b` pulled

### Setup

```bash
# Install Python dependencies
uv sync

# Pull the required LLM (if not already available)
ollama pull qwen2.5:14b
```

### Usage

```bash
# Step 1: Index the D&D rules corpus (run once)
python -m src.backend.main index-corpus

# Step 2: Create a new campaign
python -m src.backend.main new-campaign "MyAdventure" --seed 42

# Step 3: Run a turn
python -m src.backend.main turn --campaign "MyAdventure.yaml"

# Other commands
python -m src.backend.main status --campaign "MyAdventure.yaml"   # View world state
python -m src.backend.main query "how does sneak attack work"      # Query rules corpus
python -m src.backend.main test-ai                                 # Test Ollama connection
```

### Configuration

Optionally override defaults in `config.yaml`:

```yaml
ollama:
  model: qwen2.5:14b
  base_url: http://localhost:11434
  temperature: 0.7

chromadb:
  persist_directory: data/chromadb
  collection_name: dnd5e_corpus
```
