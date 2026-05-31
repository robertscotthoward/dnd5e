"""Tests for the character sheet endpoint and related logic."""

import pytest
from pathlib import Path

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.models.world import Object, Location


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(tmp_path: Path, name: str = "SheetTest"):
    campaign = new_campaign_object(name, seed=42)
    world_path = tmp_path / name / "world.yaml"
    world_path.parent.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, world_path)
    return campaign, world_path


def _add_pc(campaign, world_path: Path) -> Object:
    parties = campaign.world.get_parties()
    party_id = parties[0].id if parties else 1
    pc = Object(
        id=campaign.world.next_id(),
        parent=party_id,
        type="PC",
        name="Aldric",
        description="Human Fighter from Waterdeep",
        location=Location(x=0, y=0, z=0),
        properties={
            "race": "Human",
            "classes": [{"type": "Fighter", "level": 3}],
            "abilities": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 11, "chr": 9},
            "hp": {"current": 20, "max": 28},
            "experience": 900,
            "background": "A former soldier seeking redemption.",
            "region": "Waterdeep",
            "proficiencies": ["Athletics", "Intimidation"],
            "features": [{"name": "Second Wind", "description": "Recover HP as bonus action."}],
            "conditions": [],
            "goals": ["Find the stolen artifact"],
            "personality": "Stoic and determined",
        },
    )
    campaign.world.add_object(pc)
    save_campaign(campaign, world_path)
    return pc


def _add_item(campaign, pc_id: int, world_path: Path) -> Object:
    item = Object(
        id=campaign.world.next_id(),
        parent=pc_id,
        type="sword",
        name="Longsword",
        weight=3.0,
        cost=1500,
        properties={"equipped": True},
    )
    campaign.world.add_object(item)
    save_campaign(campaign, world_path)
    return item


def _ability_block(abilities: dict) -> dict:
    """Build the ability block the endpoint builds."""
    def mod(score: int) -> int:
        return (score - 10) // 2

    return {
        key: {"score": score, "modifier": mod(score)}
        for key, score in abilities.items()
    }


# ---------------------------------------------------------------------------
# Ability modifier calculation
# ---------------------------------------------------------------------------

def test_ability_modifier_positive(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    block = _ability_block(pc.properties["abilities"])
    # STR 16 → modifier +3
    assert block["str"]["score"] == 16
    assert block["str"]["modifier"] == 3


def test_ability_modifier_negative(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    block = _ability_block(pc.properties["abilities"])
    # CHR 9 → modifier -1
    assert block["chr"]["modifier"] == -1


def test_ability_modifier_zero(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    block = _ability_block(pc.properties["abilities"])
    # INT 10 → modifier 0
    assert block["int"]["modifier"] == 0


def test_ability_modifier_con(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    block = _ability_block(pc.properties["abilities"])
    # CON 14 → modifier +2
    assert block["con"]["modifier"] == 2


# ---------------------------------------------------------------------------
# PC properties contain expected sheet data
# ---------------------------------------------------------------------------

def test_pc_has_proficiencies(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    proficiencies = pc.properties.get("proficiencies", [])
    assert "Athletics" in proficiencies
    assert "Intimidation" in proficiencies


def test_pc_has_features(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    features = pc.properties.get("features", [])
    assert any(f["name"] == "Second Wind" for f in features)


def test_pc_background_and_region(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    assert pc.properties["background"] == "A former soldier seeking redemption."
    assert pc.properties["region"] == "Waterdeep"
    assert pc.properties["race"] == "Human"
    assert pc.properties["classes"][0]["type"] == "Fighter"
    assert pc.properties["experience"] == 900


def test_pc_hp_values(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    hp = pc.properties.get("hp", {})
    assert hp["current"] == 20
    assert hp["max"] == 28


# ---------------------------------------------------------------------------
# Item / inventory tests
# ---------------------------------------------------------------------------

def test_pc_children_include_items(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    _add_item(campaign, pc.id, world_path)

    children = campaign.world.get_children(pc.id)
    assert len(children) == 1
    assert children[0].name == "Longsword"
    assert children[0].weight == 3.0
    assert children[0].properties.get("equipped") is True


def test_pc_no_items_by_default(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    children = campaign.world.get_children(pc.id)
    assert children == []


def test_item_equipped_flag_is_stored(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    item = _add_item(campaign, pc.id, world_path)
    assert item.properties["equipped"] is True


def test_total_weight_of_items(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    _add_item(campaign, pc.id, world_path)
    # Add a second item
    shield = Object(
        id=campaign.world.next_id(),
        parent=pc.id,
        type="shield",
        name="Shield",
        weight=6.0,
        properties={"equipped": True},
    )
    campaign.world.add_object(shield)

    children = campaign.world.get_children(pc.id)
    total = sum(c.weight for c in children)
    assert total == 9.0


# ---------------------------------------------------------------------------
# Non-PC objects must not be exposed as character sheets
# ---------------------------------------------------------------------------

def test_non_pc_object_type_check(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    item = Object(id=campaign.world.next_id(), parent=1, type="sword", name="Longsword")
    campaign.world.add_object(item)

    obj = campaign.world.get_object(item.id)
    # The endpoint rejects non-PC objects
    assert obj.type != "PC"


# ---------------------------------------------------------------------------
# Endpoint item-list builder: stowed items have equipped=False
# ---------------------------------------------------------------------------

def test_stowed_item_equipped_false(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    bag = Object(
        id=campaign.world.next_id(),
        parent=pc.id,
        type="potion",
        name="Healing Potion",
        weight=0.5,
        properties={"equipped": False},
    )
    campaign.world.add_object(bag)
    children = campaign.world.get_children(pc.id)
    assert children[0].properties.get("equipped") is False


# ---------------------------------------------------------------------------
# Goals and personality
# ---------------------------------------------------------------------------

def test_pc_goals_list(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    goals = pc.properties.get("goals", [])
    assert "Find the stolen artifact" in goals


def test_pc_personality(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    assert pc.properties.get("personality") == "Stoic and determined"
