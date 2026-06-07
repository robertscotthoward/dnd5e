"""Procedural world generator — fills unseen coordinates on demand."""

import random
from typing import Optional

from src.backend.models.world import Location, Object, Size, World
from src.backend.world.bsp import BspPartitioner, Rect

# ---------------------------------------------------------------------------
# Biome constants
# ---------------------------------------------------------------------------

BIOME_GRASSLAND = "grassland"
BIOME_DUNGEON = "dungeon_stone"
BIOME_COBBLESTONE = "cobblestone"
BIOME_FOREST = "forest"
BIOME_CAVE = "cave"
BIOME_DESERT = "desert"
BIOME_ARCTIC = "arctic"
BIOME_UNDERGROUND = "underground"

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

# ---------------------------------------------------------------------------
# Tile color mapping
# Used by the frontend WorldMap to color each tile appropriately.
# ---------------------------------------------------------------------------

# tile_color values understood by the frontend:
#   "brown"      — road, ground, door, entrance, cobblestone
#   "orange"     — building, store, smithy, market, general_store, magic_shop,
#                  academy, manor, prison, black_market, festhall, temple
#   "green"      — inn, tavern, pub
#   "dark_green" — forest, park, vegetation
#   "blue"       — water, river, ocean, swamp, lake

TILE_COLOR_BY_TYPE: dict[str, str] = {
    # Ground / traversable surfaces
    "ground":          "brown",
    "floor":           "brown",
    "road":            "brown",
    "cobblestone":     "brown",
    "door":            "brown",
    "entrance":        "brown",
    "wall":            "brown",
    "path":            "brown",
    "plaza":           "brown",
    "courtyard":       "brown",
    "forum":           "brown",
    # Buildings / stores
    "building":        "orange",
    "store":           "orange",
    "general_store":   "orange",
    "magic_shop":      "orange",
    "smithy":          "orange",
    "market":          "orange",
    "black_market":    "orange",
    "festhall":        "orange",
    "temple":          "orange",
    "manor":           "orange",
    "academy":         "orange",
    "prison":          "orange",
    "citadel":         "orange",
    "library_fortress":"orange",
    "military_outpost":"orange",
    "dungeon":         "orange",
    "cave":            "orange",
    "cave_entrance":   "orange",
    "room":            "orange",
    "ruin":            "orange",
    # Inns / pubs
    "inn":             "green",
    "tavern":          "green",
    "pub":             "green",
    # Forest / vegetation
    "forest":          "dark_green",
    "park":            "dark_green",
    "tree":            "dark_green",
    "vegetation":      "dark_green",
    # Water
    "water":           "blue",
    "river":           "blue",
    "ocean":           "blue",
    "lake":            "blue",
    "swamp":           "blue",
    "pond":            "blue",
}

# Biome → default tile_color for ground tiles
_BIOME_TILE_COLOR: dict[str, str] = {
    BIOME_GRASSLAND:   "brown",
    BIOME_DUNGEON:     "brown",
    BIOME_COBBLESTONE: "brown",
    BIOME_FOREST:      "dark_green",
    BIOME_CAVE:        "brown",
    BIOME_DESERT:      "brown",
    BIOME_ARCTIC:      "brown",
    BIOME_UNDERGROUND: "brown",
}

# ---------------------------------------------------------------------------
# Large features that can be placed probabilistically in open terrain
# ---------------------------------------------------------------------------

_LARGE_FEATURES = ("forest", "ruin", "cave_entrance")
_FEATURE_PROBABILITY = 0.10

# Area cover types — a single object covering many LOS tiles
_AREA_COVER_TYPES = ("park", "forum", "road", "plaza", "courtyard")

# ---------------------------------------------------------------------------
# Building types spawned by BSP inside settlement parents
# ---------------------------------------------------------------------------

# (type, name_template, tile_color)
_SETTLEMENT_BUILDINGS: list[tuple[str, str, str]] = [
    ("inn",           "The {adj} {animal} Inn",  "green"),
    ("tavern",        "The {adj} {animal} Tavern","green"),
    ("general_store", "General Store",            "orange"),
    ("smithy",        "Smithy",                   "orange"),
    ("temple",        "Temple",                   "orange"),
    ("magic_shop",    "Sorcerous Wares",          "orange"),
    ("market",        "Market Stalls",            "orange"),
    ("manor",         "Manor House",              "orange"),
]

_ADJ = ["Golden", "Silver", "Iron", "Rusty", "Wandering", "Prancing", "Laughing", "Broken"]
_ANIMAL = ["Dragon", "Stag", "Wolf", "Bear", "Boar", "Raven", "Fox", "Ox"]


class WorldGenerator:
    """
    Procedural terrain generator that fills unseen coordinates on demand.

    Usage::

        gen = WorldGenerator(world, seed=42)
        new_objs = gen.fill(missing_coords, parent_id)
        new_obj = gen.fill_coordinate(coord, parent_id)
        children = gen.fill_children(parent_id)
        children = gen.fill_children_bsp(parent_id, player_pos, radius)
    """

    def __init__(self, world: World, seed: int) -> None:
        self.world = world
        self.rng = random.Random(seed)
        self._bsp = BspPartitioner(rng=random.Random(seed ^ 0xBEEF))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_biome(self, parent_id: int) -> str:
        """
        Walk the ancestor chain from parent_id upward and return the terrain
        type that best matches the enclosing region.
        """
        obj = self.world.get_object(parent_id)
        while obj is not None:
            biome = _TYPE_BIOME.get(obj.type)
            if biome:
                return biome
            if obj.name:
                name_lower = obj.name.lower()
                for keyword, biome in _TYPE_BIOME.items():
                    if keyword in name_lower:
                        return biome
            if obj.parent is None:
                break
            obj = self.world.get_object(obj.parent)
        return BIOME_GRASSLAND

    def tile_color_for(self, obj_type: str, biome: Optional[str] = None) -> str:
        """Return the canonical tile_color string for a given object type."""
        color = TILE_COLOR_BY_TYPE.get(obj_type)
        if color:
            return color
        if biome:
            return _BIOME_TILE_COLOR.get(biome, "brown")
        return "brown"

    def fill_coordinate(
        self,
        coord: tuple[float, float],
        parent_id: int,
    ) -> Optional[Object]:
        """
        Ensure a single (x, y) coordinate under parent_id has at least one object.

        Skip-if-occupied guard: if any non-mobile object already exists at this
        coordinate, returns None immediately.

        Returns the newly created Object, or None if the coordinate was already
        occupied by a fixed object.
        """
        x, y = float(coord[0]), float(coord[1])

        children = self.world.get_children(parent_id)
        for child in children:
            if child.location.x == x and child.location.y == y:
                if not child.properties.get("mobile", False):
                    return None

        biome = self.resolve_biome(parent_id)
        ground_name = _BIOME_GROUND_NAME.get(biome, "Ground")
        tile_color = _BIOME_TILE_COLOR.get(biome, "brown")
        return self._make_object(
            obj_type="ground",
            name=ground_name,
            parent_id=parent_id,
            x=x,
            y=y,
            properties={"tile_color": tile_color},
        )

    def fill_children(self, parent_id: int) -> list[Object]:
        """
        Populate the immediate children of a parent whose `generated` flag is False.

        For settlement-type parents (town, city) uses BSP placement of building
        shells.  For indoor parents (inn, room, dungeon) uses the perimeter-wall
        layout.  Sets `generated: true` on the parent when done.

        Returns newly created objects (empty list if already generated or missing).
        """
        parent = self.world.get_object(parent_id)
        if parent is None:
            return []
        if parent.properties.get("generated", False):
            return []

        # Settlement-type parents get BSP building placement
        if parent.type in ("town", "city", "region"):
            return self._fill_settlement(parent)

        # Default: interior perimeter-wall layout
        return self._fill_interior(parent)

    def fill_children_bsp(
        self,
        parent_id: int,
        player_pos: tuple[float, float],
        radius: float,
    ) -> list[Object]:
        """
        BSP-driven fill: place child buildings/objects within radius of player_pos,
        without exceeding the parent's boundaries.

        This is the primary trigger for lazy on-demand world expansion.  Unlike
        `fill_children`, which populates the entire parent, this only materialises
        the area within reach of the player, leaving the rest dark until approached.

        Args:
            parent_id:  ID of the enclosing parent object.
            player_pos: Player's (x, y) in the parent's local coordinate space.
            radius:     Maximum distance from the player in world feet.

        Returns:
            List of newly created Object instances.
        """
        parent = self.world.get_object(parent_id)
        if parent is None:
            return []

        # Derive floor area from parent size; default to 200×200 if unset
        floor_w = parent.size.width if parent.size.width >= 5 else 200.0
        floor_h = parent.size.length if parent.size.length >= 5 else 200.0
        area = Rect(0.0, 0.0, floor_w, floor_h)

        rects = self._bsp.partition(
            area=area,
            player_pos=player_pos,
            radius=radius,
            min_cell=(10.0, 10.0),
            max_depth=4,
        )

        occupied = self._fixed_coords_at_parent(parent_id)
        new_objects: list[Object] = []

        for rect in rects:
            cx = rect.x + rect.width / 2.0
            cy = rect.y + rect.height / 2.0
            cx = round(cx / 5.0) * 5.0
            cy = round(cy / 5.0) * 5.0
            key = (cx, cy)
            if key in occupied:
                continue

            # Decide what to place in this cell
            obj_type, name, tile_color = self._pick_feature_for_parent(parent)

            obj = self._make_object(
                obj_type=obj_type,
                name=name,
                parent_id=parent_id,
                x=cx,
                y=cy,
                properties={
                    "tile_color": tile_color,
                    "generated": False,
                    "size_w": rect.width,
                    "size_h": rect.height,
                },
                is_moveable=False,
            )
            new_objects.append(obj)
            occupied.add(key)

        return new_objects

    def fill(
        self,
        coords: list[tuple[float, float]],
        parent_id: int,
    ) -> list[Object]:
        """
        Populate empty tile coordinates under parent_id.

        For each (x, y) pair in *coords* that has no existing fixed child object at
        that position, creates at minimum a ground tile.  Also attempts
        large-feature placement once per 5×5 cluster (10 % chance).

        Mobile objects (mobile: true) do not block ground tile creation.

        Returns the list of newly created Object instances.
        """
        occupied = self._fixed_coords_at_parent(parent_id)
        biome = self.resolve_biome(parent_id)
        ground_name = _BIOME_GROUND_NAME.get(biome, "Ground")
        tile_color = _BIOME_TILE_COLOR.get(biome, "brown")

        new_objects: list[Object] = []

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
                feature_color = self.tile_color_for(feature_type, biome)
                for fx, fy in cluster_coords:
                    if (fx, fy) not in occupied and (fx, fy) not in placed_features:
                        feature = self._make_object(
                            obj_type=feature_type,
                            name=feature_type.replace("_", " ").title(),
                            parent_id=parent_id,
                            x=fx,
                            y=fy,
                            properties={
                                "generated": False,
                                "tile_color": feature_color,
                            },
                        )
                        new_objects.append(feature)
                        occupied.add((fx, fy))
                        placed_features.add((fx, fy))
                        break

            for x, y in cluster_coords:
                if (x, y) not in occupied:
                    ground = self._make_object(
                        obj_type="ground",
                        name=ground_name,
                        parent_id=parent_id,
                        x=x,
                        y=y,
                        properties={"tile_color": tile_color},
                    )
                    new_objects.append(ground)
                    occupied.add((x, y))

        return new_objects

    # fill_interior is an alias kept for backwards compatibility
    def fill_interior(self, parent_id: int) -> list[Object]:
        """Alias for fill_children — generates interior of an ungenerated parent."""
        return self.fill_children(parent_id)

    def find_ungenerated_parents_in_coords(
        self,
        coords: list[tuple[float, float]],
        parent_id: int,
    ) -> list[int]:
        """
        Return IDs of child objects at the given coordinates whose `generated`
        flag is False.  Used to trigger lazy fill_children calls.
        """
        result: list[int] = []
        children = self.world.get_children(parent_id)
        coord_set = {(float(c[0]), float(c[1])) for c in coords}
        for child in children:
            pos = (child.location.x, child.location.y)
            if pos in coord_set and child.properties.get("generated") is False:
                result.append(child.id)
        return result

    # ------------------------------------------------------------------
    # Private settlement / interior generators
    # ------------------------------------------------------------------

    def _fill_settlement(self, parent: Object) -> list[Object]:
        """
        Use BSP to place a full set of building shells across a settlement
        (town, city).  Only called once; sets `generated: true`.
        """
        floor_w = parent.size.width if parent.size.width >= 5 else 200.0
        floor_h = parent.size.length if parent.size.length >= 5 else 200.0
        area = Rect(0.0, 0.0, floor_w, floor_h)

        # Partition the whole settlement floor at once
        rects = self._bsp.partition(
            area=area,
            player_pos=(floor_w / 2.0, floor_h / 2.0),
            radius=max(floor_w, floor_h),  # no radius clipping for full fill
            min_cell=(10.0, 10.0),
            max_depth=4,
        )

        occupied = self._fixed_coords_at_parent(parent.id)
        new_objects: list[Object] = []

        for rect in rects:
            cx = round((rect.x + rect.width / 2.0) / 5.0) * 5.0
            cy = round((rect.y + rect.height / 2.0) / 5.0) * 5.0
            key = (cx, cy)
            if key in occupied:
                continue

            obj_type, name, tile_color = self._pick_feature_for_parent(parent)
            obj = self._make_object(
                obj_type=obj_type,
                name=name,
                parent_id=parent.id,
                x=cx,
                y=cy,
                properties={
                    "tile_color": tile_color,
                    "generated": False,
                    "size_w": rect.width,
                    "size_h": rect.height,
                },
                is_moveable=False,
            )
            new_objects.append(obj)
            occupied.add(key)

        parent.set_prop("generated", True)
        return new_objects

    def _fill_interior(self, parent: Object) -> list[Object]:
        """
        Populate an indoor parent (inn, room, dungeon) with a perimeter-wall
        layout: floor tiles, walls on the perimeter, and a door on the south face.
        """
        new_objects: list[Object] = []

        width = max(1, int(parent.size.width // 5)) if parent.size.width >= 5 else 3
        length = max(1, int(parent.size.length // 5)) if parent.size.length >= 5 else 3

        biome = self.resolve_biome(parent.id)
        floor_name = _BIOME_GROUND_NAME.get(biome, "Floor")
        floor_color = _BIOME_TILE_COLOR.get(biome, "brown")

        for row in range(length):
            for col in range(width):
                x = float(col * 5)
                y = float(row * 5)

                is_perimeter = (
                    row == 0 or row == length - 1
                    or col == 0 or col == width - 1
                )
                is_door = (row == 0 and col == width // 2)

                if is_door:
                    obj = self._make_object(
                        obj_type="door",
                        name="Door",
                        parent_id=parent.id,
                        x=x,
                        y=y,
                        is_moveable=True,
                        properties={"tile_color": "brown"},
                    )
                elif is_perimeter:
                    obj = self._make_object(
                        obj_type="wall",
                        name="Wall",
                        parent_id=parent.id,
                        x=x,
                        y=y,
                        properties={"tile_color": "brown"},
                    )
                else:
                    obj = self._make_object(
                        obj_type="floor",
                        name=floor_name,
                        parent_id=parent.id,
                        x=x,
                        y=y,
                        properties={"tile_color": floor_color},
                    )
                new_objects.append(obj)

        parent.set_prop("generated", True)
        return new_objects

    def _pick_feature_for_parent(
        self, parent: Object
    ) -> tuple[str, str, str]:
        """
        Return (obj_type, name, tile_color) for a child feature appropriate
        to the parent type.
        """
        parent_type = parent.type

        if parent_type in ("town", "city"):
            choice = self.rng.choice(_SETTLEMENT_BUILDINGS)
            obj_type, name_tmpl, color = choice
            name = name_tmpl.format(
                adj=self.rng.choice(_ADJ),
                animal=self.rng.choice(_ANIMAL),
            )
            return obj_type, name, color

        if parent_type == "region":
            # Regions get forests, roads, ruins at random
            feature_type = self.rng.choice(("forest", "road", "ruin", "cave_entrance"))
            color = self.tile_color_for(feature_type)
            return feature_type, feature_type.replace("_", " ").title(), color

        # Generic fallback: ground tile
        biome = self.resolve_biome(parent.id)
        ground_name = _BIOME_GROUND_NAME.get(biome, "Ground")
        color = _BIOME_TILE_COLOR.get(biome, "brown")
        return "ground", ground_name, color

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _coords_at_parent(self, parent_id: int) -> set[tuple[float, float]]:
        children = self.world.get_children(parent_id)
        return {(child.location.x, child.location.y) for child in children}

    def _fixed_coords_at_parent(self, parent_id: int) -> set[tuple[float, float]]:
        children = self.world.get_children(parent_id)
        return {
            (child.location.x, child.location.y)
            for child in children
            if not child.properties.get("mobile", False)
        }

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
