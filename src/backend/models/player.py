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


# Caster classes — any class not in this set is a non-caster
CASTER_CLASSES = {
    "Bard", "Cleric", "Druid", "Paladin", "Ranger",
    "Sorcerer", "Warlock", "Wizard",
}

# D&D 5e spell slots per level for full casters (Bard, Cleric, Druid, Sorcerer, Wizard)
# Index: level 1-20; value: dict of {slot_level: count}
FULL_CASTER_SLOTS: list[dict[int, int]] = [
    {},                                                           # level 0 placeholder
    {1: 2},                                                       # 1
    {1: 3},                                                       # 2
    {1: 4, 2: 2},                                                 # 3
    {1: 4, 2: 3},                                                 # 4
    {1: 4, 2: 3, 3: 2},                                          # 5
    {1: 4, 2: 3, 3: 3},                                          # 6
    {1: 4, 2: 3, 3: 3, 4: 1},                                    # 7
    {1: 4, 2: 3, 3: 3, 4: 2},                                    # 8
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},                             # 9
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},                             # 10
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},                      # 11
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},                      # 12
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},                # 13
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},                # 14
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},         # 15
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},         # 16
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},  # 17
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},  # 18
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},  # 19
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},  # 20
]

# Half-casters (Paladin, Ranger): spell slots start at level 2, advance at half rate
HALF_CASTER_SLOTS: list[dict[int, int]] = [
    {},       # 0
    {},       # 1 — no slots
    {1: 2},   # 2
    {1: 3},   # 3
    {1: 3},   # 4
    {1: 4, 2: 2},  # 5
    {1: 4, 2: 2},  # 6
    {1: 4, 2: 3},  # 7
    {1: 4, 2: 3},  # 8
    {1: 4, 2: 3, 3: 2},  # 9
    {1: 4, 2: 3, 3: 2},  # 10
    {1: 4, 2: 3, 3: 3},  # 11
    {1: 4, 2: 3, 3: 3},  # 12
    {1: 4, 2: 3, 3: 3, 4: 1},  # 13
    {1: 4, 2: 3, 3: 3, 4: 1},  # 14
    {1: 4, 2: 3, 3: 3, 4: 2},  # 15
    {1: 4, 2: 3, 3: 3, 4: 2},  # 16
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},  # 17
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},  # 18
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},  # 19
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},  # 20
]

# Warlock pact magic: separate short-rest slots, all same level
WARLOCK_SLOTS: list[dict[int, int]] = [
    {},          # 0
    {1: 1},      # 1
    {1: 2},      # 2
    {2: 2},      # 3
    {2: 2},      # 4
    {3: 2},      # 5
    {3: 2},      # 6
    {4: 2},      # 7
    {4: 2},      # 8
    {5: 2},      # 9
    {5: 2},      # 10
    {5: 3},      # 11
    {5: 3},      # 12
    {5: 3},      # 13
    {5: 3},      # 14
    {5: 3},      # 15
    {5: 3},      # 16
    {5: 4},      # 17
    {5: 4},      # 18
    {5: 4},      # 19
    {5: 4},      # 20
]

HALF_CASTER_SET = {"Paladin", "Ranger"}
WARLOCK_SET = {"Warlock"}


def get_spell_slots_for_class(class_type: str, level: int) -> dict[int, int]:
    """Return the max spell slots dict {slot_level: count} for a class at a given level."""
    safe_level = max(0, min(level, 20))
    if class_type in WARLOCK_SET:
        return WARLOCK_SLOTS[safe_level].copy()
    if class_type in HALF_CASTER_SET:
        return HALF_CASTER_SLOTS[safe_level].copy()
    if class_type in CASTER_CLASSES:
        return FULL_CASTER_SLOTS[safe_level].copy()
    return {}


def build_initial_spell_slots(class_type: str, level: int) -> dict[str, dict[str, int]]:
    """
    Build the initial spell_slots property for a character.

    Returns a dict keyed by str(slot_level):
      {"1": {"max": 2, "used": 0}, "2": {"max": 3, "used": 0}, ...}
    """
    max_slots = get_spell_slots_for_class(class_type, level)
    return {
        str(slot_level): {"max": count, "used": 0}
        for slot_level, count in max_slots.items()
    }


def apply_racial_modifiers(abilities: dict[str, int], race: str) -> dict[str, int]:
    """Apply racial modifiers to ability scores."""
    modifiers = RACE_MODIFIERS.get(race, {})
    result = abilities.copy()
    for ability, mod in modifiers.items():
        result[ability] = result.get(ability, 10) + mod
    return result
