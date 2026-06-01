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
    get_journal,
    get_players,
    list_campaigns,
    list_snapshots,
    load_campaign_world,
    restore_snapshot,
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
from src.backend.models.player import (
    CLASS_HIT_DICE,
    get_ability_modifier,
    apply_racial_modifiers,
    build_initial_spell_slots,
    CASTER_CLASSES,
)

router = APIRouter(tags=["campaigns"])


class CreateCampaignRequest(BaseModel):
    name: str
    seed: Optional[int] = None


class SnapshotRequest(BaseModel):
    label: str


class AwardXpRequest(BaseModel):
    character_id: int
    amount: int
    reason: Optional[str] = None


class LevelUpRequest(BaseModel):
    hp_gain: int
    asi_choices: dict[str, int] = {}  # e.g. {"str": 1, "con": 1}


class RollStatsRequest(BaseModel):
    race: str
    seed: Optional[int] = None


class GenerateBackgroundRequest(BaseModel):
    name: str
    race: str
    class_type: str
    region: str


@router.post("/campaigns/{campaign_id}/generate-background")
def generate_background(campaign_id: str, req: GenerateBackgroundRequest, request: Request):
    """
    Generate an AI background narrative for a character based on name, race, class, and region.

    Called during character creation before the character object is committed to the world.
    Safe to call multiple times for regeneration.
    """
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")

    try:
        prompt = (
            f"Write a 2-3 sentence D&D 5e character background for a {req.race} {req.class_type} "
            f"from {req.region} named {req.name}. Make it evocative and suitable for the Forgotten Realms."
        )
        background = ai_client.llm.complete(prompt).text.strip()
    except Exception as e:
        background = f"A {req.race} {req.class_type} from {req.region} seeking adventure."

    return {"background": background}


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
        campaign = load_campaign_world(campaign_id)
        if campaign:
            char_id = player["character_object_id"]
            char_obj = campaign.world.get_object(char_id)
            location = campaign.world.get_object(char_obj.parent) if char_obj else None
            location_name = location.name if location else "an unknown location"
            race = char_obj.properties.get("race", "Adventurer") if char_obj else "Adventurer"
            classes = char_obj.properties.get("classes", []) if char_obj else []
            class_str = "/".join(c.get("type", "?") for c in classes) if classes else "Unknown"
            hp = char_obj.properties.get("hp", {}) if char_obj else {}
            conditions = list(char_obj.properties.get("conditions", [])) if char_obj else []
            # Build visible surroundings list
            visible_objects = []
            if char_obj:
                for sibling in campaign.world.get_children(char_obj.parent):
                    if sibling.id != char_id and sibling.name:
                        visible_objects.append(f"{sibling.name} ({sibling.type})")
                # Also list notable items in the location container itself
                loc_children = campaign.world.get_children(char_obj.parent) if location else []
                for item in loc_children:
                    if item.type not in ("PC", "NPC", "party") and item.name:
                        if f"{item.name} ({item.type})" not in visible_objects:
                            visible_objects.append(f"{item.name} ({item.type})")
            # Nearby party members
            nearby_party = []
            if char_obj:
                for sibling in campaign.world.get_children(char_obj.parent):
                    if sibling.id != char_id and sibling.type in ("PC", "NPC") and sibling.name:
                        nearby_party.append(sibling.name)
            recent_messages = [m.model_dump(mode="json") for m in get_chat(campaign_id, limit=20)]
            summary = ai_client.generate_dm_recap(
                character_name=player["character_name"] or "Adventurer",
                race=race,
                class_str=class_str,
                location_name=location_name,
                turn_number=meta.turn_number,
                recent_messages=recent_messages,
                hp_current=hp.get("current", 0),
                hp_max=hp.get("max", 0),
                conditions=conditions,
                visible_objects=visible_objects,
                nearby_party=nearby_party,
                is_new_character=False,
            )
        else:
            summary = (
                f"Welcome back, {player['character_name']}! "
                f"Your adventure awaits on turn {meta.turn_number}."
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

    spell_slots = build_initial_spell_slots(char_req.class_type, 1)

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
            "spell_slots": spell_slots,
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

    # Build opening scene context
    party_obj = campaign.world.get_object(party_id)
    location_name = party_obj.name if party_obj else "the realm"
    visible_objects = [
        f"{o.name} ({o.type})"
        for o in campaign.world.get_children(party_id)
        if o.id != char_obj.id and o.name and o.type not in ("PC", "NPC")
    ]
    nearby_party = [
        o.name
        for o in campaign.world.get_children(party_id)
        if o.id != char_obj.id and o.type in ("PC", "NPC") and o.name
    ]
    summary = ai_client.generate_dm_recap(
        character_name=char_req.name,
        race=char_req.race,
        class_str=char_req.class_type,
        location_name=location_name,
        turn_number=meta.turn_number,
        recent_messages=[],
        hp_current=max_hp,
        hp_max=max_hp,
        conditions=[],
        visible_objects=visible_objects,
        nearby_party=nearby_party,
        is_new_character=True,
    )

    return {
        "character_object_id": char_obj.id,
        "name": char_req.name,
        "race": char_req.race,
        "class_type": char_req.class_type,
        "hp": {"current": max_hp, "max": max_hp},
        "abilities": abilities,
        "background": background,
        "summary": summary,
    }


@router.get("/campaigns/{campaign_id}/state")
def get_state(campaign_id: str, request: Request):
    """Return the full campaign state: meta, players, recent chat, and initiative order."""
    session = get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    players = get_players(campaign_id)
    chat = get_chat(campaign_id, limit=100)

    initiative_order = []
    if meta.game_mode == "Combat" and meta.combat_queue:
        campaign = load_campaign_world(campaign_id)
        if campaign:
            for obj_id in meta.combat_queue:
                obj = campaign.world.get_object(obj_id)
                initiative_order.append({
                    "id": obj_id,
                    "name": (obj.name if obj else f"Combatant #{obj_id}"),
                    "initiative": obj.properties.get("initiative", 0) if obj else 0,
                })

    return {
        "meta": meta,
        "players": players,
        "chat": chat,
        "initiative_order": initiative_order,
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


@router.post("/campaigns/{campaign_id}/award-xp")
def award_xp(campaign_id: str, req: AwardXpRequest, request: Request):
    """
    Award XP to a character and return the updated XP totals.

    If a level-up occurs the response includes a ``level_up`` block with
    details for the frontend dialog (hit die, ASI flag, new level).
    """
    session = get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    from src.backend.core.tools import WorldTools

    tools = WorldTools(campaign.world)
    result = tools.award_xp(req.character_id, req.amount)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    save_campaign_world(campaign_id, campaign)

    reason_text = f" ({req.reason})" if req.reason else ""
    sys_msg = ChatMessage(
        sender="SYSTEM",
        sender_type="SYSTEM",
        text=f"{result.data['new_xp'] - result.data['old_xp']} XP awarded{reason_text}. "
             f"Total: {result.data['new_xp']} XP (Level {result.data['new_level']}).",
        turn_number=meta.turn_number,
    )
    append_chat(campaign_id, sys_msg)

    return result.data


@router.post("/campaigns/{campaign_id}/characters/{character_id}/level-up")
def apply_level_up(
    campaign_id: str,
    character_id: int,
    req: LevelUpRequest,
    request: Request,
):
    """
    Apply level-up choices (hit die roll result and ASI selections) to a character.

    Called from the frontend LevelUpDialog after the player confirms their choices.
    """
    session = get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    char_obj = campaign.world.get_object(character_id)
    if not char_obj:
        raise HTTPException(status_code=404, detail=f"Character {character_id} not found")

    # Apply HP gain
    if req.hp_gain > 0:
        hp = char_obj.properties.get("hp", {"current": 1, "max": 1})
        hp["max"] = hp.get("max", 1) + req.hp_gain
        hp["current"] = hp.get("current", 1) + req.hp_gain
        char_obj.properties["hp"] = hp

    # Apply ASI choices
    if req.asi_choices:
        abilities = char_obj.properties.get("abilities", {})
        for ab_key, bonus in req.asi_choices.items():
            if ab_key in abilities:
                abilities[ab_key] = abilities[ab_key] + bonus
        char_obj.properties["abilities"] = abilities

    save_campaign_world(campaign_id, campaign)

    # Update player record with new HP
    hp_data = char_obj.properties.get("hp", {})
    update_player_character(
        campaign_id,
        session.user_id,
        char_obj.id,
        char_obj.name,
        char_obj.properties.get("race"),
        char_obj.properties.get("classes", [{}])[0].get("type") if char_obj.properties.get("classes") else None,
        hp_data.get("max", 0),
        hp_data.get("current", 0),
    )

    return {
        "character_id": character_id,
        "hp": char_obj.properties.get("hp"),
        "abilities": char_obj.properties.get("abilities"),
    }


class CastSpellRequest(BaseModel):
    slot_level: int


class EquipItemRequest(BaseModel):
    equipped: bool


@router.post("/campaigns/{campaign_id}/characters/{character_id}/cast-spell")
def cast_spell(campaign_id: str, character_id: int, req: CastSpellRequest, request: Request):
    """
    Consume one spell slot of the given level for a caster character.

    Returns updated spell_slots for the character.
    """
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    from src.backend.core.tools import WorldTools

    tools = WorldTools(campaign.world)
    result = tools.cast_spell(character_id, req.slot_level)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    save_campaign_world(campaign_id, campaign)
    char_obj = campaign.world.get_object(character_id)
    return {"spell_slots": char_obj.properties.get("spell_slots", {}), "message": result.message}


@router.post("/campaigns/{campaign_id}/characters/{character_id}/long-rest")
def long_rest(campaign_id: str, character_id: int, request: Request):
    """
    Perform a long rest: restore all spell slots and full HP for the character.
    """
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    from src.backend.core.tools import WorldTools

    tools = WorldTools(campaign.world)
    result = tools.long_rest(character_id)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    save_campaign_world(campaign_id, campaign)
    return result.data


@router.post("/campaigns/{campaign_id}/characters/{character_id}/items/{item_id}/equip")
def equip_item(
    campaign_id: str,
    character_id: int,
    item_id: int,
    req: EquipItemRequest,
    request: Request,
):
    """
    Set the equipped state of an item carried by a character.

    The item must be a direct child of the character object. Calls
    set_object_property(item_id, 'equipped', req.equipped).
    """
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    char_obj = campaign.world.get_object(character_id)
    if not char_obj or char_obj.type != "PC":
        raise HTTPException(status_code=404, detail="Character not found")

    item_obj = campaign.world.get_object(item_id)
    if not item_obj or item_obj.parent != character_id:
        raise HTTPException(status_code=404, detail="Item not found on character")

    from src.backend.core.tools import WorldTools

    tools = WorldTools(campaign.world)
    result = tools.set_object_property(item_id, "equipped", req.equipped)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    save_campaign_world(campaign_id, campaign)
    return {"item_id": item_id, "equipped": req.equipped}


@router.get("/campaigns/{campaign_id}/characters/{character_id}")
def get_character(campaign_id: str, character_id: int, request: Request):
    """
    Return full character sheet data for a PC from their world object properties.

    Includes ability scores, modifiers, classes, proficiencies, features,
    equipped/carried items, carry capacity (STR * 15), and current HP.
    """
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    char_obj = campaign.world.get_object(character_id)
    if not char_obj or char_obj.type != "PC":
        raise HTTPException(status_code=404, detail="Character not found")

    props = char_obj.properties
    abilities = props.get("abilities", {})

    def mod(score: int) -> int:
        return (score - 10) // 2

    ability_block = {
        key: {"score": score, "modifier": mod(score)}
        for key, score in abilities.items()
    }

    # Carry capacity = STR score * 15 (D&D 5e rule)
    str_score = abilities.get("str", 10)
    carry_capacity = str_score * 15

    # Gather carried items from world children
    children = campaign.world.get_children(character_id)
    items = [
        {
            "id": c.id,
            "name": c.name or c.type,
            "type": c.type,
            "weight": c.weight,
            "cost": c.cost,
            "equipped": c.properties.get("equipped", False),
            "description": c.description,
        }
        for c in children
    ]

    return {
        "id": char_obj.id,
        "name": char_obj.name,
        "description": char_obj.description,
        "race": props.get("race", "Unknown"),
        "classes": props.get("classes", []),
        "abilities": ability_block,
        "hp": props.get("hp", {"current": 0, "max": 0}),
        "experience": props.get("experience", 0),
        "background": props.get("background", ""),
        "region": props.get("region", ""),
        "proficiencies": props.get("proficiencies", []),
        "features": props.get("features", []),
        "conditions": props.get("conditions", []),
        "death_saves": props.get("death_saves", {"successes": 0, "failures": 0}),
        "spell_slots": props.get("spell_slots", {}),
        "items": items,
        "carry_capacity": carry_capacity,
        "personality": props.get("personality", ""),
        "goals": props.get("goals", []),
    }


class AddQuestRequest(BaseModel):
    title: str
    milestones: list[str]


class CompleteMilestoneRequest(BaseModel):
    quest_id: int
    milestone_idx: int


@router.get("/campaigns/{campaign_id}/quests")
def get_quests(campaign_id: str, request: Request):
    """Return all quests for a campaign."""
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    from src.backend.core.tools import WorldTools

    tools = WorldTools(campaign.world)
    result = tools.get_quests()
    return {"quests": result.data["quests"]}


@router.post("/campaigns/{campaign_id}/quests")
def post_quest(campaign_id: str, req: AddQuestRequest, request: Request):
    """Add a new quest to the campaign world."""
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    from src.backend.core.tools import WorldTools

    tools = WorldTools(campaign.world)
    result = tools.add_quest(req.title, req.milestones)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    save_campaign_world(campaign_id, campaign)
    return result.data


@router.post("/campaigns/{campaign_id}/quests/complete-milestone")
def post_complete_milestone(campaign_id: str, req: CompleteMilestoneRequest, request: Request):
    """Mark a quest milestone as completed."""
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    from src.backend.core.tools import WorldTools

    tools = WorldTools(campaign.world)
    result = tools.complete_milestone(req.quest_id, req.milestone_idx)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    save_campaign_world(campaign_id, campaign)
    return result.data


@router.get("/campaigns/{campaign_id}/journal")
def get_campaign_journal(campaign_id: str):
    """Return the full journal.md text for a campaign."""
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"journal": get_journal(campaign_id)}


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


@router.get("/campaigns/{campaign_id}/npcs")
def get_npcs(campaign_id: str, request: Request):
    """Return all known NPCs and their dispositions for a campaign."""
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    from src.backend.core.tools import WorldTools

    tools = WorldTools(campaign.world)
    result = tools.get_npc_relationships()
    return {"npcs": result.data["npcs"]}


@router.get("/campaigns/{campaign_id}/map")
def get_map(campaign_id: str, request: Request):
    """
    Return all world objects with their computed absolute [x, y, z] positions.

    Absolute position = recursive sum of location offsets up the parent chain.
    Objects with no location (or location [0,0,0]) are placed at their parent's
    absolute position.  The player character for the authenticated user is flagged
    with is_player=True so the frontend can highlight and auto-center on them.
    """
    session = get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=500, detail="Could not load world")

    # Compute absolute positions via memoised DFS
    abs_pos: dict[int, tuple[float, float, float]] = {}

    def get_abs(obj_id: int) -> tuple[float, float, float]:
        if obj_id in abs_pos:
            return abs_pos[obj_id]
        obj = campaign.world.get_object(obj_id)
        if obj is None:
            abs_pos[obj_id] = (0.0, 0.0, 0.0)
            return abs_pos[obj_id]
        lx, ly, lz = obj.location.x, obj.location.y, obj.location.z
        if obj.parent is None:
            abs_pos[obj_id] = (lx, ly, lz)
        else:
            px, py, pz = get_abs(obj.parent)
            abs_pos[obj_id] = (px + lx, py + ly, pz + lz)
        return abs_pos[obj_id]

    player = find_player(campaign_id, session.user_id)
    player_char_id = player.get("character_object_id") if player else None

    nodes = []
    for obj in campaign.world.objects.values():
        ax, ay, az = get_abs(obj.id)
        nodes.append({
            "id": obj.id,
            "parent": obj.parent,
            "type": obj.type,
            "name": obj.name or obj.type,
            "description": obj.description or "",
            "x": ax,
            "y": ay,
            "z": az,
            "is_moveable": obj.is_moveable,
            "is_virtual": obj.is_virtual,
            "is_player": obj.id == player_char_id,
        })

    return {"nodes": nodes}


@router.post("/campaigns/{campaign_id}/snapshots/{snapshot_id}/restore")
def post_snapshot_restore(campaign_id: str, snapshot_id: str, request: Request):
    """
    Restore a campaign to a snapshot state.

    Copies snapshot files (world.yaml, players.json, chat.json) back to the
    campaign root. The campaign meta.json is not overwritten so the campaign
    identity (id, name, created_by) is preserved.
    """
    get_current_user(request)
    meta = get_campaign_meta(campaign_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Campaign not found")
    try:
        snap = restore_snapshot(campaign_id, snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"restored": True, "snapshot": snap}
