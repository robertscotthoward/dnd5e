"""Player-related constants and helpers for the D&D 5e game engine.

Player data is stored in Object.properties, not separate classes.
This module provides constants and helper functions for player creation.
"""

# Default races with their typical ability modifiers
RACE_MODIFIERS: dict[str, dict[str, int]] = {
    "Human": {"str": 1, "int": 1, "wis": 1, "dex": 1, "con": 1, "chr": 1},
    "Elf": {"dex": 2, "int": 1},
    "Dwarf": {"con": 2, "wis": 1},
    "Halfling": {"dex": 2, "chr": 1},
    "Half-Elf": {"chr": 2, "dex": 1, "wis": 1},
    "Half-Orc": {"str": 2, "con": 1},
    "Dragonborn": {"str": 2, "chr": 1},
    "Gnome": {"int": 2, "con": 1},
    "Tiefling": {"chr": 2, "int": 1},
}

# Default classes with their hit dice
CLASS_HIT_DICE: dict[str, int] = {
    "Barbarian": 12,
    "Fighter": 10,
    "Paladin": 10,
    "Ranger": 10,
    "Bard": 8,
    "Cleric": 8,
    "Druid": 8,
    "Monk": 8,
    "Rogue": 8,
    "Warlock": 8,
    "Sorcerer": 6,
    "Wizard": 6,
}


def get_ability_modifier(score: int) -> int:
    """Calculate ability modifier: (score - 10) // 2."""
    return (score - 10) // 2


def calculate_max_hp(class_type: str, con_modifier: int, level: int = 1) -> int:
    """
    Calculate max HP for a character.

    Level 1: hit die max + CON modifier
    Higher levels: hit die max + (average roll + CON modifier) per additional level
    """
    hit_die = CLASS_HIT_DICE.get(class_type, 8)
    if level == 1:
        return max(1, hit_die + con_modifier)

    # Level 1 gets max, subsequent levels get average + 1
    avg_roll = (hit_die // 2) + 1
    base_hp = hit_die + con_modifier
    additional_hp = (avg_roll + con_modifier) * (level - 1)
    return max(1, base_hp + additional_hp)


def apply_racial_modifiers(abilities: dict[str, int], race: str) -> dict[str, int]:
    """Apply racial modifiers to ability scores."""
    modifiers = RACE_MODIFIERS.get(race, {})
    result = abilities.copy()
    for ability, mod in modifiers.items():
        result[ability] = result.get(ability, 10) + mod
    return result
