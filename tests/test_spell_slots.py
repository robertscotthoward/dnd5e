"""Tests for spell slot tracker: data helpers, cast_spell, and long_rest tools."""

import pytest
from pathlib import Path

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.core.tools import WorldTools
from src.backend.models.player import (
    build_initial_spell_slots,
    get_spell_slots_for_class,
    CASTER_CLASSES,
)
from src.backend.models.world import Object, Location


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world(tmp_path: Path):
    campaign = new_campaign_object("SlotTest", seed=99)
    world_path = tmp_path / "SlotTest" / "world.yaml"
    world_path.parent.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, world_path)
    return campaign.world, world_path


def _add_caster(world, class_type: str, level: int = 1) -> Object:
    parties = world.get_parties()
    party_id = parties[0].id if parties else 1
    spell_slots = build_initial_spell_slots(class_type, level)
    pc = Object(
        id=world.next_id(),
        parent=party_id,
        type="PC",
        name=f"Test{class_type}",
        properties={
            "classes": [{"type": class_type, "level": level}],
            "hp": {"current": 20, "max": 20},
            "spell_slots": spell_slots,
        },
    )
    world.add_object(pc)
    return pc


# ---------------------------------------------------------------------------
# build_initial_spell_slots
# ---------------------------------------------------------------------------

def test_wizard_level1_has_two_first_level_slots():
    slots = build_initial_spell_slots("Wizard", 1)
    assert slots["1"]["max"] == 2
    assert slots["1"]["used"] == 0


def test_wizard_level5_has_correct_slots():
    slots = build_initial_spell_slots("Wizard", 5)
    assert slots["1"]["max"] == 4
    assert slots["2"]["max"] == 3
    assert slots["3"]["max"] == 2
    assert "4" not in slots


def test_wizard_level9_has_five_levels():
    slots = build_initial_spell_slots("Wizard", 9)
    assert "5" in slots
    assert slots["5"]["max"] == 1


def test_fighter_non_caster_returns_empty():
    slots = build_initial_spell_slots("Fighter", 5)
    assert slots == {}


def test_barbarian_non_caster_returns_empty():
    slots = build_initial_spell_slots("Barbarian", 10)
    assert slots == {}


def test_paladin_half_caster_no_slots_at_level1():
    slots = build_initial_spell_slots("Paladin", 1)
    assert slots == {}


def test_paladin_half_caster_slots_at_level2():
    slots = build_initial_spell_slots("Paladin", 2)
    assert slots["1"]["max"] == 2


def test_paladin_level5_has_two_slot_levels():
    slots = build_initial_spell_slots("Paladin", 5)
    assert "1" in slots
    assert "2" in slots
    assert "3" not in slots


def test_warlock_pact_magic_level1():
    slots = build_initial_spell_slots("Warlock", 1)
    assert slots["1"]["max"] == 1


def test_warlock_pact_magic_level5():
    slots = build_initial_spell_slots("Warlock", 5)
    assert "3" in slots
    # Warlock at level 5 gets 2 slots at level 3
    assert slots["3"]["max"] == 2
    assert "1" not in slots


def test_cleric_level3_has_first_and_second_slots():
    slots = build_initial_spell_slots("Cleric", 3)
    assert slots["1"]["max"] == 4
    assert slots["2"]["max"] == 2


def test_sorcerer_level17_has_ninth_level():
    slots = build_initial_spell_slots("Sorcerer", 17)
    assert "9" in slots


# ---------------------------------------------------------------------------
# cast_spell tool
# ---------------------------------------------------------------------------

def test_cast_spell_decrements_slot(tmp_path):
    world, _ = _make_world(tmp_path)
    pc = _add_caster(world, "Wizard", 3)
    tools = WorldTools(world)

    result = tools.cast_spell(pc.id, 1)

    assert result.success
    assert result.data["remaining"] == 3  # 4 - 1 = 3 at level 3


def test_cast_spell_exact_remaining(tmp_path):
    world, _ = _make_world(tmp_path)
    pc = _add_caster(world, "Wizard", 1)
    tools = WorldTools(world)

    # Level 1 wizard has 2 first-level slots
    tools.cast_spell(pc.id, 1)
    result = tools.cast_spell(pc.id, 1)

    assert result.success
    assert result.data["remaining"] == 0


def test_cast_spell_fails_when_no_slots_left(tmp_path):
    world, _ = _make_world(tmp_path)
    pc = _add_caster(world, "Wizard", 1)
    tools = WorldTools(world)

    tools.cast_spell(pc.id, 1)
    tools.cast_spell(pc.id, 1)
    result = tools.cast_spell(pc.id, 1)

    assert not result.success


def test_cast_spell_fails_for_missing_slot_level(tmp_path):
    world, _ = _make_world(tmp_path)
    pc = _add_caster(world, "Wizard", 1)
    tools = WorldTools(world)

    # Level 1 wizard has no 5th-level slots
    result = tools.cast_spell(pc.id, 5)
    assert not result.success


def test_cast_spell_fails_for_non_caster(tmp_path):
    world, _ = _make_world(tmp_path)
    parties = world.get_parties()
    party_id = parties[0].id if parties else 1
    fighter = Object(
        id=world.next_id(),
        parent=party_id,
        type="PC",
        name="Bob",
        properties={"hp": {"current": 10, "max": 10}},
    )
    world.add_object(fighter)
    tools = WorldTools(world)

    result = tools.cast_spell(fighter.id, 1)
    assert not result.success


def test_cast_spell_fails_for_missing_object(tmp_path):
    world, _ = _make_world(tmp_path)
    tools = WorldTools(world)
    result = tools.cast_spell(9999, 1)
    assert not result.success


# ---------------------------------------------------------------------------
# long_rest tool
# ---------------------------------------------------------------------------

def test_long_rest_restores_all_slots(tmp_path):
    world, _ = _make_world(tmp_path)
    pc = _add_caster(world, "Wizard", 3)
    tools = WorldTools(world)

    tools.cast_spell(pc.id, 1)
    tools.cast_spell(pc.id, 2)
    result = tools.long_rest(pc.id)

    assert result.success
    slots = result.data["spell_slots"]
    for slot_data in slots.values():
        assert slot_data["used"] == 0


def test_long_rest_restores_hp(tmp_path):
    world, _ = _make_world(tmp_path)
    pc = _add_caster(world, "Wizard", 1)
    pc.properties["hp"]["current"] = 5
    tools = WorldTools(world)

    result = tools.long_rest(pc.id)

    assert result.success
    assert result.data["hp"]["current"] == 20


def test_long_rest_on_non_caster_still_restores_hp(tmp_path):
    world, _ = _make_world(tmp_path)
    parties = world.get_parties()
    party_id = parties[0].id if parties else 1
    fighter = Object(
        id=world.next_id(),
        parent=party_id,
        type="PC",
        name="Grog",
        properties={"hp": {"current": 3, "max": 30}},
    )
    world.add_object(fighter)
    tools = WorldTools(world)

    result = tools.long_rest(fighter.id)

    assert result.success
    assert result.data["hp"]["current"] == 30


def test_long_rest_fails_for_missing_object(tmp_path):
    world, _ = _make_world(tmp_path)
    tools = WorldTools(world)
    result = tools.long_rest(9999)
    assert not result.success


def test_long_rest_resets_used_counter_to_zero(tmp_path):
    world, _ = _make_world(tmp_path)
    pc = _add_caster(world, "Cleric", 5)
    tools = WorldTools(world)

    # Expend all level-1 slots
    for _ in range(4):
        tools.cast_spell(pc.id, 1)

    tools.long_rest(pc.id)
    obj = world.get_object(pc.id)
    assert obj.properties["spell_slots"]["1"]["used"] == 0
