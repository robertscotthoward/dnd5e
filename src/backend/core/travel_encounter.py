"""Travel encounter engine: d20 roll against location-appropriate encounter tables."""

import random
from typing import Optional

# Encounter tables keyed by location type (lower-case).
# Each entry: (min_cr, max_cr, enemy_type, name, count_dice)
# count_dice: "1" | "1d4" | "1d6" | etc.
ENCOUNTER_TABLES: dict[str, list[dict]] = {
    "forest": [
        {"cr": "1/4", "type": "NPC", "name": "Wolf", "count": "1d4"},
        {"cr": "1/4", "type": "NPC", "name": "Goblin", "count": "1d6"},
        {"cr": "1/2", "type": "NPC", "name": "Hobgoblin", "count": "1d4"},
        {"cr": "1", "type": "NPC", "name": "Owlbear", "count": "1"},
        {"cr": "2", "type": "NPC", "name": "Bandit Captain", "count": "1"},
        {"cr": "1/4", "type": "NPC", "name": "Bandit", "count": "2d4"},
    ],
    "dungeon": [
        {"cr": "1/4", "type": "NPC", "name": "Skeleton", "count": "1d6"},
        {"cr": "1/4", "type": "NPC", "name": "Zombie", "count": "1d4"},
        {"cr": "1/2", "type": "NPC", "name": "Shadow", "count": "1d4"},
        {"cr": "1", "type": "NPC", "name": "Ghoul", "count": "1d4"},
        {"cr": "2", "type": "NPC", "name": "Wight", "count": "1"},
        {"cr": "1/4", "type": "NPC", "name": "Giant Rat", "count": "2d6"},
    ],
    "road": [
        {"cr": "1/4", "type": "NPC", "name": "Bandit", "count": "2d4"},
        {"cr": "1/2", "type": "NPC", "name": "Thug", "count": "1d4"},
        {"cr": "2", "type": "NPC", "name": "Bandit Captain", "count": "1"},
        {"cr": "1/4", "type": "NPC", "name": "Cultist", "count": "1d6"},
        {"cr": "1/2", "type": "NPC", "name": "Orc", "count": "1d4"},
        {"cr": "1/4", "type": "NPC", "name": "Goblin", "count": "2d4"},
    ],
    "mountain": [
        {"cr": "1/2", "type": "NPC", "name": "Orc", "count": "1d6"},
        {"cr": "1/4", "type": "NPC", "name": "Kobold", "count": "2d6"},
        {"cr": "1", "type": "NPC", "name": "Harpy", "count": "1d4"},
        {"cr": "2", "type": "NPC", "name": "Ogre", "count": "1"},
        {"cr": "1", "type": "NPC", "name": "Giant Eagle", "count": "1d4"},
        {"cr": "1/4", "type": "NPC", "name": "Mountain Goat", "count": "1d6"},
    ],
    "swamp": [
        {"cr": "1/4", "type": "NPC", "name": "Lizardfolk", "count": "1d4"},
        {"cr": "1/2", "type": "NPC", "name": "Crocodile", "count": "1d4"},
        {"cr": "1", "type": "NPC", "name": "Will-o'-Wisp", "count": "1d4"},
        {"cr": "2", "type": "NPC", "name": "Merrow", "count": "1d4"},
        {"cr": "1/4", "type": "NPC", "name": "Giant Frog", "count": "1d6"},
        {"cr": "1/2", "type": "NPC", "name": "Black Bear", "count": "1"},
    ],
    "plains": [
        {"cr": "1/4", "type": "NPC", "name": "Gnoll", "count": "1d6"},
        {"cr": "1/4", "type": "NPC", "name": "Hobgoblin", "count": "1d4"},
        {"cr": "1", "type": "NPC", "name": "Lion", "count": "1d4"},
        {"cr": "2", "type": "NPC", "name": "Griffon", "count": "1"},
        {"cr": "1/2", "type": "NPC", "name": "Orc", "count": "1d4"},
        {"cr": "1/4", "type": "NPC", "name": "Hyena", "count": "2d6"},
    ],
    "desert": [
        {"cr": "1/4", "type": "NPC", "name": "Gnoll", "count": "1d4"},
        {"cr": "1/2", "type": "NPC", "name": "Jackalwere", "count": "1d4"},
        {"cr": "1", "type": "NPC", "name": "Giant Scorpion", "count": "1"},
        {"cr": "2", "type": "NPC", "name": "Yuan-ti Pureblood", "count": "1d4"},
        {"cr": "1/4", "type": "NPC", "name": "Dust Mephit", "count": "1d6"},
        {"cr": "1/2", "type": "NPC", "name": "Wight", "count": "1"},
    ],
    "urban": [
        {"cr": "1/4", "type": "NPC", "name": "Thug", "count": "1d4"},
        {"cr": "1/2", "type": "NPC", "name": "Spy", "count": "1"},
        {"cr": "2", "type": "NPC", "name": "Bandit Captain", "count": "1"},
        {"cr": "1/4", "type": "NPC", "name": "Cultist", "count": "1d6"},
        {"cr": "1", "type": "NPC", "name": "Assassin", "count": "1"},
        {"cr": "1/4", "type": "NPC", "name": "Bandit", "count": "2d4"},
    ],
    "default": [
        {"cr": "1/4", "type": "NPC", "name": "Goblin", "count": "1d4"},
        {"cr": "1/4", "type": "NPC", "name": "Bandit", "count": "1d4"},
        {"cr": "1/2", "type": "NPC", "name": "Orc", "count": "1"},
        {"cr": "1", "type": "NPC", "name": "Ogre", "count": "1"},
    ],
}

# Encounter chance: roll d20 vs this DC to trigger an encounter
ENCOUNTER_DC = 15


def _resolve_count(notation: str, rng: random.Random) -> int:
    """Resolve a simple count notation like '1', '1d4', '2d6'."""
    notation = notation.strip()
    if "d" in notation:
        parts = notation.split("d")
        times = int(parts[0]) if parts[0] else 1
        sides = int(parts[1])
        return sum(rng.randint(1, sides) for _ in range(times))
    return int(notation)


def get_encounter_table(location_type: str) -> list[dict]:
    """Return the encounter table for a given location type, falling back to default."""
    key = location_type.lower().strip() if location_type else "default"
    # Try exact match first, then partial match
    if key in ENCOUNTER_TABLES:
        return ENCOUNTER_TABLES[key]
    for table_key in ENCOUNTER_TABLES:
        if table_key in key or key in table_key:
            return ENCOUNTER_TABLES[table_key]
    return ENCOUNTER_TABLES["default"]


class TravelEncounterEngine:
    """
    Manages random encounter checks during Travel mode.

    Rolls a hidden d20 against ENCOUNTER_DC.  On a hit, selects a
    location-appropriate encounter from the corpus-derived table,
    rolls enemy count, and returns enough data for the DM agent to
    spawn enemies and switch to Combat mode.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def roll_encounter(
        self,
        location_type: str = "default",
        party_level: int = 1,
    ) -> dict:
        """
        Roll a d20 encounter check for a travel segment.

        Args:
            location_type: Type of terrain being traversed (forest, dungeon, road, etc.)
            party_level: Average party level used for difficulty scaling (future use)

        Returns:
            dict with keys:
              d20_roll      — the raw d20 result
              encounter_dc  — the DC that had to be met
              triggered     — True if an encounter was triggered
              location_type — the location type used for lookup
              encounter     — dict describing the encounter (None if not triggered)
        """
        d20_roll = self.rng.randint(1, 20)
        triggered = d20_roll >= ENCOUNTER_DC

        result: dict = {
            "d20_roll": d20_roll,
            "encounter_dc": ENCOUNTER_DC,
            "triggered": triggered,
            "location_type": location_type,
            "encounter": None,
        }

        if triggered:
            table = get_encounter_table(location_type)
            entry = self.rng.choice(table)
            count = _resolve_count(entry["count"], self.rng)
            result["encounter"] = {
                "enemy_type": entry["type"],
                "enemy_name": entry["name"],
                "cr": entry["cr"],
                "count": count,
                "spawn_instructions": (
                    f"Spawn {count}x {entry['name']} (CR {entry['cr']}) as NPC objects "
                    f"in the current location and start combat."
                ),
            }

        return result
