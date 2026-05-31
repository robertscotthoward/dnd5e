"""D&D 5e AI Game Engine — FastAPI app and Typer CLI entry point."""

import sys
import random
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()
cli = typer.Typer(name="dnd5e", help="D&D 5e Agentic Campaign Engine")


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

@cli.command("index-corpus")
def cmd_index_corpus(
    force: bool = typer.Option(False, "--force", help="Re-index even if already indexed."),
) -> None:
    """Ingest all markdown files under data/corpus/ into ChromaDB via LlamaIndex."""
    from src.backend.core.vector_store import vector_store
    vector_store.index_corpus(force=force)


@cli.command("new-campaign")
def cmd_new_campaign(
    name: str = typer.Argument(..., help="Campaign name (used as folder name)."),
    seed: Optional[int] = typer.Option(None, "--seed", help="Fixed random seed. Auto-generated if omitted."),
) -> None:
    """Generate four randomized D&D 5e PCs, a party, and a seeded world YAML."""
    from src.backend.core.campaign_io import new_campaign_object, save_campaign

    if seed is None:
        seed = random.randint(1, 999_999)

    console.print(f"[bold]Creating campaign:[/bold] {name}")
    console.print(f"[bold]Seed:[/bold] {seed}")

    campaign = new_campaign_object(name, seed)

    campaigns_dir = Path(__file__).parent.parent.parent / "data" / "campaigns" / name
    campaigns_dir.mkdir(parents=True, exist_ok=True)
    world_path = campaigns_dir / "world.yaml"
    save_campaign(campaign, world_path)

    console.print(f"\n[green]World saved:[/green] {world_path}")
    console.print(f"[bold]Party:[/bold] The Adventurers")
    console.print(f"\n[bold]Player Characters:[/bold]")
    for obj in campaign.world.get_pcs():
        race = obj.properties.get("race", "Unknown")
        classes = obj.properties.get("classes", [])
        cls = classes[0]["type"] if classes else "Unknown"
        hp = obj.properties.get("hp", {})
        console.print(f"  - {obj.name} ({race} {cls}) — HP {hp.get('current', 0)}/{hp.get('max', 0)}")

    # Log seed to seeds.log
    seeds_log = campaigns_dir / "seeds.log"
    with open(seeds_log, "a", encoding="utf-8") as f:
        f.write(f"campaign_created seed={seed} name={name}\n")
    console.print(f"\n[dim]Seed logged to {seeds_log}[/dim]")


@cli.command("turn")
def cmd_turn(
    campaign: str = typer.Option(..., "--campaign", help="Campaign name."),
    situation: str = typer.Option(
        "The party rests in the Common Room of Stonehill Inn, waiting for adventure.",
        "--situation",
        help="Current situation description passed to the DM agent.",
    ),
) -> None:
    """Run one DM agent turn: query rules, update world, produce narrative, persist YAML."""
    from src.backend.core.campaign_io import load_campaign_from_file, save_campaign
    from src.backend.core.ai_client import ai_client
    from src.backend.core.tools import WorldTools

    # Resolve campaign file path
    campaigns_dir = Path(__file__).parent.parent.parent / "data" / "campaigns"
    # Accept bare name or explicit path
    candidate = Path(campaign)
    if candidate.exists():
        world_path = candidate
    else:
        # Try <name>/world.yaml
        world_path = campaigns_dir / campaign / "world.yaml"
        if not world_path.exists():
            # Try appending .yaml directly
            world_path = campaigns_dir / (campaign + ".yaml")

    if not world_path.exists():
        console.print(f"[red]Campaign file not found: {world_path}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Loading campaign:[/bold] {world_path}")
    campaign_obj = load_campaign_from_file(world_path)
    console.print(
        f"[dim]Turn {campaign_obj.turn_number} | Seed {campaign_obj.seed} | "
        f"{len(campaign_obj.world.objects)} objects[/dim]"
    )

    # Build world tools
    world_tools = WorldTools(campaign_obj.world)

    # Query rules for current situation
    console.print("\n[bold]Querying rules corpus...[/bold]")
    rules_context = ai_client.query_rules(situation)
    if rules_context == "No relevant rules found.":
        console.print("[yellow]No corpus indexed — DM will proceed without rules context.[/yellow]")
    else:
        console.print(f"[dim]Rules context: {len(rules_context)} chars[/dim]")

    # Run DM agent turn
    console.print("\n[bold]Running DM agent...[/bold]")
    narrative = ai_client.generate_dm_response(campaign_obj, situation, world_tools)

    # Advance turn counter and log event
    campaign_obj.advance_turn()
    campaign_obj.add_event(
        event_type="dm_narrative",
        description=narrative,
        seed=campaign_obj.seed,
    )

    # Persist updated world YAML
    save_campaign(campaign_obj, world_path)
    console.print(f"\n[green]World saved:[/green] {world_path}")

    # Append to seeds.log
    seeds_log = world_path.parent / "seeds.log"
    with open(seeds_log, "a", encoding="utf-8") as f:
        f.write(f"turn={campaign_obj.turn_number} seed={campaign_obj.seed} campaign={campaign_obj.name}\n")
    console.print(f"[dim]Seed logged to {seeds_log}[/dim]")

    # Print narrative
    console.print("\n[bold cyan]--- DM Narrative ---[/bold cyan]")
    console.print(narrative)
    console.print("[bold cyan]--------------------[/bold cyan]")


# ---------------------------------------------------------------------------
# FastAPI application (used by uvicorn)
# ---------------------------------------------------------------------------

def create_app():
    """Create and return the FastAPI application."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from src.backend.api.routes import router

    application = FastAPI(title="D&D 5e AI Game Engine")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router, prefix="/api")
    return application


# ---------------------------------------------------------------------------
# Entry point — Typer CLI if run as a module; FastAPI app as a module attribute
# ---------------------------------------------------------------------------

app = create_app()

if __name__ == "__main__":
    cli()
