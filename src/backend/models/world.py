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

    def get_visible_world(self, observer_id: int) -> "World":
        """
        Get a subset of the world visible from the observer's location.

        Visibility rules:
        - All ancestors are visible
        - Siblings and their immediate containers are visible
        - Objects at the same location level are visible
        - Contents of closed containers are not visible
        """
        observer = self.objects.get(observer_id)
        if not observer:
            return World(name=f"{self.name}_visible")

        visible_ids: set[int] = {observer_id}

        # Add all ancestors
        for ancestor in self.get_ancestors(observer_id):
            visible_ids.add(ancestor.id)

        # Add siblings (same parent)
        if observer.parent is not None:
            siblings = self.get_children(observer.parent)
            for sibling in siblings:
                visible_ids.add(sibling.id)

        # Create visible world
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
