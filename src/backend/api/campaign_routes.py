"""Campaign management API endpoints."""

import random
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.backend.core.auth import get_current_user
from src.backend.core.campaign_manager import (
    add_player,
    append_chat,
    campaign_path,
    create_campaign as mgr_create_campaign,
    create_snapshot,
    find_player,
    get_campaign_meta,
    get_chat,
    get_players,
    list_campaigns,
    list_snapshots,
    load_campaign_world,
    save_campaign_meta,
    save_campaign_world,
    update_player_character,
)
from src.backend.core.campaign_io import (
    generate_ability_scores,
    generate_ability_scores_detailed,
    roll_bonus_die,
)
from src.backend.models.player import RACE_MODIFIERS
from src.backend.core.ai_client import ai_client
from src.backend.models.user import CampaignMeta, CharacterCreate, ChatMessage, Snapshot
from src.backend.models.world import Object, Location
from src.backend.models.player import CLASS_HIT_DICE, get_ability_modifier, apply_racial_modifiers

router = APIRouter(tags=["campaigns"])


class CreateCampaignRequest(BaseModel):
    name: str
    seed: Optional[int] = None


class SnapshotRequest(BaseModel):
    label: str


class RollStatsRequest(BaseModel):
    race: str
    seed: Optional[int] = None


@router.post("/campaigns/{campaign_id}/roll-stats")
def roll_stats(campaign_id: str, req: RollStatsRequest, request: Request):
    """
    Roll 4d6 drop-lowest ability scores for character creation.

    Returns per-die detail, racial bonuses for the chosen race, and a bonus d6
    that the player may freely distribute across abilities.
    """
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")

    seed = req.seed if req.seed is not None else random.randint(1, 999999)
    rolls = generate_ability_scores_detailed(seed)
    bonus = roll_bonus_die(seed)
    racial_bonuses = RACE_MODIFIERS.get(req.race, {})

    return {
        "seed": seed,
        "rolls": rolls,
        "bonus_die": bonus,
        "racial_bonuses": racial_bonuses,
    }


@router.get("/campaigns")
def get_campaigns():
    """List all available campaigns."""
    return list_campaigns()


@router.post("/campaigns")
def post_campaign(req: CreateCampaignRequest, request: Request):
    """Create a new campaign. Requires authentication."""
    session = get_current_user(request)
    meta = mgr_create_campaign(req.name, session.username, req.seed)
    return meta


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str):
    """Get campaign metadata and current player list."""
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    players = get_players(campaign_id)
    return {"meta": meta, "players": players}


@router.post("/campaigns/{campaign_id}/join")
def join_campaign(campaign_id: str, request: Request):
    """
    Join a campaign as the authenticated user.

    Returns whether a character still needs to be created, the player record, and an
    optional DM summary if returning to an existing character.
    """
    session = get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    player = add_player(campaign_id, session.user_id, session.username)
    needs_character = player.get("character_object_id") is None
    summary = None
    if not needs_character:
        # Generate a DM summary of where they left off
        campaign = load_campaign_world(campaign_id)
        if campaign:
            char_id = player["character_object_id"]
            char_obj = campaign.world.get_object(char_id)
            location = campaign.world.get_object(char_obj.parent) if char_obj else None
            summary = (
                f"Welcome back, {player['character_name']}! "
                f"You are in {location.name if location else 'an unknown location'} "
                f"on turn {meta.turn_number}."
            )
    return {
        "needs_character": needs_character,
        "player": player,
        "summary": summary,
    }


@router.post("/campaigns/{campaign_id}/characters")
def create_character(campaign_id: str, char_req: CharacterCreate, request: Request):
    """
    Create a PC object in the world and link it to the authenticated user.

    Generates ability scores, applies racial modifiers, calculates HP, and
    optionally uses AI to write a background if none is provided.
    """
    session = get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    player = find_player(campaign_id, session.user_id)
    if not player:
        raise HTTPException(status_code=400, detail="Join the campaign first")
    if player.get("character_object_id") is not None:
        raise HTTPException(status_code=400, detail="Character already created")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load campaign world")

    # Generate or use provided background
    background = char_req.background
    if not background:
        try:
            prompt = (
                f"Write a 2-3 sentence D&D 5e character background for a {char_req.race} {char_req.class_type} "
                f"from {char_req.region} named {char_req.name}. Make it evocative and suitable for the Forgotten Realms."
            )
            background = ai_client.llm.complete(prompt).text.strip()
        except Exception:
            background = f"A {char_req.race} {char_req.class_type} from {char_req.region} seeking adventure."

    # Use player-rolled abilities if provided, otherwise generate randomly
    if char_req.abilities:
        abilities = char_req.abilities
    else:
        seed = random.randint(1, 999999)
        abilities = generate_ability_scores(seed)
        abilities = apply_racial_modifiers(abilities, char_req.race)

    con_mod = get_ability_modifier(abilities["con"])
    hit_die = CLASS_HIT_DICE.get(char_req.class_type, 8)
    max_hp = max(1, hit_die + con_mod)

    # Find the party object (first party, or fall back to Common Room id=7)
    parties = campaign.world.get_parties()
    party_id = parties[0].id if parties else 7

    char_obj = Object(
        id=campaign.world.next_id(),
        parent=party_id,
        type="PC",
        name=char_req.name,
        description=f"{char_req.race} {char_req.class_type} from {char_req.region}",
        location=Location(x=0, y=0, z=0),
        properties={
            "race": char_req.race,
            "classes": [{"type": char_req.class_type, "level": 1}],
            "abilities": abilities,
            "hp": {"max": max_hp, "current": max_hp},
            "background": background,
            "region": char_req.region,
            "personality": "",
            "goals": ["Survive and prosper"],
            "experience": 0,
            "player_controlled": True,
            "user_id": session.user_id,
        },
    )
    campaign.world.add_object(char_obj)
    save_campaign_world(campaign_id, campaign)

    update_player_character(
        campaign_id,
        session.user_id,
        char_obj.id,
        char_req.name,
        char_req.race,
        char_req.class_type,
        max_hp,
        max_hp,
    )

    return {
        "character_object_id": char_obj.id,
        "name": char_req.name,
        "race": char_req.race,
        "class_type": char_req.class_type,
        "hp": {"current": max_hp, "max": max_hp},
        "abilities": abilities,
        "background": background,
    }


@router.get("/campaigns/{campaign_id}/state")
def get_state(campaign_id: str, request: Request):
    """Return the full campaign state: meta, players, and recent chat."""
    session = get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    players = get_players(campaign_id)
    chat = get_chat(campaign_id, limit=100)
    return {
        "meta": meta,
        "players": players,
        "chat": chat,
    }


@router.post("/campaigns/{campaign_id}/turn")
def advance_turn(campaign_id: str, request: Request):
    """
    Execute one AI-driven game turn.

    Advances the turn counter, calls the DM agent for narration, saves the
    updated world, appends the DM message to chat, and returns the narration.
    """
    session = get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    from src.backend.core.tools import WorldTools

    campaign.advance_turn()
    tools = WorldTools(campaign.world)
    situation = f"Turn {campaign.turn_number} begins. The party is adventuring."
    narration = ai_client.generate_dm_response(campaign, situation, tools)

    save_campaign_world(campaign_id, campaign)
    meta.turn_number = campaign.turn_number
    meta.updated_at = datetime.now().isoformat()
    save_campaign_meta(meta)

    # Save DM message to chat
    dm_msg = ChatMessage(
        sender="DM",
        sender_type="DM",
        text=narration,
        turn_number=campaign.turn_number,
    )
    append_chat(campaign_id, dm_msg)

    return {"narration": narration, "turn_number": campaign.turn_number}


@router.get("/campaigns/{campaign_id}/chat")
def get_campaign_chat(campaign_id: str, limit: int = 100):
    """Return recent chat messages for a campaign."""
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return get_chat(campaign_id, limit)


@router.get("/campaigns/{campaign_id}/snapshots")
def get_snapshots(campaign_id: str):
    """List all snapshots for a campaign."""
    return list_snapshots(campaign_id)


@router.post("/campaigns/{campaign_id}/snapshots")
def post_snapshot(campaign_id: str, req: SnapshotRequest, request: Request):
    """Create a snapshot of the current campaign state. Requires authentication."""
    session = get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    snap = create_snapshot(campaign_id, req.label, session.username)
    return snap
