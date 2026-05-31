"""World manipulation tools for the AI agents."""

import logging
import random
from typing import Any, Optional
from pydantic import BaseModel

from ..models.world import World, Object, Location, Size
from ..models.user import CampaignMeta
from .combat import CombatEngine

logger = logging.getLogger(__name__)

# D&D 5e XP thresholds per level (index = level, value = total XP needed to reach that level)
XP_THRESHOLDS: list[int] = [
    0,       # level 0 (unused placeholder)
    0,       # level 1
    300,     # level 2
    900,     # level 3
    2700,    # level 4
    6500,    # level 5
    14000,   # level 6
    23000,   # level 7
    34000,   # level 8
    48000,   # level 9
    64000,   # level 10
    85000,   # level 11
    100000,  # level 12
    120000,  # level 13
    140000,  # level 14
    165000,  # level 15
    195000,  # level 16
    225000,  # level 17
    265000,  # level 18
    305000,  # level 19
    355000,  # level 20
]

MAX_LEVEL = 20

# Number of Ability Score Improvement levels (levels where ASI is granted)
ASI_LEVELS = {4, 8, 12, 16, 19}


def xp_level_for(total_xp: int) -> int:
    """Return the level a character has reached given total XP."""
    level = 1
    for lvl in range(MAX_LEVEL, 0, -1):
        if total_xp >= XP_THRESHOLDS[lvl]:
            level = lvl
            break
    return level


def xp_to_next_level(total_xp: int) -> int:
    """Return XP needed to reach the next level, or 0 if already at max."""
    current = xp_level_for(total_xp)
    if current >= MAX_LEVEL:
        return 0
    return XP_THRESHOLDS[current + 1] - total_xp


class ToolResult(BaseModel):
    """Result of a tool call."""

    success: bool
    message: str
    data: Optional[dict] = None


class WorldTools:
    """
    Tools for manipulating the game world.

    These tools are called by the AI agents to modify world state.
    Only tools are allowed to update the world.
    """

    def __init__(self, world: World, memgraph_url: Optional[str] = None):
        self.world = world
        self._memgraph_url = memgraph_url

    def _sync_upsert(self, obj: Object) -> None:
        """Push a single object upsert to Memgraph; log and swallow on failure."""
        if self._memgraph_url is None:
            return
        try:
            from .memgraph_client import upsert_object, _obj_to_props
            upsert_object(obj.id, _obj_to_props(obj), obj.parent, url=self._memgraph_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Memgraph upsert failed for object %d: %s", obj.id, exc)

    def _sync_delete(self, obj_id: int) -> None:
        """Remove a node from Memgraph; log and swallow on failure."""
        if self._memgraph_url is None:
            return
        try:
            from .memgraph_client import delete_object as mg_delete
            mg_delete(obj_id, url=self._memgraph_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Memgraph delete failed for object %d: %s", obj_id, exc)

    def create_object(
        self,
        type: str,
        parent_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[list[float]] = None,
        size: Optional[list[float]] = None,
        weight: float = 0.0,
        cost: int = 0,
        is_moveable: bool = True,
        is_virtual: bool = False,
        **properties: Any,
    ) -> ToolResult:
        """
        Create a new object in the world.

        Args:
            type: Object type (e.g. "sword", "room", "PC")
            parent_id: ID of the parent object
            name: Optional name
            description: Optional description
            location: [x, y, z] coordinates relative to parent
            size: [l, w, h] dimensions
            weight: Weight in pounds
            cost: Cost in copper pieces
            is_moveable: Can the location change?
            is_virtual: Can children extend beyond parent bounds?
            **properties: Additional properties (hp, abilities, etc.)
        """
        # Validate parent exists
        parent = self.world.get_object(parent_id)
        if not parent:
            return ToolResult(success=False, message=f"Parent object {parent_id} not found")

        obj_id = self.world.next_id()
        obj = Object(
            id=obj_id,
            parent=parent_id,
            type=type,
            name=name,
            description=description,
            location=Location.from_list(location) if location else Location(),
            size=Size.from_list(size) if size else Size(),
            weight=weight,
            cost=cost,
            is_moveable=is_moveable,
            is_virtual=is_virtual,
            properties=properties,
        )
        self.world.add_object(obj)
        self._sync_upsert(obj)
        return ToolResult(
            success=True,
            message=f"Created {type} '{name or 'unnamed'}' with ID {obj_id}",
            data={"id": obj_id},
        )

    def move_object(self, id: int, parent_id: int, location: Optional[list[float]] = None) -> ToolResult:
        """
        Move an object to a new parent.

        Args:
            id: ID of the object to move
            parent_id: ID of the new parent object
            location: Optional new location relative to parent
        """
        obj = self.world.get_object(id)
        if not obj:
            return ToolResult(success=False, message=f"Object {id} not found")

        if not obj.is_moveable:
            return ToolResult(success=False, message=f"Object {id} is not moveable")

        new_parent = self.world.get_object(parent_id)
        if not new_parent:
            return ToolResult(success=False, message=f"Parent object {parent_id} not found")

        old_parent_id = obj.parent
        obj.parent = parent_id
        if location:
            obj.location = Location.from_list(location)
        else:
            obj.location = Location()

        self._sync_upsert(obj)
        return ToolResult(
            success=True,
            message=f"Moved object {id} from parent {old_parent_id} to {parent_id}",
            data={"id": id, "old_parent": old_parent_id, "new_parent": parent_id},
        )

    def set_object_property(self, id: int, name: str, value: Any) -> ToolResult:
        """
        Set a property on an object.

        Args:
            id: ID of the object
            name: Property name
            value: Property value
        """
        obj = self.world.get_object(id)
        if not obj:
            return ToolResult(success=False, message=f"Object {id} not found")

        # Handle built-in properties
        if hasattr(obj, name) and name not in ("id", "parent", "properties"):
            if name == "location" and isinstance(value, list):
                obj.location = Location.from_list(value)
            elif name == "size" and isinstance(value, list):
                obj.size = Size.from_list(value)
            else:
                setattr(obj, name, value)
        else:
            # Store in properties dict
            obj.properties[name] = value

        return ToolResult(
            success=True,
            message=f"Set {name}={value} on object {id}",
            data={"id": id, "property": name, "value": value},
        )

    def add_hp(self, id: int, delta: int) -> ToolResult:
        """
        Modify an object's HP.

        Args:
            id: Object ID of the player/creature
            delta: Amount to add (negative for damage)

        Returns:
            Result including new HP and death status
        """
        obj = self.world.get_object(id)
        if not obj:
            return ToolResult(success=False, message=f"Object {id} not found")

        hp = obj.properties.get("hp")
        if not hp:
            return ToolResult(success=False, message=f"Object {id} has no HP")

        old_hp = hp["current"]
        new_hp = max(0, min(hp["max"], old_hp + delta))
        hp["current"] = new_hp
        is_dead = new_hp <= 0

        message_parts = [f"Modified HP of {obj.name or 'object'}: {old_hp} -> {new_hp}"]
        if delta < 0:
            message_parts.append(f"({-delta} damage)")
        else:
            message_parts.append(f"({delta} healing)")

        if is_dead:
            message_parts.append(f"{obj.name or 'Object'} is unconscious and must make death saving throws!")
            # Initialize death saves when HP first drops to 0
            if old_hp > 0:
                obj.properties["death_saves"] = {"successes": 0, "failures": 0}

        return ToolResult(
            success=True,
            message=" ".join(message_parts),
            data={"id": id, "old_hp": old_hp, "new_hp": new_hp, "is_dead": is_dead},
        )

    def delete_object(self, id: int, cascade: bool = False) -> ToolResult:
        """
        Delete an object from the world.

        Args:
            id: ID of the object to delete
            cascade: If True, delete all children. If False, move children to parent.
        """
        obj = self.world.get_object(id)
        if not obj:
            return ToolResult(success=False, message=f"Object {id} not found")

        if obj.parent is None:
            return ToolResult(success=False, message="Cannot delete the root object")

        children = self.world.get_children(id)
        # Collect descendants before the cascade removes them from the world.
        deleted_ids = [id]
        if cascade:
            deleted_ids += [d.id for d in self.world.get_descendants(id)]

        success = self.world.delete_object(id, cascade=cascade)

        if success:
            for did in deleted_ids:
                self._sync_delete(did)
            if cascade:
                message = f"Deleted object {id} and {len(children)} children"
            else:
                message = f"Deleted object {id}, moved {len(children)} children to parent"
            return ToolResult(success=True, message=message, data={"id": id, "cascade": cascade})
        else:
            return ToolResult(success=False, message=f"Failed to delete object {id}")

    def award_xp(self, id: int, amount: int) -> ToolResult:
        """
        Award experience points to a character.

        When XP crosses a level threshold the result data includes a
        ``level_up`` key with the new level, hit die, and whether an ASI
        is available.

        Args:
            id: Object ID of the PC
            amount: XP to award (must be positive)
        """
        if amount <= 0:
            return ToolResult(success=False, message="XP amount must be positive")

        obj = self.world.get_object(id)
        if not obj:
            return ToolResult(success=False, message=f"Object {id} not found")

        old_xp = obj.properties.get("experience", 0)
        new_xp = old_xp + amount
        obj.properties["experience"] = new_xp

        old_level = xp_level_for(old_xp)
        new_level = xp_level_for(new_xp)

        # Update class level on level-up
        level_up_data = None
        if new_level > old_level:
            classes = obj.properties.get("classes", [])
            if classes:
                classes[0]["level"] = new_level
                obj.properties["classes"] = classes

            from ..models.player import CLASS_HIT_DICE
            class_type = classes[0].get("type", "Fighter") if classes else "Fighter"
            hit_die = CLASS_HIT_DICE.get(class_type, 8)
            has_asi = new_level in ASI_LEVELS

            level_up_data = {
                "character_id": id,
                "character_name": obj.name or f"object_{id}",
                "old_level": old_level,
                "new_level": new_level,
                "hit_die": hit_die,
                "class_type": class_type,
                "has_asi": has_asi,
            }

        msg_parts = [
            f"Awarded {amount} XP to {obj.name or 'object'}: "
            f"{old_xp} -> {new_xp} XP (level {new_level})"
        ]
        if level_up_data:
            msg_parts.append(f"LEVEL UP! {obj.name} is now level {new_level}!")

        return ToolResult(
            success=True,
            message=" ".join(msg_parts),
            data={
                "id": id,
                "old_xp": old_xp,
                "new_xp": new_xp,
                "old_level": old_level,
                "new_level": new_level,
                "level_up": level_up_data,
                "xp_to_next": xp_to_next_level(new_xp),
            },
        )

    def cast_spell(self, id: int, slot_level: int) -> ToolResult:
        """
        Consume one spell slot of the given level for a caster character.

        Args:
            id: Object ID of the PC
            slot_level: Spell slot level to consume (1-9)
        """
        obj = self.world.get_object(id)
        if not obj:
            return ToolResult(success=False, message=f"Object {id} not found")

        spell_slots = obj.properties.get("spell_slots")
        if not spell_slots:
            return ToolResult(success=False, message=f"Object {id} has no spell slots")

        key = str(slot_level)
        slot = spell_slots.get(key)
        if not slot:
            return ToolResult(
                success=False,
                message=f"No level-{slot_level} spell slots available",
            )

        available = slot["max"] - slot["used"]
        if available <= 0:
            return ToolResult(
                success=False,
                message=f"No level-{slot_level} spell slots remaining",
            )

        slot["used"] += 1
        obj.properties["spell_slots"] = spell_slots

        remaining = available - 1
        return ToolResult(
            success=True,
            message=(
                f"{obj.name or 'Caster'} expends a level-{slot_level} spell slot "
                f"({remaining} remaining)."
            ),
            data={
                "id": id,
                "slot_level": slot_level,
                "used": slot["used"],
                "max": slot["max"],
                "remaining": remaining,
            },
        )

    def long_rest(self, id: int) -> ToolResult:
        """
        Perform a long rest for a character: restore all spell slots and full HP.

        Args:
            id: Object ID of the PC
        """
        obj = self.world.get_object(id)
        if not obj:
            return ToolResult(success=False, message=f"Object {id} not found")

        restored = []

        # Restore spell slots
        spell_slots = obj.properties.get("spell_slots")
        if spell_slots:
            for slot_data in spell_slots.values():
                slot_data["used"] = 0
            obj.properties["spell_slots"] = spell_slots
            restored.append("spell slots")

        # Restore HP to max
        hp = obj.properties.get("hp")
        if hp:
            old_hp = hp["current"]
            hp["current"] = hp["max"]
            obj.properties["hp"] = hp
            if old_hp < hp["max"]:
                restored.append(f"HP ({old_hp} -> {hp['max']})")

        name = obj.name or "Character"
        if restored:
            msg = f"{name} takes a long rest and recovers: {', '.join(restored)}."
        else:
            msg = f"{name} takes a long rest."

        return ToolResult(
            success=True,
            message=msg,
            data={
                "id": id,
                "spell_slots": obj.properties.get("spell_slots"),
                "hp": obj.properties.get("hp"),
            },
        )

    def roll_death_save(self, id: int) -> ToolResult:
        """
        Roll a death saving throw for an unconscious PC (HP = 0).

        Rolls d20: 20 = instant stabilize, ≥ 10 = success, < 10 = failure.
        Three successes = stable; two failures = dead.

        Args:
            id: Object ID of the unconscious PC
        """
        obj = self.world.get_object(id)
        if not obj:
            return ToolResult(success=False, message=f"Object {id} not found")

        hp = obj.properties.get("hp", {})
        if hp.get("current", 1) > 0:
            return ToolResult(success=False, message=f"Object {id} is not unconscious (HP > 0)")

        saves = obj.properties.setdefault("death_saves", {"successes": 0, "failures": 0})
        roll = random.randint(1, 20)

        # Natural 20: instant stabilize
        if roll == 20:
            saves["successes"] = 3
            saves["failures"] = 0
            obj.properties["death_saves"] = saves
            return ToolResult(
                success=True,
                message=f"{obj.name or 'PC'} rolled a natural 20 on their death save and stabilizes!",
                data={
                    "id": id,
                    "roll": roll,
                    "result": "success",
                    "successes": saves["successes"],
                    "failures": saves["failures"],
                    "stable": True,
                    "dead": False,
                },
            )

        is_success = roll >= 10
        if is_success:
            saves["successes"] = min(3, saves["successes"] + 1)
        else:
            saves["failures"] = min(3, saves["failures"] + 1)

        obj.properties["death_saves"] = saves

        stable = saves["successes"] >= 3
        dead = saves["failures"] >= 2

        outcome = "success" if is_success else "failure"
        name = obj.name or "PC"
        if stable:
            narrative = f"{name} rolled {roll} — success! {name} stabilizes with 3 successes."
        elif dead:
            narrative = f"{name} rolled {roll} — failure! {name} has died (2 failures)."
        else:
            narrative = (
                f"{name} rolled {roll} — {outcome}! "
                f"({saves['successes']} successes, {saves['failures']} failures)"
            )

        return ToolResult(
            success=True,
            message=narrative,
            data={
                "id": id,
                "roll": roll,
                "result": outcome,
                "successes": saves["successes"],
                "failures": saves["failures"],
                "stable": stable,
                "dead": dead,
            },
        )

    def add_quest(self, title: str, milestones: list[str]) -> ToolResult:
        """
        Add a new quest to the campaign world.

        Quests are stored under world root properties.quests as a list of dicts.
        Each quest has: id, title, milestones (list of {text, completed}).

        Args:
            title: Quest title
            milestones: List of milestone description strings
        """
        root = next(
            (obj for obj in self.world.objects.values() if obj.parent is None),
            None,
        )
        if not root:
            return ToolResult(success=False, message="World root object not found")

        quests = root.properties.get("quests", [])
        quest_id = len(quests)
        quest = {
            "id": quest_id,
            "title": title,
            "milestones": [{"text": m, "completed": False} for m in milestones],
        }
        quests.append(quest)
        root.properties["quests"] = quests

        return ToolResult(
            success=True,
            message=f"Quest '{title}' added with {len(milestones)} milestone(s)",
            data={"quest": quest},
        )

    def complete_milestone(self, quest_id: int, milestone_idx: int) -> ToolResult:
        """
        Mark a quest milestone as completed.

        Args:
            quest_id: Index of the quest in the quests list
            milestone_idx: Index of the milestone within the quest
        """
        root = next(
            (obj for obj in self.world.objects.values() if obj.parent is None),
            None,
        )
        if not root:
            return ToolResult(success=False, message="World root object not found")

        quests = root.properties.get("quests", [])
        if quest_id < 0 or quest_id >= len(quests):
            return ToolResult(success=False, message=f"Quest {quest_id} not found")

        quest = quests[quest_id]
        milestones = quest.get("milestones", [])
        if milestone_idx < 0 or milestone_idx >= len(milestones):
            return ToolResult(
                success=False,
                message=f"Milestone {milestone_idx} not found in quest {quest_id}",
            )

        milestone = milestones[milestone_idx]
        if milestone["completed"]:
            return ToolResult(
                success=True,
                message=f"Milestone already completed: {milestone['text']}",
                data={"quest": quest},
            )

        milestone["completed"] = True
        root.properties["quests"] = quests

        return ToolResult(
            success=True,
            message=f"Milestone completed: {milestone['text']}",
            data={"quest": quest, "milestone_idx": milestone_idx},
        )

    def get_quests(self) -> ToolResult:
        """Return all quests stored on the world root."""
        root = next(
            (obj for obj in self.world.objects.values() if obj.parent is None),
            None,
        )
        quests = root.properties.get("quests", []) if root else []
        return ToolResult(
            success=True,
            message=f"{len(quests)} quest(s) found",
            data={"quests": quests},
        )

    def set_npc_disposition(
        self,
        npc_id: int,
        disposition: str,
        notes: str = "",
    ) -> ToolResult:
        """
        Set or update a known NPC's disposition toward the party.

        Disposition must be one of: friendly, neutral, hostile, allied.
        NPC data is stored under world root properties.known_npcs keyed by npc_id.

        Args:
            npc_id: ID of the NPC object
            disposition: One of friendly, neutral, hostile, allied
            notes: Optional DM notes about this NPC
        """
        valid = {"friendly", "neutral", "hostile", "allied"}
        if disposition not in valid:
            return ToolResult(
                success=False,
                message=f"Invalid disposition '{disposition}'. Must be one of: {', '.join(sorted(valid))}",
            )

        npc = self.world.get_object(npc_id)
        if not npc:
            return ToolResult(success=False, message=f"NPC {npc_id} not found")

        root = next(
            (obj for obj in self.world.objects.values() if obj.parent is None),
            None,
        )
        if not root:
            return ToolResult(success=False, message="World root object not found")

        known_npcs = root.properties.get("known_npcs", {})
        key = str(npc_id)
        existing = known_npcs.get(key, {})
        known_npcs[key] = {
            "id": npc_id,
            "name": npc.name or f"NPC {npc_id}",
            "disposition": disposition,
            "notes": notes if notes else existing.get("notes", ""),
        }
        root.properties["known_npcs"] = known_npcs

        return ToolResult(
            success=True,
            message=f"Set {npc.name or npc_id} disposition to {disposition}",
            data={"npc": known_npcs[key]},
        )

    def get_npc_relationships(self) -> ToolResult:
        """Return all known NPCs and their dispositions from the world root."""
        root = next(
            (obj for obj in self.world.objects.values() if obj.parent is None),
            None,
        )
        known_npcs = root.properties.get("known_npcs", {}) if root else {}
        npcs = list(known_npcs.values())
        return ToolResult(
            success=True,
            message=f"{len(npcs)} known NPC(s)",
            data={"npcs": npcs},
        )

    def trigger_travel_encounter(
        self,
        location_type: str = "default",
        party_level: int = 1,
        seed: Optional[int] = None,
    ) -> ToolResult:
        """
        Roll a hidden d20 encounter check for a travel segment.

        On a hit (d20 >= 15), returns encounter data so the DM can spawn
        enemies and switch to Combat mode.

        Args:
            location_type: Terrain type (forest, dungeon, road, mountain, swamp,
                           plains, desert, urban, or default)
            party_level: Average party level (used for future scaling)
            seed: Optional RNG seed for reproducible tests
        """
        from .travel_encounter import TravelEncounterEngine

        engine = TravelEncounterEngine(seed=seed)
        roll_result = engine.roll_encounter(
            location_type=location_type,
            party_level=party_level,
        )

        if roll_result["triggered"]:
            enc = roll_result["encounter"]
            return ToolResult(
                success=True,
                message=(
                    f"Encounter triggered! (d20={roll_result['d20_roll']} >= {roll_result['encounter_dc']}) "
                    f"{enc['count']}x {enc['enemy_name']} (CR {enc['cr']}) appear."
                ),
                data=roll_result,
            )
        else:
            return ToolResult(
                success=True,
                message=(
                    f"Travel uneventful. (d20={roll_result['d20_roll']} < {roll_result['encounter_dc']})"
                ),
                data=roll_result,
            )

    def get_object(self, id: int) -> ToolResult:
        """
        Get an object by ID.

        Args:
            id: ID of the object to retrieve
        """
        obj = self.world.get_object(id)
        if not obj:
            return ToolResult(success=False, message=f"Object {id} not found")

        return ToolResult(
            success=True,
            message=f"Found object {id}: {obj.type} '{obj.name or 'unnamed'}'",
            data=obj.model_dump(),
        )

    def get_sub_world(
        self,
        observer_id: int,
        perception_bonus: int = 0,
        vision_range: float = 60.0,
        darkvision_range: float = 0.0,
    ) -> ToolResult:
        """
        Get the visible world from an observer's perspective.

        Applies range, light/dark, and stealth perception filtering.

        Args:
            observer_id: Object ID of the observer
            perception_bonus: Observer's Perception modifier (default 0)
            vision_range: Normal sight radius in feet (default 60)
            darkvision_range: Darkvision radius in feet (default 0 = none)
        """
        visible_world = self.world.get_visible_world(
            observer_id,
            perception_bonus=perception_bonus,
            vision_range=vision_range,
            darkvision_range=darkvision_range,
        )
        return ToolResult(
            success=True,
            message=f"Retrieved visible world with {len(visible_world.objects)} objects",
            data=visible_world.model_dump_yaml(),
        )


class CombatTools:
    """
    Combat tools callable by the DM agent.

    Wraps CombatEngine to provide initiative rolling, turn management,
    attack resolution, and saving throws as discrete tool calls.
    """

    def __init__(self, world: World, meta: CampaignMeta):
        self.engine = CombatEngine(world, meta)

    def start_combat(self, combatant_ids: list[int]) -> ToolResult:
        """
        Begin combat by rolling initiative for all listed combatants.

        Args:
            combatant_ids: List of world object IDs entering combat
        """
        result = self.engine.start_combat(combatant_ids)
        if "error" in result:
            return ToolResult(success=False, message=result["error"])
        names = [e["name"] for e in result["initiative_order"]]
        active = result["active_turn"]
        return ToolResult(
            success=True,
            message=f"Combat started. Initiative order: {', '.join(names)}. First turn: {active}.",
            data=result,
        )

    def next_turn(self) -> ToolResult:
        """Advance combat to the next combatant's turn."""
        result = self.engine.next_turn()
        if "error" in result:
            return ToolResult(success=False, message=result["error"])
        return ToolResult(
            success=True,
            message=f"Turn advanced. Now active: {result['active_name']} (ID {result['active_turn']}).",
            data=result,
        )

    def end_combat(self) -> ToolResult:
        """End combat and return to Exploration mode."""
        result = self.engine.end_combat()
        return ToolResult(success=True, message=result["message"], data=result)

    def roll_attack(
        self,
        attacker_id: int,
        target_id: int,
        attack_bonus: int = 0,
    ) -> ToolResult:
        """
        Roll an attack roll (d20 + bonus) against target AC.

        Args:
            attacker_id: Object ID of the attacker
            target_id: Object ID of the target
            attack_bonus: Proficiency + ability modifier (default 0)
        """
        result = self.engine.roll_attack(attacker_id, target_id, attack_bonus)
        if "error" in result:
            return ToolResult(success=False, message=result["error"])
        status = "HIT" if result["hit"] else "MISS"
        crit = " (CRITICAL HIT!)" if result["critical_hit"] else (" (CRITICAL MISS)" if result["critical_miss"] else "")
        msg = (
            f"{result['attacker']} attacks {result['target']}: "
            f"d20={result['d20_roll']}+{result['attack_bonus']}={result['total']} vs AC {result['target_ac']} — {status}{crit}"
        )
        return ToolResult(success=True, message=msg, data=result)

    def roll_saving_throw(
        self,
        target_id: int,
        ability: str,
        dc: int,
    ) -> ToolResult:
        """
        Roll a saving throw for a target against a difficulty class.

        Args:
            target_id: Object ID of the creature making the save
            ability: Ability score to use: str, dex, con, int, wis, chr
            dc: Difficulty Class to beat or meet
        """
        result = self.engine.roll_saving_throw(target_id, ability, dc)
        if "error" in result:
            return ToolResult(success=False, message=result["error"])
        status = "SUCCESS" if result["success"] else "FAILURE"
        msg = (
            f"{result['target']} {ability.upper()} saving throw: "
            f"d20={result['d20_roll']}+{result['modifier']}={result['total']} vs DC {result['dc']} — {status}"
        )
        return ToolResult(success=True, message=msg, data=result)

    def roll_damage(self, attacker_id: int, damage_dice: str) -> ToolResult:
        """
        Roll damage dice for an attack.

        Args:
            attacker_id: Object ID of the attacker (used for context only)
            damage_dice: Dice notation like '1d8+3', '2d6', 'd4+1'
        """
        from .combat import roll_dice

        attacker = self.engine.world.get_object(attacker_id)
        attacker_name = attacker.name if attacker else f"object_{attacker_id}"

        try:
            result = roll_dice(damage_dice, self.engine.rng)
        except ValueError as e:
            return ToolResult(success=False, message=str(e))

        msg = (
            f"{attacker_name} rolls {damage_dice}: {result['rolls']} "
            f"(modifier {result['modifier']:+d}) = {result['total']} damage"
        )
        return ToolResult(success=True, message=msg, data=result)


# Tool definitions for LlamaIndex/Ollama
TOOL_DEFINITIONS = [
    {
        "name": "create_object",
        "description": "Create a new object in the world",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "Object type (e.g. 'sword', 'room', 'PC')"},
                "parent_id": {"type": "integer", "description": "ID of the parent object"},
                "name": {"type": "string", "description": "Optional name"},
                "description": {"type": "string", "description": "Optional description"},
                "location": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] coordinates"},
                "size": {"type": "array", "items": {"type": "number"}, "description": "[l, w, h] dimensions"},
                "weight": {"type": "number", "description": "Weight in pounds"},
                "cost": {"type": "integer", "description": "Cost in copper pieces"},
            },
            "required": ["type", "parent_id"],
        },
    },
    {
        "name": "move_object",
        "description": "Move an object to a new parent location",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID of the object to move"},
                "parent_id": {"type": "integer", "description": "ID of the new parent object"},
                "location": {"type": "array", "items": {"type": "number"}, "description": "New [x, y, z] location"},
            },
            "required": ["id", "parent_id"],
        },
    },
    {
        "name": "set_object_property",
        "description": "Set a property on an object",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID of the object"},
                "name": {"type": "string", "description": "Property name"},
                "value": {"description": "Property value"},
            },
            "required": ["id", "name", "value"],
        },
    },
    {
        "name": "add_hp",
        "description": "Modify a player's HP (negative for damage, positive for healing)",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Object ID of the player"},
                "delta": {"type": "integer", "description": "Amount to add (negative for damage)"},
            },
            "required": ["id", "delta"],
        },
    },
    {
        "name": "delete_object",
        "description": "Delete an object from the world",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID of the object to delete"},
                "cascade": {"type": "boolean", "description": "If true, delete children; if false, move to parent"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "get_object",
        "description": "Get an object by ID",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "ID of the object"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "award_xp",
        "description": "Award experience points to a player character after combat or a story milestone",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Object ID of the PC"},
                "amount": {"type": "integer", "description": "XP to award (positive integer)"},
            },
            "required": ["id", "amount"],
        },
    },
    {
        "name": "cast_spell",
        "description": (
            "Consume one spell slot of the given level for a caster. "
            "Call this when a player casts a leveled spell. Returns an error if no slots remain."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Object ID of the caster PC"},
                "slot_level": {"type": "integer", "description": "Spell slot level to consume (1-9)"},
            },
            "required": ["id", "slot_level"],
        },
    },
    {
        "name": "long_rest",
        "description": (
            "Perform a long rest for a character: restore all spell slots and full HP."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Object ID of the PC"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "roll_death_save",
        "description": (
            "Roll a death saving throw for an unconscious PC (HP = 0). "
            "Roll d20: 20 = instant stable, >=10 = success, <10 = failure. "
            "Three successes = stable; two failures = dead. "
            "Call this at the start of each unconscious PC's turn during Combat."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Object ID of the unconscious PC"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "add_quest",
        "description": (
            "Add a new quest to the campaign with a title and a list of milestone descriptions. "
            "Call when the story introduces a new objective or side quest."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Quest title"},
                "milestones": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of milestone descriptions",
                },
            },
            "required": ["title", "milestones"],
        },
    },
    {
        "name": "complete_milestone",
        "description": (
            "Mark a quest milestone as completed. "
            "Call when the party achieves a quest objective."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "quest_id": {"type": "integer", "description": "Index of the quest"},
                "milestone_idx": {"type": "integer", "description": "Index of the milestone within the quest"},
            },
            "required": ["quest_id", "milestone_idx"],
        },
    },
]
