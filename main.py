"""D&D 5e AI Game Engine - CLI Entry Point."""

import random
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from src.backend.core.config import settings
from src.backend.core.vector_store import vector_store
from src.backend.core.ai_client import ai_client
from src.backend.core.tools import WorldTools
from src.backend.core.campaign_io import (
    generate_ability_scores,
    create_default_world,
    create_default_pcs,
    save_campaign,
    load_campaign_from_file,
)
from src.backend.models.world import World, Object, Location, Size
from src.backend.models.player import RACE_MODIFIERS, CLASS_HIT_DICE, get_ability_modifier, apply_racial_modifiers
from src.backend.models.game import Campaign, GameState

app = typer.Typer(
    name="dnd5e",
    help="D&D 5e AI-powered game engine with agents for DM, Players, and World simulation",
    no_args_is_help=True,
)
console = Console()

# Global game state
game_state = GameState()


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
    console.print(f"Created world with {len(world.objects)} location objects")

    # Create party (PCs will be children of the party)
    party = Object(
        id=world.next_id(),
        parent=7,  # Common room
        type="party",
        name="The Adventurers",
        description="A band of adventurers seeking fortune and glory",
        is_virtual=True,
    )
    world.add_object(party)

    # Create PCs as children of the party
    create_default_pcs(world, party.id, seed)
    console.print(f"Created {len(world.get_pcs())} player characters")

    # Create campaign (just world + metadata, no separate pcs/parties lists)
    campaign = Campaign(
        name=name,
        seed=seed,
        world=world,
    )

    # Save campaign
    save_path = settings.worlds_path / f"{name}.yaml"
    save_campaign(campaign, save_path)

    # Load into game state
    game_state.load_campaign(campaign, str(save_path))

    console.print(f"[green]Campaign saved to: {save_path}[/green]")

    # Show summary
    _show_status()


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
    _show_status()


@app.command()
def turn(
    campaign_file: Optional[Path] = typer.Option(None, "--campaign", "-c", help="Campaign file to load"),
):
    """Execute one game turn (DM + players act)."""
    # Load campaign if specified
    if campaign_file:
        if not campaign_file.exists():
            campaign_file = settings.worlds_path / campaign_file
        if campaign_file.exists():
            campaign = load_campaign_from_file(campaign_file)
            game_state.load_campaign(campaign, str(campaign_file))

    if not game_state.has_campaign:
        console.print("[red]No campaign loaded. Use 'new-campaign' or 'load-campaign' first.[/red]")
        console.print("[dim]Or use: turn --campaign <file>[/dim]")
        raise typer.Exit(1)

    campaign = game_state.campaign
    campaign.advance_turn()

    console.print(Panel(f"[bold]Turn {campaign.turn_number}[/bold]", title="Game Turn"))

    # Create tools for this turn
    tools = WorldTools(campaign.world)

    # 1. World Agent: Update environment
    console.print("\n[dim]World updates...[/dim]")
    world_update = ai_client.generate_world_update(campaign)
    if world_update:
        console.print(f"[italic]{world_update}[/italic]")

    # 2. Each player acts
    pcs = campaign.world.get_pcs()
    for pc in pcs:
        if pc.is_dead:
            continue

        console.print(f"\n[bold blue]{pc.name}'s turn[/bold blue]")
        location = campaign.world.get_object(pc.parent)
        location_name = location.name if location else "unknown location"
        situation = f"Turn {campaign.turn_number}. The party is in {location_name}."
        action = ai_client.generate_player_action(campaign, pc.id, situation)
        console.print(f"[cyan]{action}[/cyan]")

    # 3. DM resolves and narrates
    console.print("\n[bold yellow]Dungeon Master[/bold yellow]")
    situation = "The party has completed their actions. Resolve any outcomes and narrate what happens."
    dm_response = ai_client.generate_dm_response(campaign, situation, tools)
    console.print(dm_response)

    # Save campaign
    save_campaign(campaign, Path(game_state.campaign_file))
    console.print(f"\n[dim]Campaign saved. Turn {campaign.turn_number} complete.[/dim]")


def _show_status() -> None:
    """Internal function to display game status."""
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
    pcs = campaign.world.get_pcs()
    if pcs:
        table = Table(title="Player Characters")
        table.add_column("ID", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Race")
        table.add_column("Class")
        table.add_column("Level")
        table.add_column("HP", justify="right")
        table.add_column("Status")

        for pc in pcs:
            classes = pc.properties.get("classes", [])
            class_str = "/".join(c.get("type", "?") for c in classes) if classes else "Unknown"
            level = sum(c.get("level", 1) for c in classes) if classes else 1
            hp = pc.properties.get("hp", {})
            hp_str = f"{hp.get('current', '?')}/{hp.get('max', '?')}"
            status_str = "[red]Dead[/red]" if pc.is_dead else "[green]Alive[/green]"
            table.add_row(
                str(pc.id),
                pc.name or "Unknown",
                pc.properties.get("race", "Unknown"),
                class_str,
                str(level),
                hp_str,
                status_str,
            )

        console.print(table)


@app.command()
def status(
    campaign_file: Optional[Path] = typer.Option(None, "--campaign", "-c", help="Campaign file to load"),
):
    """Show current game state."""
    # Load campaign if specified
    if campaign_file is not None:
        if not campaign_file.exists():
            campaign_file = settings.worlds_path / campaign_file
        if campaign_file.exists():
            campaign = load_campaign_from_file(campaign_file)
            game_state.load_campaign(campaign, str(campaign_file))

    _show_status()


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
    elif obj.type == "party":
        label = f"[bold green]{label}[/bold green]"

    node = tree.add(label)
    for child in world.get_children(obj_id):
        add_tree_node(node, world, child.id)


if __name__ == "__main__":
    app()
