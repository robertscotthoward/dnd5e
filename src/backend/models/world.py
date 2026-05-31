"""World and Object models for the D&D 5e game engine."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class Location(BaseModel):
    """3D coordinates relative to parent. [0,0,0] means "with" or "in" the parent."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.z]

    @classmethod
    def from_list(cls, coords: list[float]) -> "Location":
        return cls(x=coords[0], y=coords[1], z=coords[2])


class Size(BaseModel):
    """Dimensions of an object in feet. [0,0,0] means size is irrelevant."""

    length: float = 0.0
    width: float = 0.0
    height: float = 0.0

    def to_list(self) -> list[float]:
        return [self.length, self.width, self.height]

    @classmethod
    def from_list(cls, dims: list[float]) -> "Size":
        return cls(length=dims[0], width=dims[1], height=dims[2])


class Object(BaseModel):
    """
    Base object in the world. Everything is an object - locations, items, players, parties.

    The world resolution is 5 feet. Objects form a parent/child hierarchy.
    All game data (stats, abilities, HP, etc.) is stored in properties.
    """

    id: int
    parent: Optional[int] = None  # None only for the root System object
    type: str  # e.g. PC, NPC, party, system, planet, continent, bed, sword, ring
    name: Optional[str] = None
    description: Optional[str] = None
    location: Location = Field(default_factory=Location)
    size: Size = Field(default_factory=Size)
    weight: float = 0.0  # in pounds
    cost: int = 0  # in copper pieces
    is_moveable: bool = True  # can the location change?
    is_virtual: bool = False  # can children extend beyond parent bounds?
    properties: dict[str, Any] = Field(default_factory=dict)  # all additional data

    # Convenience methods for common properties
    def get_prop(self, key: str, default: Any = None) -> Any:
        """Get a property value."""
        return self.properties.get(key, default)

    def set_prop(self, key: str, value: Any) -> None:
        """Set a property value."""
        self.properties[key] = value

    @property
    def hp(self) -> Optional[dict]:
        """Get HP if this is a player/creature."""
        return self.properties.get("hp")

    @property
    def is_dead(self) -> bool:
        """Check if this object is dead (HP <= 0)."""
        hp = self.hp
        if hp is None:
            return False
        return hp.get("current", 1) <= 0

    @property
    def abilities(self) -> Optional[dict]:
        """Get ability scores if this is a player/creature."""
        return self.properties.get("abilities")

    def get_ability_modifier(self, ability: str) -> int:
        """Calculate ability modifier: (score - 10) // 2."""
        abilities = self.abilities
        if not abilities:
            return 0
        score = abilities.get(ability, 10)
        return (score - 10) // 2

    def model_dump_yaml(self) -> dict:
        """Convert to YAML-friendly dict."""
        data = {
            "id": self.id,
            "type": self.type,
        }
        if self.parent is not None:
            data["parent"] = self.parent
        if self.name:
            data["name"] = self.name
        if self.description:
            data["description"] = self.description
        if self.location.x != 0 or self.location.y != 0 or self.location.z != 0:
            data["location"] = self.location.to_list()
        if self.size.length != 0 or self.size.width != 0 or self.size.height != 0:
            data["size"] = self.size.to_list()
        if self.weight != 0:
            data["weight"] = self.weight
        if self.cost != 0:
            data["cost"] = self.cost
        if not self.is_moveable:
            data["is_moveable"] = self.is_moveable
        if self.is_virtual:
            data["is_virtual"] = self.is_virtual
        if self.properties:
            data["properties"] = self.properties
        return data


class World(BaseModel):
    """
    The game world containing all objects.

    Objects are stored in a dictionary keyed by integer ID.
    Everything is an object - locations, items, players, parties.
    """

    name: str
    max_id: int = 0
    delete_ids: list[int] = Field(default_factory=list)
    objects: dict[int, Object] = Field(default_factory=dict)

    def next_id(self) -> int:
        """Get the next available object ID."""
        self.max_id += 1
        return self.max_id

    def add_object(self, obj: Object) -> Object:
        """Add an object to the world."""
        self.objects[obj.id] = obj
        return obj

    def get_object(self, obj_id: int) -> Optional[Object]:
        """Get an object by ID."""
        return self.objects.get(obj_id)

    def get_objects_by_type(self, obj_type: str) -> list[Object]:
        """Get all objects of a specific type."""
        return [obj for obj in self.objects.values() if obj.type == obj_type]

    def get_pcs(self) -> list[Object]:
        """Get all player characters."""
        return self.get_objects_by_type("PC")

    def get_npcs(self) -> list[Object]:
        """Get all non-player characters."""
        return self.get_objects_by_type("NPC")

    def get_parties(self) -> list[Object]:
        """Get all parties."""
        return self.get_objects_by_type("party")

    def delete_object(self, obj_id: int, cascade: bool = False) -> bool:
        """
        Delete an object from the world.

        If cascade=True, delete all children.
        If cascade=False, move children to the deleted object's parent.
        """
        obj = self.objects.get(obj_id)
        if not obj:
            return False

        children = self.get_children(obj_id)

        if cascade:
            for child in children:
                self.delete_object(child.id, cascade=True)
        else:
            for child in children:
                child.parent = obj.parent

        del self.objects[obj_id]
        self.delete_ids.append(obj_id)
        return True

    def get_children(self, parent_id: int) -> list[Object]:
        """Get all direct children of an object."""
        return [obj for obj in self.objects.values() if obj.parent == parent_id]

    def get_descendants(self, parent_id: int) -> list[Object]:
        """Get all descendants (children, grandchildren, etc.) of an object."""
        descendants = []
        children = self.get_children(parent_id)
        for child in children:
            descendants.append(child)
            descendants.extend(self.get_descendants(child.id))
        return descendants

    def get_ancestors(self, obj_id: int) -> list[Object]:
        """Get all ancestors (parent, grandparent, etc.) up to root."""
        ancestors = []
        obj = self.objects.get(obj_id)
        while obj and obj.parent is not None:
            parent = self.objects.get(obj.parent)
            if parent:
                ancestors.append(parent)
                obj = parent
            else:
                break
        return ancestors

    def get_party_members(self, party_id: int) -> list[Object]:
        """Get all members of a party (PCs/NPCs whose parent is the party)."""
        return [
            obj for obj in self.objects.values()
            if obj.parent == party_id and obj.type in ("PC", "NPC")
        ]

    def _euclidean_distance(self, a: "Object", b: "Object") -> float:
        """Euclidean distance between two objects in feet (same-parent coordinate space)."""
        dx = a.location.x - b.location.x
        dy = a.location.y - b.location.y
        dz = a.location.z - b.location.z
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def _is_location_dark(self, obj_id: int) -> bool:
        """
        Walk ancestors to find the nearest room/area and check its light property.

        Returns True when the nearest enclosing container with a light property
        has light == "dark".  Defaults to lit (False) when no such ancestor exists.
        """
        obj = self.objects.get(obj_id)
        while obj and obj.parent is not None:
            parent = self.objects.get(obj.parent)
            if parent is None:
                break
            light_state = parent.properties.get("light")
            if light_state is not None:
                return str(light_state).lower() == "dark"
            obj = parent
        return False

    def get_visible_world(
        self,
        observer_id: int,
        perception_bonus: int = 0,
        vision_range: float = 60.0,
        darkvision_range: float = 0.0,
        is_night: bool = False,
        observer_race: str = "",
    ) -> "World":
        """
        Return the subset of the world visible to the observer.

        Visibility rules applied in order:
        1. The observer itself is always visible.
        2. All ancestors (containers, rooms, continents, etc.) are always visible —
           the observer must know what they are inside.
        3. Siblings sharing the same direct parent are visible when within
           `vision_range` feet AND the location is lit (or within `darkvision_range`
           if the location is dark).
        4. Children of a sibling are only visible when the sibling is not a closed
           container (`properties.closed` is falsy).
        5. Stealth / hidden objects require the observer to beat the object's
           `properties.stealth_dc` with a passive perception check
           (10 + perception_bonus).
        6. At night, non-darkvision races suffer disadvantage on Perception
           (modelled as -5 to passive perception).

        Args:
            observer_id: World object ID of the perceiving character.
            perception_bonus: Observer's Perception skill modifier (default 0).
            vision_range: Normal sight radius in feet (default 60).
            darkvision_range: Darkvision radius in feet (default 0 = none).
            is_night: True when the campaign is in night time.
            observer_race: Race name of the observer; used for darkvision check.
        """
        from src.backend.core.time_cycle import perception_disadvantage  # local import avoids circular

        observer = self.objects.get(observer_id)
        if not observer:
            return World(name=f"{self.name}_visible")

        visible_ids: set[int] = {observer_id}

        # --- 1. Ancestors always visible ---
        for ancestor in self.get_ancestors(observer_id):
            visible_ids.add(ancestor.id)

        # --- 2. Siblings and range / light / stealth filtering ---
        # Night disadvantage: -5 penalty to passive perception for non-darkvision races
        night_penalty = 5 if perception_disadvantage(is_night, observer_race) else 0
        passive_perception = 10 + perception_bonus - night_penalty
        is_dark = self._is_location_dark(observer_id)

        if observer.parent is not None:
            siblings = self.get_children(observer.parent)
            for sibling in siblings:
                if sibling.id == observer_id:
                    continue

                # Range check — objects at [0,0,0] are "same room" (always in range)
                dist = self._euclidean_distance(observer, sibling)
                if dist > 0.0:
                    effective_range = darkvision_range if is_dark else vision_range
                    if dist > effective_range:
                        continue

                # Stealth / hidden check
                stealth_dc = sibling.properties.get("stealth_dc")
                if stealth_dc is not None and passive_perception < int(stealth_dc):
                    continue

                visible_ids.add(sibling.id)

                # --- 3. Contents of non-closed siblings ---
                if not sibling.properties.get("closed", False):
                    for child in self.get_children(sibling.id):
                        stealth_dc_child = child.properties.get("stealth_dc")
                        if stealth_dc_child is not None and passive_perception < int(stealth_dc_child):
                            continue
                        visible_ids.add(child.id)

        # --- Build visible world ---
        visible_world = World(
            name=f"{self.name}_visible",
            max_id=self.max_id,
            delete_ids=[],
        )
        for obj_id in visible_ids:
            obj = self.objects.get(obj_id)
            if obj:
                visible_world.objects[obj_id] = obj.model_copy()

        return visible_world

    def model_dump_yaml(self) -> dict:
        """Convert to YAML-friendly dict."""
        return {
            "name": self.name,
            "max_id": self.max_id,
            "delete_ids": self.delete_ids,
            "objects": {obj_id: obj.model_dump_yaml() for obj_id, obj in self.objects.items()},
        }
