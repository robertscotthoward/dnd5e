"""Player models for the D&D 5e game engine."""

from typing import Optional
from pydantic import BaseModel, Field


class AbilityScores(BaseModel):
    """The six ability scores for a D&D character."""

    str_: int = Field(10, alias="str")  # Strength
    int_: int = Field(10, alias="int")  # Intelligence
    wis: int = 10  # Wisdom
    dex: int = 10  # Dexterity
    con: int = 10  # Constitution
    chr: int = 10  # Charisma

    class Config:
        populate_by_name = True

    def get_modifier(self, ability: str) -> int:
        """Calculate ability modifier: (score - 10) // 2."""
        score = getattr(self, ability if ability not in ("str", "int") else f"{ability}_")
        return (score - 10) // 2


class ClassLevel(BaseModel):
    """A character's class and level in that class."""

    type: str  # e.g. "Ranger", "Fighter", "Wizard"
    level: int = 1


class HealthPool(BaseModel):
    """A pool of points (HP, mana, etc.) with max and current values."""

    max: int
    current: int

    def modify(self, delta: int) -> int:
        """Modify current value, clamping to [0, max]. Returns new value."""
        self.current = max(0, min(self.max, self.current + delta))
        return self.current

    @property
    def is_depleted(self) -> bool:
        return self.current <= 0


class Player(BaseModel):
    """
    Base player model for both PCs and NPCs.

    Players are Objects in the world with additional game statistics.
    The object_id links this player data to their Object in the world.
    """

    object_id: int  # Links to the Object in the world
    name: str
    race: str  # e.g. "Human", "Elf", "Dwarf"
    classes: list[ClassLevel] = Field(default_factory=list)
    abilities: AbilityScores = Field(default_factory=AbilityScores)
    hp: HealthPool
    mana: Optional[HealthPool] = None
    health: Optional[HealthPool] = None  # Separate from HP for some systems
    personality: Optional[str] = None  # For AI decision making
    disposition: Optional[str] = None  # e.g. "friendly", "hostile", "neutral"

    @property
    def total_level(self) -> int:
        """Sum of all class levels."""
        return sum(c.level for c in self.classes)

    @property
    def is_dead(self) -> bool:
        return self.hp.is_depleted

    def add_class(self, class_type: str, level: int = 1) -> None:
        """Add a new class or increase level in existing class."""
        for c in self.classes:
            if c.type.lower() == class_type.lower():
                c.level += level
                return
        self.classes.append(ClassLevel(type=class_type, level=level))


class PC(Player):
    """
    Player Character - controlled by AI agent representing a player.

    PCs have additional tracking for experience and backstory.
    """

    experience: int = 0
    backstory: Optional[str] = None
    goals: list[str] = Field(default_factory=list)


class NPC(Player):
    """
    Non-Player Character - monsters, townfolk, etc.

    NPCs have additional tracking for AI behavior.
    """

    is_hostile: bool = False
    patrol_route: list[int] = Field(default_factory=list)  # Object IDs to patrol between
    dialogue: dict[str, str] = Field(default_factory=dict)  # Trigger -> response mapping
    loot_table: list[dict] = Field(default_factory=list)  # Items dropped on death


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
