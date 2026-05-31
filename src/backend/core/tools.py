"""World manipulation tools for the AI agents."""

from typing import Any, Optional
from pydantic import BaseModel

from ..models.world import World, Object, Location, Size
from ..models.user import CampaignMeta
from .combat import CombatEngine


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

    def __init__(self, world: World):
        self.world = world

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
            message_parts.append(f"{obj.name or 'Object'} has died!")

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
        success = self.world.delete_object(id, cascade=cascade)

        if success:
            if cascade:
                message = f"Deleted object {id} and {len(children)} children"
            else:
                message = f"Deleted object {id}, moved {len(children)} children to parent"
            return ToolResult(success=True, message=message, data={"id": id, "cascade": cascade})
        else:
            return ToolResult(success=False, message=f"Failed to delete object {id}")

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

    def get_sub_world(self, observer_id: int) -> ToolResult:
        """
        Get the visible world from an observer's perspective.

        Args:
            observer_id: Object ID of the observer
        """
        visible_world = self.world.get_visible_world(observer_id)
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
]
