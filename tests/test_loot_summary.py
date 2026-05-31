"""Tests for loot generation after combat."""

import random
from pathlib import Path

import pytest

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.core.loot import generate_loot
from src.backend.models.world import Object, World


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world() -> World:
    campaign = new_campaign_object("LootTest", seed=42)
    return campaign.world


def _add_enemy(world: World, hp: int = 10, creature_type: str = "goblin") -> Object:
    parties = world.get_parties()
    parent_id = parties[0].id if parties else 1
    eid = world.next_id()
    enemy = Object(
        id=eid,
        parent=parent_id,
        type="NPC",
        name=f"{creature_type.capitalize()}_{eid}",
        properties={
            "creature_type": creature_type,
            "hp": {"current": 0, "max": hp},  # already dead
        },
    )
    world.add_object(enemy)
    return enemy


def _find_loot_parent(world: World) -> int:
    parties = world.get_parties()
    return parties[0].id if parties else 1


# ---------------------------------------------------------------------------
# generate_loot tests
# ---------------------------------------------------------------------------

def test_loot_returns_dict_structure():
    world = _make_world()
    enemy = _add_enemy(world, hp=10)
    parent_id = _find_loot_parent(world)
    rng = random.Random(1)

    result = generate_loot([enemy], world, parent_id, rng=rng)

    assert "enemies_defeated" in result
    assert "coins" in result
    assert "items" in result
    assert "loot_container_id" in result
    assert result["loot_container_id"] == parent_id


def test_loot_defeated_enemy_names():
    world = _make_world()
    e1 = _add_enemy(world, creature_type="goblin")
    e2 = _add_enemy(world, creature_type="orc")
    parent_id = _find_loot_parent(world)

    result = generate_loot([e1, e2], world, parent_id, rng=random.Random(2))

    assert e1.name in result["enemies_defeated"]
    assert e2.name in result["enemies_defeated"]


def test_coins_always_generated():
    world = _make_world()
    enemy = _add_enemy(world, hp=30)
    parent_id = _find_loot_parent(world)
    rng = random.Random(10)

    result = generate_loot([enemy], world, parent_id, rng=rng)

    coins = result["coins"]
    assert isinstance(coins["gp"], int)
    assert isinstance(coins["sp"], int)
    assert isinstance(coins["cp"], int)
    assert coins["gp"] >= 0 and coins["sp"] >= 0 and coins["cp"] >= 0


def test_items_created_in_world():
    """Items in the loot summary must exist as world objects."""
    world = _make_world()
    enemy = _add_enemy(world, hp=20)
    parent_id = _find_loot_parent(world)
    # Force an item drop by giving many enemies
    enemies = [_add_enemy(world, hp=10) for _ in range(10)]
    rng = random.Random(99)

    result = generate_loot(enemies, world, parent_id, rng=rng)

    for item in result["items"]:
        obj = world.get_object(item["id"])
        assert obj is not None, f"Item {item['id']} ({item['name']}) not found in world"


def test_coin_pile_object_created():
    """A coins object should exist in the world when coins are dropped."""
    world = _make_world()
    enemies = [_add_enemy(world, hp=10) for _ in range(5)]
    parent_id = _find_loot_parent(world)
    rng = random.Random(7)

    result = generate_loot(enemies, world, parent_id, rng=rng)

    coin_items = [i for i in result["items"] if "Coins" in i["name"]]
    if result["coins"]["gp"] > 0 or result["coins"]["sp"] > 0 or result["coins"]["cp"] > 0:
        assert len(coin_items) >= 1


def test_item_dict_has_required_fields():
    world = _make_world()
    enemies = [_add_enemy(world, hp=10) for _ in range(10)]
    parent_id = _find_loot_parent(world)
    rng = random.Random(42)

    result = generate_loot(enemies, world, parent_id, rng=rng)

    for item in result["items"]:
        assert "id" in item
        assert "name" in item
        assert "weight" in item
        assert "cost_gp" in item
        assert "description" in item
        assert "taken_by" in item
        assert item["taken_by"] is None  # not yet taken


def test_no_enemies_returns_empty_loot():
    world = _make_world()
    parent_id = _find_loot_parent(world)

    result = generate_loot([], world, parent_id, rng=random.Random(1))

    assert result["enemies_defeated"] == []
    # No coins
    assert result["coins"]["gp"] == 0
    assert result["coins"]["sp"] == 0
    assert result["coins"]["cp"] == 0
    assert result["items"] == []


def test_high_hp_enemy_drops_more_coin():
    """A high-HP enemy should drop more gold on average than a low-HP one."""
    world_low = _make_world()
    world_high = _make_world()

    rng = random.Random(5)
    low_enemies = [_add_enemy(world_low, hp=5) for _ in range(5)]
    result_low = generate_loot(low_enemies, world_low, _find_loot_parent(world_low), rng=rng)

    rng = random.Random(5)
    high_enemies = [_add_enemy(world_high, hp=200) for _ in range(5)]
    result_high = generate_loot(high_enemies, world_high, _find_loot_parent(world_high), rng=rng)

    total_low = result_low["coins"]["gp"] * 100 + result_low["coins"]["sp"] * 10 + result_low["coins"]["cp"]
    total_high = result_high["coins"]["gp"] * 100 + result_high["coins"]["sp"] * 10 + result_high["coins"]["cp"]
    assert total_high > total_low


def test_creature_type_influences_items():
    """Different creature types have different item pools."""
    world = _make_world()
    goblin = _add_enemy(world, creature_type="goblin")
    orc = _add_enemy(world, creature_type="orc")
    parent_id = _find_loot_parent(world)

    # Run many times to see at least one item from each table
    goblin_names = {"Crude Dagger", "Goblin Pouch", "Shortbow"}
    orc_names = {"Greataxe", "Hide Armor", "War Horn"}

    goblin_found = set()
    orc_found = set()
    for seed in range(200):
        w2 = _make_world()
        g = _add_enemy(w2, creature_type="goblin")
        o = _add_enemy(w2, creature_type="orc")
        pid = _find_loot_parent(w2)
        rng = random.Random(seed)
        res_g = generate_loot([g], w2, pid, rng=rng)
        goblin_found |= {i["name"] for i in res_g["items"]}
        rng = random.Random(seed)
        res_o = generate_loot([o], w2, pid, rng=rng)
        orc_found |= {i["name"] for i in res_o["items"]}

    # At least one goblin-specific item should appear across 200 seeds
    assert goblin_found & goblin_names, f"No goblin items found in {goblin_found}"
    assert orc_found & orc_names, f"No orc items found in {orc_found}"


def test_deterministic_with_seed():
    """Same RNG seed produces identical loot."""
    world1 = _make_world()
    world2 = _make_world()

    enemies1 = [_add_enemy(world1, hp=15) for _ in range(3)]
    enemies2 = [_add_enemy(world2, hp=15) for _ in range(3)]
    parent1 = _find_loot_parent(world1)
    parent2 = _find_loot_parent(world2)

    res1 = generate_loot(enemies1, world1, parent1, rng=random.Random(77))
    res2 = generate_loot(enemies2, world2, parent2, rng=random.Random(77))

    assert res1["coins"] == res2["coins"]
    assert len(res1["items"]) == len(res2["items"])
    for i1, i2 in zip(res1["items"], res2["items"]):
        assert i1["name"] == i2["name"]
        assert i1["weight"] == i2["weight"]
        assert i1["cost_gp"] == i2["cost_gp"]
