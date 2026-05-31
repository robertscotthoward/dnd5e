"""Campaign I/O utilities - shared between CLI and API."""

import random
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from src.backend.models.world import World, Object, Location, Size
from src.backend.models.game import Campaign
from src.backend.models.player import CLASS_HIT_DICE, RACE_MODIFIERS, get_ability_modifier, apply_racial_modifiers


def generate_ability_scores(seed: int) -> dict[str, int]:
    """Generate random ability scores using 4d6 drop lowest."""
    rng = random.Random(seed)

    def roll_ability() -> int:
        rolls = [rng.randint(1, 6) for _ in range(4)]
        rolls.sort(reverse=True)
        return sum(rolls[:3])

    return {
        "str": roll_ability(),
        "int": roll_ability(),
        "wis": roll_ability(),
        "dex": roll_ability(),
        "con": roll_ability(),
        "chr": roll_ability(),
    }


def generate_ability_scores_detailed(seed: int) -> dict[str, dict]:
    """Generate ability scores with full per-die detail (4d6 drop lowest).

    Returns a dict keyed by ability (standard D&D order: str, dex, con, int, wis, chr).
    Each value contains:
      dice   - list[int]: all 4 dice as rolled (original order)
      kept   - list[int]: top 3 values (sorted descending)
      dropped - int: the lowest die that was dropped
      total  - int: sum of the 3 kept dice
    """
    rng = random.Random(seed)
    abilities = ["str", "dex", "con", "int", "wis", "chr"]
    result = {}
    for ability in abilities:
        dice = [rng.randint(1, 6) for _ in range(4)]
        sorted_desc = sorted(dice, reverse=True)
        kept = sorted_desc[:3]
        dropped = sorted_desc[3]
        result[ability] = {
            "dice": dice,
            "kept": kept,
            "dropped": dropped,
            "total": sum(kept),
        }
    return result


def roll_bonus_die(seed: int) -> int:
    """Roll a single d6 bonus die using a seed offset to avoid correlation."""
    return random.Random(seed ^ 0xDEADBEEF).randint(1, 6)


def create_default_world(name: str) -> World:
    """Create the default world hierarchy for a new campaign."""
    world = World(name=name)

    # System: Realmspace (root)
    system = Object(
        id=world.next_id(),
        parent=None,
        type="system",
        name="Realmspace",
        description="The crystal sphere containing Toril and its celestial bodies",
        is_moveable=False,
    )
    world.add_object(system)

    # Planet: Toril
    planet = Object(
        id=world.next_id(),
        parent=system.id,
        type="planet",
        name="Toril",
        description="The world of Abeir-Toril, home to the Forgotten Realms",
        is_moveable=False,
    )
    world.add_object(planet)

    # Continent: Faerûn
    continent = Object(
        id=world.next_id(),
        parent=planet.id,
        type="continent",
        name="Faerûn",
        description="The western continent of Toril",
        is_moveable=False,
    )
    world.add_object(continent)

    # Region: The Sword Coast
    region = Object(
        id=world.next_id(),
        parent=continent.id,
        type="region",
        name="The Sword Coast",
        description="A region on the western coast of Faerûn",
        is_moveable=False,
    )
    world.add_object(region)

    # Town: Phandalin (starting location)
    town = Object(
        id=world.next_id(),
        parent=region.id,
        type="town",
        name="Phandalin",
        description="A frontier town on the Triboar Trail",
        is_moveable=False,
        is_virtual=True,
    )
    world.add_object(town)

    # Inn: Stonehill Inn
    inn = Object(
        id=world.next_id(),
        parent=town.id,
        type="inn",
        name="Stonehill Inn",
        description="A modest inn run by Toblen Stonehill and his family",
        is_moveable=False,
        is_virtual=True,
    )
    world.add_object(inn)

    # Common Room
    common_room = Object(
        id=world.next_id(),
        parent=inn.id,
        type="room",
        name="Common Room",
        description="The main gathering area of the inn with tables and a fireplace",
        is_moveable=False,
        is_virtual=True,
        size=Size(length=30, width=20, height=10),
    )
    world.add_object(common_room)

    return world


_PC_NAMES = [
    "Aldric", "Brynn", "Caelum", "Dara", "Edric", "Faye", "Gareth", "Hana",
    "Idris", "Jora", "Kael", "Lira", "Mira", "Nori", "Oryn", "Petra",
    "Quinn", "Reva", "Soren", "Talis", "Uris", "Vex", "Wren", "Xara",
    "Yola", "Zara", "Thorin", "Elara", "Brom", "Cass",
]

_PERSONALITIES = [
    "Bold and brash, charges into danger without hesitation",
    "Cautious and calculating, always plans three steps ahead",
    "Gruff but loyal, values honor above all else",
    "Curious and bookish, always seeking knowledge",
    "Quick-witted and charming, can't resist a clever scheme",
    "Compassionate and steadfast, puts others before self",
    "Brooding and intense, haunted by a mysterious past",
    "Cheerful optimist who sees the best in everyone",
    "Sarcastic loner who hides genuine care behind sharp remarks",
    "Zealous believer, driven by faith or ideology",
]

_BACKSTORIES = [
    "A former soldier seeking redemption for past failures",
    "A scholar investigating ancient mysteries",
    "A street urchin turned adventurer by circumstance",
    "A priest spreading light in dark places",
    "An exile from a distant homeland, searching for purpose",
    "A wanderer who stumbled into adventure and never looked back",
    "A disgraced noble trying to restore family honor",
    "A reformed criminal using skills for good",
    "A hunter tracking a beast that destroyed their village",
    "An orphan raised by monks, now seeking their heritage",
]


def create_default_pcs(world: World, party_id: int, seed: int) -> None:
    """Create 4 randomized player characters as Objects in the world."""
    rng = random.Random(seed)
    races = list(RACE_MODIFIERS.keys())
    classes = list(CLASS_HIT_DICE.keys())

    used_names: set[str] = set()
    chosen_races = rng.sample(races, min(4, len(races)))
    chosen_classes = rng.sample(classes, min(4, len(classes)))

    for i in range(4):
        char_seed = seed + i * 1000

        # Pick a unique name
        candidate = rng.choice(_PC_NAMES)
        attempts = 0
        while candidate in used_names and attempts < 30:
            candidate = rng.choice(_PC_NAMES)
            attempts += 1
        used_names.add(candidate)

        race = chosen_races[i]
        char_class = chosen_classes[i]
        personality = _PERSONALITIES[rng.randrange(len(_PERSONALITIES))]
        backstory = _BACKSTORIES[rng.randrange(len(_BACKSTORIES))]

        # Generate abilities with racial modifiers
        abilities = generate_ability_scores(char_seed)
        abilities = apply_racial_modifiers(abilities, race)

        # Calculate HP
        con_mod = get_ability_modifier(abilities["con"])
        hit_die = CLASS_HIT_DICE.get(char_class, 8)
        max_hp = max(1, hit_die + con_mod)

        # Create PC as an Object with all properties
        pc = Object(
            id=world.next_id(),
            parent=party_id,
            type="PC",
            name=candidate,
            description=f"{race} {char_class}",
            location=Location(x=5 * (i % 2), y=5 * (i // 2), z=0),
            properties={
                "race": race,
                "classes": [{"type": char_class, "level": 1}],
                "abilities": abilities,
                "hp": {"max": max_hp, "current": max_hp},
                "personality": personality,
                "backstory": backstory,
                "goals": ["Complete the current quest", "Grow stronger through adventure"],
                "experience": 0,
            },
        )
        world.add_object(pc)


def new_campaign_object(name: str, seed: Optional[int] = None) -> Campaign:
    """Create a complete Campaign object with world and default PCs."""
    if seed is None:
        seed = random.randint(1, 999999)
    world = create_default_world(name)
    party = Object(
        id=world.next_id(),
        parent=7,  # Common room
        type="party",
        name="The Adventurers",
        description="A band of adventurers seeking fortune and glory",
        is_virtual=True,
    )
    world.add_object(party)
    create_default_pcs(world, party.id, seed)
    return Campaign(name=name, seed=seed, world=world)


def save_campaign(campaign: Campaign, path: Path) -> None:
    """Save campaign to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "name": campaign.name,
        "seed": campaign.seed,
        "turn_number": campaign.turn_number,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": datetime.now().isoformat(),
        "world": campaign.world.model_dump_yaml(),
    }

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def load_campaign_from_file(path: Path) -> Campaign:
    """Load campaign from YAML file."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Reconstruct world
    world_data = data["world"]
    world = World(
        name=world_data["name"],
        max_id=world_data["max_id"],
        delete_ids=world_data.get("delete_ids", []),
    )

    for obj_id_str, obj_data in world_data["objects"].items():
        obj = Object(
            id=obj_data["id"],
            parent=obj_data.get("parent"),
            type=obj_data["type"],
            name=obj_data.get("name"),
            description=obj_data.get("description"),
            location=Location.from_list(obj_data["location"]) if "location" in obj_data else Location(),
            size=Size.from_list(obj_data["size"]) if "size" in obj_data else Size(),
            weight=obj_data.get("weight", 0),
            cost=obj_data.get("cost", 0),
            is_moveable=obj_data.get("is_moveable", True),
            is_virtual=obj_data.get("is_virtual", False),
            properties=obj_data.get("properties", {}),
        )
        world.add_object(obj)

    return Campaign(
        name=data["name"],
        seed=data["seed"],
        world=world,
        turn_number=data.get("turn_number", 0),
        created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
    )
