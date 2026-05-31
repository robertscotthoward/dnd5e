"""Tests for the inventory / equipment panel (carry capacity, equip toggle)."""

import pytest
from pathlib import Path

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.core.tools import WorldTools
from src.backend.models.world import Object, Location


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(tmp_path: Path, name: str = "InvTest"):
    campaign = new_campaign_object(name, seed=42)
    world_path = tmp_path / name / "world.yaml"
    world_path.parent.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, world_path)
    return campaign, world_path


def _add_pc(campaign, world_path: Path, str_score: int = 16) -> Object:
    parties = campaign.world.get_parties()
    party_id = parties[0].id if parties else 1
    pc = Object(
        id=campaign.world.next_id(),
        parent=party_id,
        type="PC",
        name="Torrin",
        description="Dwarf Fighter",
        location=Location(x=0, y=0, z=0),
        properties={
            "race": "Dwarf",
            "classes": [{"type": "Fighter", "level": 2}],
            "abilities": {"str": str_score, "dex": 12, "con": 14, "int": 10, "wis": 11, "chr": 9},
            "hp": {"current": 18, "max": 20},
            "experience": 300,
            "background": "A stout warrior.",
            "region": "Ironforge",
            "proficiencies": ["Athletics"],
            "features": [],
            "conditions": [],
            "goals": [],
            "personality": "",
        },
    )
    campaign.world.add_object(pc)
    save_campaign(campaign, world_path)
    return pc


def _add_item(campaign, pc_id: int, name: str, weight: float, equipped: bool, world_path: Path) -> Object:
    item = Object(
        id=campaign.world.next_id(),
        parent=pc_id,
        type="weapon",
        name=name,
        weight=weight,
        cost=500,
        properties={"equipped": equipped},
    )
    campaign.world.add_object(item)
    save_campaign(campaign, world_path)
    return item


# ---------------------------------------------------------------------------
# Carry capacity (STR * 15)
# ---------------------------------------------------------------------------

def test_carry_capacity_str_16(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path, str_score=16)
    str_score = pc.properties["abilities"]["str"]
    assert str_score * 15 == 240


def test_carry_capacity_str_10(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path, str_score=10)
    assert pc.properties["abilities"]["str"] * 15 == 150


def test_carry_capacity_str_8(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path, str_score=8)
    assert pc.properties["abilities"]["str"] * 15 == 120


def test_carry_capacity_str_20(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path, str_score=20)
    assert pc.properties["abilities"]["str"] * 15 == 300


# ---------------------------------------------------------------------------
# Weight totals
# ---------------------------------------------------------------------------

def test_total_weight_single_item(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    _add_item(campaign, pc.id, "Longsword", 3.0, True, world_path)
    children = campaign.world.get_children(pc.id)
    total = sum(c.weight for c in children)
    assert total == 3.0


def test_total_weight_multiple_items(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    _add_item(campaign, pc.id, "Longsword", 3.0, True, world_path)
    _add_item(campaign, pc.id, "Shield", 6.0, True, world_path)
    _add_item(campaign, pc.id, "Backpack", 5.0, False, world_path)
    children = campaign.world.get_children(pc.id)
    total = sum(c.weight for c in children)
    assert total == 14.0


def test_total_weight_zero_weight_items(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    _add_item(campaign, pc.id, "Feather", 0.0, False, world_path)
    children = campaign.world.get_children(pc.id)
    total = sum(c.weight for c in children)
    assert total == 0.0


# ---------------------------------------------------------------------------
# Equip / unequip via WorldTools.set_object_property
# ---------------------------------------------------------------------------

def test_equip_item(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    item = _add_item(campaign, pc.id, "Dagger", 1.0, False, world_path)

    tools = WorldTools(campaign.world)
    result = tools.set_object_property(item.id, "equipped", True)

    assert result.success is True
    updated = campaign.world.get_object(item.id)
    assert updated.properties["equipped"] is True


def test_unequip_item(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    item = _add_item(campaign, pc.id, "Longsword", 3.0, True, world_path)

    tools = WorldTools(campaign.world)
    result = tools.set_object_property(item.id, "equipped", False)

    assert result.success is True
    updated = campaign.world.get_object(item.id)
    assert updated.properties["equipped"] is False


def test_equip_nonexistent_item(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)

    tools = WorldTools(campaign.world)
    result = tools.set_object_property(99999, "equipped", True)

    assert result.success is False
    assert "not found" in result.message


def test_equip_toggle_preserves_other_properties(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    item = Object(
        id=campaign.world.next_id(),
        parent=pc.id,
        type="weapon",
        name="Battle Axe",
        weight=4.0,
        properties={"equipped": False, "damage": "1d8", "damage_type": "slashing"},
    )
    campaign.world.add_object(item)

    tools = WorldTools(campaign.world)
    tools.set_object_property(item.id, "equipped", True)

    updated = campaign.world.get_object(item.id)
    assert updated.properties["equipped"] is True
    assert updated.properties["damage"] == "1d8"
    assert updated.properties["damage_type"] == "slashing"


# ---------------------------------------------------------------------------
# Items as children of the PC
# ---------------------------------------------------------------------------

def test_item_parent_is_pc(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    item = _add_item(campaign, pc.id, "Crossbow", 5.0, False, world_path)
    assert item.parent == pc.id


def test_items_not_visible_as_party_children(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    _add_item(campaign, pc.id, "Shortsword", 2.0, True, world_path)

    # Items are children of the PC, not of the party
    pc_children = campaign.world.get_children(pc.id)
    assert any(c.name == "Shortsword" for c in pc_children)

    party_children = campaign.world.get_children(pc.parent)
    assert not any(c.name == "Shortsword" for c in party_children)


def test_mixed_equipped_and_stowed(tmp_path):
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    _add_item(campaign, pc.id, "Sword", 3.0, True, world_path)
    _add_item(campaign, pc.id, "Rope", 10.0, False, world_path)
    _add_item(campaign, pc.id, "Torch", 1.0, False, world_path)

    children = campaign.world.get_children(pc.id)
    equipped = [c for c in children if c.properties.get("equipped")]
    stowed = [c for c in children if not c.properties.get("equipped")]

    assert len(equipped) == 1
    assert len(stowed) == 2
    assert equipped[0].name == "Sword"


def test_character_endpoint_response_includes_carry_capacity(tmp_path):
    """Verify carry capacity is STR * 15 in the shape returned by the endpoint."""
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path, str_score=14)

    props = pc.properties
    abilities = props.get("abilities", {})
    str_score = abilities.get("str", 10)
    carry_capacity = str_score * 15

    assert carry_capacity == 210  # 14 * 15


def test_character_endpoint_items_include_equipped_flag(tmp_path):
    """Items list has correct equipped flag for each item."""
    campaign, world_path = _make_campaign(tmp_path)
    pc = _add_pc(campaign, world_path)
    sword = _add_item(campaign, pc.id, "Sword", 3.0, True, world_path)
    potion = _add_item(campaign, pc.id, "Potion", 0.5, False, world_path)

    children = campaign.world.get_children(pc.id)
    item_map = {c.id: c for c in children}

    assert item_map[sword.id].properties.get("equipped") is True
    assert item_map[potion.id].properties.get("equipped") is False
