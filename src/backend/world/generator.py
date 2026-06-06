"""Procedural world generator — fills unseen coordinates on demand."""

import random
from typing import Optional

from src.backend.models.world import Location, Object, Size, World

# Biome types returned by resolve_biome
BIOME_GRASSLAND = "grassland"
BIOME_DUNGEON = "dungeon_stone"
BIOME_COBBLESTONE = "cobblestone"
BIOME_FOREST = "forest"
BIOME_CAVE = "cave"
BIOME_DESERT = "desert"
BIOME_ARCTIC = "arctic"
BIOME_UNDERGROUND = "underground"

# Object types that map to a specific biome
_TYPE_BIOME: dict[str, str] = {
    "dungeon": BIOME_DUNGEON,
    "cave": BIOME_CAVE,
    "cave_entrance": BIOME_CAVE,
    "underground": BIOME_UNDERGROUND,
    "forest": BIOME_FOREST,
    "desert": BIOME_DESERT,
    "arctic": BIOME_ARCTIC,
    "town": BIOME_COBBLESTONE,
    "city": BIOME_COBBLESTONE,
    "inn": BIOME_COBBLESTONE,
    "room": BIOME_COBBLESTONE,
}

# Ground tile names per biome
_BIOME_GROUND_NAME: dict[str, str] = {
    BIOME_GRASSLAND: "Grassland",
    BIOME_DUNGEON: "Stone Floor",
    BIOME_COBBLESTONE: "Cobblestone",
    BIOME_FOREST: "Forest Floor",
    BIOME_CAVE: "Cave Floor",
    BIOME_DESERT: "Sand",
    BIOME_ARCTIC: "Ice",
    BIOME_UNDERGROUND: "Underground Floor",
}

# Large feature types that can be placed probabilistically
_LARGE_FEATURES = ("forest", "ruin", "cave_entrance")

# Probability (0–1) that a 5×5 cluster spawns a large feature
_FEATURE_PROBABILITY = 0.10


class WorldGenerator:
    """
    Procedural terrain generator that fills unseen coordinates on demand.

    Usage::

        gen = WorldGenerator(world, seed=42)
        new_objs = gen.fill(missing_coords, parent_id)
    """

    def __init__(self, world: World, seed: int) -> None:
        self.world = world
        self.rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_biome(self, parent_id: int) -> str:
        """
        Walk the ancestor chain from parent_id upward and return the terrain
        type that best matches the enclosing region.

        Checks the object's own type first, then its name (lower-cased) for
        known keywords. Defaults to grassland when no match is found.
        """
        obj = self.world.get_object(parent_id)
        while obj is not None:
            # Exact type match
            biome = _TYPE_BIOME.get(obj.type)
            if biome:
                return biome
            # Name keyword match
            if obj.name:
                name_lower = obj.name.lower()
                for keyword, biome in _TYPE_BIOME.items():
                    if keyword in name_lower:
                        return biome
            # Walk up
            if obj.parent is None:
                break
            obj = self.world.get_object(obj.parent)
        return BIOME_GRASSLAND

    def fill(
        self,
        coords: list[tuple[float, float]],
        parent_id: int,
    ) -> list[Object]:
        """
        Populate empty tile coordinates under parent_id.

        For each (x, y) pair in *coords* that has no existing child object at
        that position, creates at minimum a ground tile.  Also attempts
        large-feature placement once per 5×5 cluster (10 % chance).

        Returns the list of newly created Object instances.
        """
        occupied = self._coords_at_parent(parent_id)
        biome = self.resolve_biome(parent_id)
        ground_name = _BIOME_GROUND_NAME.get(biome, "Ground")

        new_objects: list[Object] = []

        # Deduplicate input coords while preserving order
        seen_input: set[tuple[float, float]] = set()
        unique_coords: list[tuple[float, float]] = []
        for c in coords:
            key = (float(c[0]), float(c[1]))
            if key not in seen_input:
                seen_input.add(key)
                unique_coords.append(key)

        # Cluster coords into 5×5 buckets for large-feature roll
        clusters: dict[tuple[int, int], list[tuple[float, float]]] = {}
        for x, y in unique_coords:
            cluster_key = (int(x // 25), int(y // 25))
            clusters.setdefault(cluster_key, []).append((x, y))

        placed_features: set[tuple[float, float]] = set()

        for cluster_coords in clusters.values():
            # Large-feature roll: one attempt per cluster
            if self.rng.random() < _FEATURE_PROBABILITY:
                feature_type = self.rng.choice(_LARGE_FEATURES)
                # Place the feature at the first available coord in this cluster
                for fx, fy in cluster_coords:
                    if (fx, fy) not in occupied and (fx, fy) not in placed_features:
                        feature = self._make_object(
                            obj_type=feature_type,
                            name=feature_type.replace("_", " ").title(),
                            parent_id=parent_id,
                            x=fx,
                            y=fy,
                            properties={"generated": False},
                        )
                        new_objects.append(feature)
                        occupied.add((fx, fy))
                        placed_features.add((fx, fy))
                        break

            # Ground tiles for every remaining empty coord in this cluster
            for x, y in cluster_coords:
                if (x, y) not in occupied:
                    ground = self._make_object(
                        obj_type="ground",
                        name=ground_name,
                        parent_id=parent_id,
                        x=x,
                        y=y,
                    )
                    new_objects.append(ground)
                    occupied.add((x, y))

        return new_objects

    def fill_interior(self, parent_id: int) -> list[Object]:
        """
        Generate children for a parent object whose properties.generated is False.

        Creates a minimal interior layout: floor tiles, perimeter walls, and
        a door on the south face.  Sets properties.generated = True on parent
        when done.

        Returns newly created objects (empty list if parent already generated
        or does not exist).
        """
        parent = self.world.get_object(parent_id)
        if parent is None:
            return []
        if parent.properties.get("generated", True):
            return []

        new_objects: list[Object] = []

        # Determine interior size (default 3×3 tiles of 5 ft each)
        width = max(1, int(parent.size.width // 5)) if parent.size.width >= 5 else 3
        length = max(1, int(parent.size.length // 5)) if parent.size.length >= 5 else 3

        biome = self.resolve_biome(parent_id)
        floor_name = _BIOME_GROUND_NAME.get(biome, "Floor")

        for row in range(length):
            for col in range(width):
                x = float(col * 5)
                y = float(row * 5)

                is_perimeter = (
                    row == 0 or row == length - 1
                    or col == 0 or col == width - 1
                )

                # Door in the middle of the south wall
                is_door = (
                    row == 0
                    and col == width // 2
                )

                if is_door:
                    obj = self._make_object(
                        obj_type="door",
                        name="Door",
                        parent_id=parent_id,
                        x=x,
                        y=y,
                        is_moveable=True,
                    )
                elif is_perimeter:
                    obj = self._make_object(
                        obj_type="wall",
                        name="Wall",
                        parent_id=parent_id,
                        x=x,
                        y=y,
                    )
                else:
                    obj = self._make_object(
                        obj_type="floor",
                        name=floor_name,
                        parent_id=parent_id,
                        x=x,
                        y=y,
                    )
                new_objects.append(obj)

        # Mark parent as generated
        parent.set_prop("generated", True)

        return new_objects

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _coords_at_parent(self, parent_id: int) -> set[tuple[float, float]]:
        """Return the set of (x, y) positions already occupied by children."""
        children = self.world.get_children(parent_id)
        return {(child.location.x, child.location.y) for child in children}

    def _make_object(
        self,
        obj_type: str,
        name: str,
        parent_id: int,
        x: float,
        y: float,
        z: float = 0.0,
        properties: Optional[dict] = None,
        is_moveable: bool = False,
    ) -> Object:
        """Create, register, and return a new world object."""
        obj = Object(
            id=self.world.next_id(),
            parent=parent_id,
            type=obj_type,
            name=name,
            location=Location(x=x, y=y, z=z),
            size=Size(),
            is_moveable=is_moveable,
            properties=properties or {},
        )
        self.world.add_object(obj)
        return obj
