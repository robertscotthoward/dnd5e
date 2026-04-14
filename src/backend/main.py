"""D&D 5e AI Game Engine - CLI Entry Point."""

import random
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from .core.config import settings
from .core.vector_store import vector_store
from .core.graph_store import graph_store
from .core.ai_client import ai_client
from .core.tools import WorldTools
from .models.world import World, Object, Location
from .models.player import PC, AbilityScores, ClassLevel, HealthPool, RACE_MODIFIERS, CLASS_HIT_DICE
from .models.game import Campaign, Party, GameState

app = typer.Typer(
    name="dnd5e",
    help="D&D 5e AI-powered game engine with agents for DM, Players, and World simulation",
    no_args_is_help=True,
)
console = Console()

# Global game state
game_state = GameState()


def generate_ability_scores(seed: int) -> AbilityScores:
    """Generate random ability scores using 4d6 drop lowest."""
    rng = random.Random(seed)

    def roll_ability() -> int:
        rolls = [rng.randint(1, 6) for _ in range(4)]
        rolls.sort(reverse=True)
        return sum(rolls[:3])

    return AbilityScores(
        str=roll_ability(),
        int=roll_ability(),
        wis=roll_ability(),
        dex=roll_ability(),
        con=roll_ability(),
        chr=roll_ability(),
    )


def create_default_world(name: str) -> World:
    """Create the default world hierarchy for a new campaign."""
    world = World(name=name)

    # System: Realmspace (root)
    system = Object(
        id=world.next_id(),
        parent=None,
        type="system",
        name="Realmspace",
        description="The crystal sphere containing Toril and its celestial bodies",
        is_moveable=False,
    )
    world.add_object(system)

    # Planet: Toril
    planet = Object(
        id=world.next_id(),
        parent=system.id,
        type="planet",
        name="Toril",
        description="The world of Abeir-Toril, home to the Forgotten Realms",
        is_moveable=False,
    )
    world.add_object(planet)

    # Continent: Faerûn
    continent = Object(
        id=world.next_id(),
        parent=planet.id,
        type="continent",
        name="Faerûn",
        description="The western continent of Toril",
        is_moveable=False,
    )
    world.add_object(continent)

    # Region: The Sword Coast
    region = Object(
        id=world.next_id(),
        parent=continent.id,
        type="region",
        name="The Sword Coast",
        description="A region on the western coast of Faerûn",
        is_moveable=False,
    )
    world.add_object(region)

    # Town: Phandalin (starting location)
    town = Object(
        id=world.next_id(),
        parent=region.id,
        type="town",
        name="Phandalin",
        description="A frontier town on the Triboar Trail",
        is_moveable=False,
        is_virtual=True,
    )
    world.add_object(town)

    # Inn: Stonehill Inn
    inn = Object(
        id=world.next_id(),
        parent=town.id,
        type="inn",
        name="Stonehill Inn",
        description="A modest inn run by Toblen Stonehill and his family",
        is_moveable=False,
        is_virtual=True,
    )
    world.add_object(inn)

    # Common Room
    common_room = Object(
        id=world.next_id(),
        parent=inn.id,
        type="room",
        name="Common Room",
        description="The main gathering area of the inn with tables and a fireplace",
        is_moveable=False,
        is_virtual=True,
        size=world.objects[1].size,  # Use a reasonable size
    )
    common_room.size.length = 30
    common_room.size.width = 20
    common_room.size.height = 10
    world.add_object(common_room)

    return world


def create_default_pcs(world: World, party_id: int, seed: int) -> list[PC]:
    """Create 4 default player characters."""
    pcs = []
    common_room_id = 7  # ID of the common room

    # Character definitions
    characters = [
        {
            "name": "Thorin",
            "race": "Dwarf",
            "class": "Fighter",
            "personality": "Gruff but loyal, values honor above all else",
            "backstory": "A former soldier seeking redemption for past failures",
        },
        {
            "name": "Elara",
            "race": "Elf",
            "class": "Wizard",
            "personality": "Curious and bookish, always seeking knowledge",
            "backstory": "A scholar from Candlekeep investigating ancient mysteries",
        },
        {
            "name": "Mira",
            "race": "Halfling",
            "class": "Rogue",
            "personality": "Quick-witted and charming, can't resist a good heist",
            "backstory": "A former street urchin turned adventurer",
        },
        {
            "name": "Aldric",
            "race": "Human",
            "class": "Cleric",
            "personality": "Compassionate healer with strong moral convictions",
            "backstory": "A priest of Lathander spreading light in dark places",
        },
    ]

    for i, char in enumerate(characters):
        # Create object in world
        char_seed = seed + i * 1000
        obj_id = world.next_id()
        obj = Object(
            id=obj_id,
            parent=common_room_id,
            type="PC",
            name=char["name"],
            description=f"{char['race']} {char['class']}",
            location=Location(x=5 * (i % 2), y=5 * (i // 2), z=0),
        )
        world.add_object(obj)

        # Generate abilities
        abilities = generate_ability_scores(char_seed)

        # Apply racial modifiers
        race_mods = RACE_MODIFIERS.get(char["race"], {})
        for ability, mod in race_mods.items():
            current = getattr(abilities, ability if ability not in ("str", "int") else f"{ability}_")
            setattr(abilities, ability if ability not in ("str", "int") else f"{ability}_", current + mod)

        # Calculate HP (hit die max + CON modifier for level 1)
        hit_die = CLASS_HIT_DICE.get(char["class"], 8)
        con_mod = abilities.get_modifier("con")
        max_hp = hit_die + con_mod

        pc = PC(
            object_id=obj_id,
            name=char["name"],
            race=char["race"],
            classes=[ClassLevel(type=char["class"], level=1)],
            abilities=abilities,
            hp=HealthPool(max=max_hp, current=max_hp),
            personality=char["personality"],
            backstory=char["backstory"],
            goals=["Complete the current quest", "Grow stronger through adventure"],
        )
        pcs.append(pc)

    return pcs


@app.command()
def new_campaign(
    name: str = typer.Argument(..., help="Name of the campaign"),
    seed: Optional[int] = typer.Option(None, help="Random seed for reproducibility"),
):
    """Create a new campaign with 4 PCs and a default world."""
    # Generate seed if not provided
    if seed is None:
        seed = random.randint(1, 999999)

    console.print(f"[bold green]Creating new campaign: {name}[/bold green]")
    console.print(f"Seed: {seed}")

    # Create world
    world = create_default_world(name)
    console.print(f"Created world with {len(world.objects)} objects")

    # Create party
    party_obj = Object(
        id=world.next_id(),
        parent=7,  # Common room
        type="party",
        name="The Adventurers",
        description="A band of adventurers seeking fortune and glory",
        is_virtual=True,
    )
    world.add_object(party_obj)

    # Create PCs
    pcs = create_default_pcs(world, party_obj.id, seed)
    console.print(f"Created {len(pcs)} player characters")

    # Create party
    party = Party(
        id=party_obj.id,
        name="The Adventurers",
        member_ids=[pc.object_id for pc in pcs],
    )

    # Create campaign
    campaign = Campaign(
        name=name,
        seed=seed,
        world=world,
        pcs=pcs,
        npcs=[],
        parties=[party],
    )

    # Save campaign
    save_path = settings.worlds_path / f"{name}.yaml"
    save_campaign(campaign, save_path)

    # Load into game state
    game_state.load_campaign(campaign, str(save_path))

    console.print(f"[green]Campaign saved to: {save_path}[/green]")

    # Show summary
    status()


@app.command()
def load_campaign(
    file: Path = typer.Argument(..., help="Path to campaign YAML file"),
):
    """Load an existing campaign from a YAML file."""
    if not file.exists():
        # Try in worlds directory
        file = settings.worlds_path / file
        if not file.exists():
            console.print(f"[red]Campaign file not found: {file}[/red]")
            raise typer.Exit(1)

    console.print(f"[bold]Loading campaign from: {file}[/bold]")

    campaign = load_campaign_from_file(file)
    game_state.load_campaign(campaign, str(file))

    console.print(f"[green]Loaded campaign: {campaign.name}[/green]")
    status()


@app.command()
def turn():
    """Execute one game turn (DM + players act)."""
    if not game_state.has_campaign:
        console.print("[red]No campaign loaded. Use 'new-campaign' or 'load-campaign' first.[/red]")
        raise typer.Exit(1)

    campaign = game_state.campaign
    campaign.advance_turn()

    console.print(Panel(f"[bold]Turn {campaign.turn_number}[/bold]", title="Game Turn"))

    # Create tools for this turn
    tools = WorldTools(campaign)

    # 1. World Agent: Update environment
    console.print("\n[dim]World updates...[/dim]")
    world_update = ai_client.generate_world_update(campaign)
    if world_update:
        console.print(f"[italic]{world_update}[/italic]")

    # 2. Each player acts
    for pc in campaign.pcs:
        if pc.is_dead:
            continue

        console.print(f"\n[bold blue]{pc.name}'s turn[/bold blue]")
        situation = f"Turn {campaign.turn_number}. The party is in {campaign.world.get_object(7).name}."
        action = ai_client.generate_player_action(campaign, pc.object_id, situation)
        console.print(f"[cyan]{action}[/cyan]")

    # 3. DM resolves and narrates
    console.print("\n[bold yellow]Dungeon Master[/bold yellow]")
    situation = "The party has completed their actions. Resolve any outcomes and narrate what happens."
    dm_response = ai_client.generate_dm_response(campaign, situation, tools)
    console.print(dm_response)

    # Save campaign
    save_campaign(campaign, Path(game_state.campaign_file))
    console.print(f"\n[dim]Campaign saved. Turn {campaign.turn_number} complete.[/dim]")


@app.command()
def status():
    """Show current game state."""
    if not game_state.has_campaign:
        console.print("[yellow]No campaign loaded.[/yellow]")
        console.print("Use 'new-campaign <name>' to create a new campaign")
        console.print("Use 'load-campaign <file>' to load an existing campaign")
        return

    campaign = game_state.campaign

    # Campaign info
    console.print(Panel(f"[bold]{campaign.name}[/bold]\nTurn: {campaign.turn_number} | Seed: {campaign.seed}"))

    # World tree
    tree = Tree("[bold]World[/bold]")
    root = campaign.world.get_object(1)
    if root:
        add_tree_node(tree, campaign.world, root.id)
    console.print(tree)

    # Players table
    table = Table(title="Player Characters")
    table.add_column("Name", style="cyan")
    table.add_column("Race")
    table.add_column("Class")
    table.add_column("Level")
    table.add_column("HP", justify="right")
    table.add_column("Status")

    for pc in campaign.pcs:
        class_str = "/".join(f"{c.type}" for c in pc.classes)
        level_str = str(pc.total_level)
        hp_str = f"{pc.hp.current}/{pc.hp.max}"
        status_str = "[red]Dead[/red]" if pc.is_dead else "[green]Alive[/green]"
        table.add_row(pc.name, pc.race, class_str, level_str, hp_str, status_str)

    console.print(table)


@app.command()
def index_corpus(
    force: bool = typer.Option(False, "--force", "-f", help="Force reindex even if already indexed"),
):
    """Index D&D rules into ChromaDB for semantic search."""
    console.print("[bold]Indexing D&D corpus...[/bold]")
    count = vector_store.index_corpus(force=force)
    console.print(f"[green]Indexed {count} chunks[/green]")


@app.command()
def query(
    text: str = typer.Argument(..., help="Search query for D&D rules"),
    n: int = typer.Option(5, "--n", "-n", help="Number of results to return"),
):
    """Search D&D rules corpus."""
    results = vector_store.search(text, n_results=n)

    if not results:
        console.print("[yellow]No results found. Is the corpus indexed?[/yellow]")
        return

    for i, result in enumerate(results, 1):
        source = result["metadata"].get("source", "Unknown")
        section = result["metadata"].get("section", "")
        distance = result.get("distance", 0)

        console.print(Panel(
            result["text"][:500] + ("..." if len(result["text"]) > 500 else ""),
            title=f"[{i}] {source}: {section}",
            subtitle=f"Distance: {distance:.4f}" if distance else None,
        ))


@app.command()
def test_ai():
    """Test connection to Ollama."""
    console.print("[bold]Testing Ollama connection...[/bold]")
    console.print(f"Model: {settings.ollama.model}")
    console.print(f"URL: {settings.ollama.base_url}")

    if ai_client.test_connection():
        console.print("[green]Connection successful![/green]")
    else:
        console.print("[red]Connection failed. Is Ollama running?[/red]")


def add_tree_node(tree: Tree, world: World, obj_id: int) -> None:
    """Recursively add world objects to a tree display."""
    obj = world.get_object(obj_id)
    if not obj:
        return

    label = f"[{obj.type}] {obj.name or 'unnamed'}"
    if obj.type == "PC":
        label = f"[bold cyan]{label}[/bold cyan]"

    node = tree.add(label)
    for child in world.get_children(obj_id):
        add_tree_node(node, world, child.id)


def save_campaign(campaign: Campaign, path: Path) -> None:
    """Save campaign to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "name": campaign.name,
        "seed": campaign.seed,
        "turn_number": campaign.turn_number,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": datetime.now().isoformat(),
        "world": campaign.world.model_dump_yaml(),
        "pcs": [pc.model_dump(mode="json") for pc in campaign.pcs],
        "npcs": [npc.model_dump(mode="json") for npc in campaign.npcs],
        "parties": [party.model_dump(mode="json") for party in campaign.parties],
    }

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def load_campaign_from_file(path: Path) -> Campaign:
    """Load campaign from YAML file."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Reconstruct world
    world_data = data["world"]
    world = World(
        name=world_data["name"],
        max_id=world_data["max_id"],
        delete_ids=world_data.get("delete_ids", []),
    )

    for obj_id_str, obj_data in world_data["objects"].items():
        obj = Object(
            id=obj_data["id"],
            parent=obj_data.get("parent"),
            type=obj_data["type"],
            name=obj_data.get("name"),
            description=obj_data.get("description"),
            location=Location.from_list(obj_data["location"]) if "location" in obj_data else Location(),
            weight=obj_data.get("weight", 0),
            cost=obj_data.get("cost", 0),
            is_moveable=obj_data.get("is_moveable", True),
            is_virtual=obj_data.get("is_virtual", False),
            properties=obj_data.get("properties", {}),
        )
        world.add_object(obj)

    # Reconstruct PCs
    pcs = []
    for pc_data in data.get("pcs", []):
        abilities_data = pc_data["abilities"]
        abilities = AbilityScores(
            str=abilities_data.get("str_", abilities_data.get("str", 10)),
            int=abilities_data.get("int_", abilities_data.get("int", 10)),
            wis=abilities_data.get("wis", 10),
            dex=abilities_data.get("dex", 10),
            con=abilities_data.get("con", 10),
            chr=abilities_data.get("chr", 10),
        )
        pc = PC(
            object_id=pc_data["object_id"],
            name=pc_data["name"],
            race=pc_data["race"],
            classes=[ClassLevel(**c) for c in pc_data.get("classes", [])],
            abilities=abilities,
            hp=HealthPool(**pc_data["hp"]),
            mana=HealthPool(**pc_data["mana"]) if pc_data.get("mana") else None,
            personality=pc_data.get("personality"),
            backstory=pc_data.get("backstory"),
            goals=pc_data.get("goals", []),
            experience=pc_data.get("experience", 0),
        )
        pcs.append(pc)

    # Reconstruct parties
    parties = [Party(**p) for p in data.get("parties", [])]

    return Campaign(
        name=data["name"],
        seed=data["seed"],
        world=world,
        pcs=pcs,
        npcs=[],
        parties=parties,
        turn_number=data.get("turn_number", 0),
        created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
    )


if __name__ == "__main__":
    app()
