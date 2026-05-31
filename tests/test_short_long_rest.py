"""Tests for short rest and long rest tools."""

import pytest
from pathlib import Path

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.core.tools import WorldTools
from src.backend.models.player import build_initial_spell_slots, CLASS_HIT_DICE
from src.backend.models.world import Object


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world(tmp_path: Path):
    campaign = new_campaign_object("RestTest", seed=42)
    world_path = tmp_path / "RestTest" / "world.yaml"
    world_path.parent.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, world_path)
    return campaign.world


def _add_pc(world, class_type: str, level: int = 3, hp_current: int = 10, hp_max: int = 30) -> Object:
    parties = world.get_parties()
    party_id = parties[0].id if parties else 1
    spell_slots = build_initial_spell_slots(class_type, level)
    abilities = {"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 10, "chr": 10}
    pc = Object(
        id=world.next_id(),
        parent=party_id,
        type="PC",
        name=f"Test{class_type}",
        properties={
            "classes": [{"type": class_type, "level": level}],
            "hp": {"current": hp_current, "max": hp_max},
            "abilities": abilities,
            "spell_slots": spell_slots if spell_slots else None,
        },
    )
    world.add_object(pc)
    return pc


# ---------------------------------------------------------------------------
# short_rest
# ---------------------------------------------------------------------------

def test_short_rest_recovers_hp(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Fighter", hp_current=5, hp_max=30)
    tools = WorldTools(world)
    result = tools.short_rest(pc.id, num_hit_dice=1)
    assert result.success
    new_hp = pc.properties["hp"]["current"]
    assert new_hp > 5, "HP should increase after short rest"


def test_short_rest_does_not_exceed_max_hp(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Fighter", hp_current=29, hp_max=30)
    tools = WorldTools(world)
    result = tools.short_rest(pc.id, num_hit_dice=1)
    assert result.success
    assert pc.properties["hp"]["current"] <= pc.properties["hp"]["max"]


def test_short_rest_at_full_hp_stays_full(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Fighter", hp_current=30, hp_max=30)
    tools = WorldTools(world)
    result = tools.short_rest(pc.id, num_hit_dice=1)
    assert result.success
    assert pc.properties["hp"]["current"] == 30


def test_short_rest_caps_dice_at_level(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Fighter", level=2, hp_current=1, hp_max=40)
    tools = WorldTools(world)
    # Request more dice than the character's level
    result = tools.short_rest(pc.id, num_hit_dice=10)
    assert result.success
    assert len(result.data["rolls"]) == 2  # capped at level 2


def test_short_rest_uses_correct_hit_die(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Barbarian", hp_current=1, hp_max=60)
    tools = WorldTools(world)
    result = tools.short_rest(pc.id)
    assert result.success
    assert result.data["hit_die"] == CLASS_HIT_DICE["Barbarian"]  # d12


def test_short_rest_nonexistent_object_fails(tmp_path):
    world = _make_world(tmp_path)
    tools = WorldTools(world)
    result = tools.short_rest(99999)
    assert not result.success


def test_short_rest_includes_con_modifier(tmp_path):
    world = _make_world(tmp_path)
    # CON 14 = +2 modifier
    pc = _add_pc(world, "Fighter", hp_current=1, hp_max=60)
    tools = WorldTools(world)
    result = tools.short_rest(pc.id)
    assert result.success
    assert result.data["con_modifier"] == 2


def test_short_rest_warlock_recovers_spell_slots(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Warlock", level=3, hp_current=10, hp_max=24)
    # Exhaust all Warlock slots
    slots = pc.properties["spell_slots"]
    for slot in slots.values():
        slot["used"] = slot["max"]
    tools = WorldTools(world)
    result = tools.short_rest(pc.id)
    assert result.success
    # All Warlock slots should be restored
    for slot in pc.properties["spell_slots"].values():
        assert slot["used"] == 0


def test_short_rest_fighter_does_not_restore_slots(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Fighter", level=3, hp_current=10, hp_max=30)
    # Fighter has no spell slots — result.data["spell_slots"] should be None
    tools = WorldTools(world)
    result = tools.short_rest(pc.id)
    assert result.success
    assert result.data.get("spell_slots") is None


# ---------------------------------------------------------------------------
# long_rest
# ---------------------------------------------------------------------------

def test_long_rest_restores_full_hp(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Fighter", hp_current=1, hp_max=30)
    tools = WorldTools(world)
    result = tools.long_rest(pc.id)
    assert result.success
    assert pc.properties["hp"]["current"] == 30


def test_long_rest_restores_spell_slots(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Wizard", level=5, hp_current=5, hp_max=28)
    # Exhaust slots
    for slot in pc.properties["spell_slots"].values():
        slot["used"] = slot["max"]
    tools = WorldTools(world)
    result = tools.long_rest(pc.id)
    assert result.success
    for slot in pc.properties["spell_slots"].values():
        assert slot["used"] == 0


def test_long_rest_at_full_hp_still_succeeds(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Cleric", level=3, hp_current=24, hp_max=24)
    tools = WorldTools(world)
    result = tools.long_rest(pc.id)
    assert result.success
    assert pc.properties["hp"]["current"] == 24


def test_long_rest_nonexistent_object_fails(tmp_path):
    world = _make_world(tmp_path)
    tools = WorldTools(world)
    result = tools.long_rest(99999)
    assert not result.success


def test_long_rest_fighter_no_slots_succeeds(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Fighter", hp_current=5, hp_max=30)
    tools = WorldTools(world)
    result = tools.long_rest(pc.id)
    assert result.success
    assert pc.properties["hp"]["current"] == 30


def test_long_rest_returns_hp_data(tmp_path):
    world = _make_world(tmp_path)
    pc = _add_pc(world, "Ranger", level=4, hp_current=10, hp_max=36)
    tools = WorldTools(world)
    result = tools.long_rest(pc.id)
    assert result.success
    assert result.data["hp"]["current"] == 36
    assert result.data["hp"]["max"] == 36
