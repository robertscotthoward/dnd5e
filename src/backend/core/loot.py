"""Loot generation after combat encounters."""

import random
from typing import Optional

from ..models.world import Object, World
from .tools import WorldTools


# Coin drop ranges by CR tier (approximated): (min_gp, max_gp)
_COIN_TABLE = [
    (0, 5),    # CR 0
    (1, 10),   # CR 1/8
    (2, 15),   # CR 1/4
    (3, 20),   # CR 1/2
    (5, 30),   # CR 1
    (10, 50),  # CR 2-3
    (20, 80),  # CR 4-5
    (50, 150), # CR 6+
]

# Simple item tables by enemy type
_ITEM_TABLES: dict[str, list[tuple[str, float, int, str]]] = {
    # (name, weight, cost_gp, description)
    "goblin": [
        ("Crude Dagger",      1.0,   2,  "A rusty goblin blade."),
        ("Goblin Pouch",      0.5,   5,  "Contains a few silver coins and some lint."),
        ("Shortbow",          2.0,   25, "A small shortbow sized for a goblin."),
    ],
    "orc": [
        ("Greataxe",          7.0,   30, "A heavy orcish greataxe."),
        ("Hide Armor",        12.0,  10, "Crude but functional hide armor."),
        ("War Horn",          1.0,   5,  "An orc war horn carved from bone."),
    ],
    "skeleton": [
        ("Bone Fragment",     0.5,   1,  "A fragment of yellowed bone."),
        ("Rusty Sword",       3.0,   5,  "A corroded longsword."),
        ("Tattered Shield",   6.0,   5,  "A splintered wooden shield."),
    ],
    "zombie": [
        ("Rotted Club",       4.0,   1,  "A mold-covered club."),
        ("Moldy Coin Purse",  0.5,   3,  "Smells terrible but has a few coins."),
    ],
    "default": [
        ("Potion of Healing", 0.5,  50, "Restores 2d4+2 HP when consumed."),
        ("Gold Coins",        0.5,  20, "A small pile of gold coins."),
        ("Silver Coins",      0.5,  5,  "A handful of silver pieces."),
        ("Leather Pouch",     0.3,  2,  "A plain leather pouch."),
    ],
}


def _creature_type(obj: Object) -> str:
    """Extract creature_type from object properties, lowercased."""
    ctype = obj.properties.get("creature_type", obj.type or "default")
    return ctype.lower()


def _cr_tier(obj: Object) -> int:
    """Guess a CR tier (0-7) from the enemy's HP."""
    hp = obj.properties.get("hp", {})
    max_hp = hp.get("max", 0)
    if max_hp <= 6:   return 0
    if max_hp <= 15:  return 1
    if max_hp <= 25:  return 2
    if max_hp <= 40:  return 3
    if max_hp <= 65:  return 4
    if max_hp <= 100: return 5
    if max_hp <= 175: return 6
    return 7


def generate_loot(
    enemies: list[Object],
    world: World,
    loot_container_parent_id: int,
    rng: Optional[random.Random] = None,
) -> dict:
    """
    Generate loot from a list of defeated enemies.

    Creates world objects for each item under `loot_container_parent_id`.
    Returns a loot summary dict with coins and item details.

    Args:
        enemies:                 Defeated enemy objects (HP <= 0).
        world:                   The game world to create loot objects in.
        loot_container_parent_id: Parent object ID where loot items are created.
        rng:                     Optional seeded RNG for deterministic tests.
    """
    if rng is None:
        rng = random.Random()

    tools = WorldTools(world)

    total_cp = 0
    total_sp = 0
    total_gp = 0
    items: list[dict] = []

    for enemy in enemies:
        tier = _cr_tier(enemy)
        min_gp, max_gp = _COIN_TABLE[tier]
        gp_drop = rng.randint(min_gp, max_gp)
        sp_drop = rng.randint(0, max_gp * 2)
        cp_drop = rng.randint(0, max_gp * 5)
        total_gp += gp_drop
        total_sp += sp_drop
        total_cp += cp_drop

        ctype = _creature_type(enemy)
        table = _ITEM_TABLES.get(ctype, _ITEM_TABLES["default"])

        # ~40% chance to drop an item per enemy
        if rng.random() < 0.4:
            item_entry = rng.choice(table)
            name, weight, cost_gp, description = item_entry
            result = tools.create_object(
                type="item",
                parent_id=loot_container_parent_id,
                name=name,
                description=description,
                weight=weight,
                cost=cost_gp * 100,  # convert gp to cp
                is_moveable=True,
                loot=True,
                source_enemy=enemy.name or str(enemy.id),
            )
            if result.success:
                items.append({
                    "id": result.data["id"],
                    "name": name,
                    "weight": weight,
                    "cost_gp": cost_gp,
                    "description": description,
                    "taken_by": None,
                })

    # Create a coin pile object if there's any coin
    total_gp_all = total_gp + total_sp // 10 + total_cp // 100
    if total_gp > 0 or total_sp > 0 or total_cp > 0:
        coin_label_parts = []
        if total_gp > 0:
            coin_label_parts.append(f"{total_gp} gp")
        if total_sp > 0:
            coin_label_parts.append(f"{total_sp} sp")
        if total_cp > 0:
            coin_label_parts.append(f"{total_cp} cp")
        coin_label = ", ".join(coin_label_parts)
        coin_weight = round((total_gp + total_sp + total_cp) / 50.0, 2)
        result = tools.create_object(
            type="coins",
            parent_id=loot_container_parent_id,
            name=f"Coins ({coin_label})",
            description=f"Currency looted from the battle: {coin_label}.",
            weight=coin_weight,
            cost=total_gp * 100 + total_sp * 10 + total_cp,
            is_moveable=True,
            loot=True,
            coins={"gp": total_gp, "sp": total_sp, "cp": total_cp},
        )
        if result.success:
            items.insert(0, {
                "id": result.data["id"],
                "name": f"Coins ({coin_label})",
                "weight": coin_weight,
                "cost_gp": total_gp_all,
                "description": f"Currency: {coin_label}.",
                "coins": {"gp": total_gp, "sp": total_sp, "cp": total_cp},
                "taken_by": None,
            })

    return {
        "enemies_defeated": [e.name or str(e.id) for e in enemies],
        "coins": {"gp": total_gp, "sp": total_sp, "cp": total_cp},
        "items": items,
        "loot_container_id": loot_container_parent_id,
    }
