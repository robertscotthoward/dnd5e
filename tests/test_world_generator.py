"""Tests for WorldGenerator — procedural terrain and object population."""

import pytest
from unittest.mock import patch

from src.backend.models.world import Location, Object, Size, World
from src.backend.world.generator import (
    BIOME_CAVE,
    BIOME_COBBLESTONE,
    BIOME_DUNGEON,
    BIOME_FOREST,
    BIOME_GRASSLAND,
    WorldGenerator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world(name: str = "Test") -> World:
    """Return a minimal World with a single region container (id=1)."""
    world = World(name=name)
    region = Object(
        id=world.next_id(),  # id=1
        parent=None,
        type="region",
        name="Open Plains",
        location=Location(),
        size=Size(),
        is_moveable=False,
    )
    world.add_object(region)
    return world


def _make_dungeon_world() -> World:
    """Return a World whose root is a dungeon container."""
    world = World(name="DungeonTest")
    dungeon = Object(
        id=world.next_id(),  # id=1
        parent=None,
        type="dungeon",
        name="Dark Dungeon",
        location=Location(),
        size=Size(),
        is_moveable=False,
    )
    world.add_object(dungeon)
    return world


def _grid_coords(n: int = 4) -> list[tuple[float, float]]:
    """Return a simple n×n grid of 5-ft coordinates."""
    return [(float(x * 5), float(y * 5)) for x in range(n) for y in range(n)]


# ---------------------------------------------------------------------------
# resolve_biome
# ---------------------------------------------------------------------------

def test_resolve_biome_grassland_default():
    """Region with no recognised type/name defaults to grassland."""
    world = _make_world()
    gen = WorldGenerator(world, seed=1)
    biome = gen.resolve_biome(1)
    assert biome == BIOME_GRASSLAND


def test_resolve_biome_dungeon_type():
    """A dungeon-type parent resolves to dungeon_stone biome."""
    world = _make_dungeon_world()
    gen = WorldGenerator(world, seed=1)
    biome = gen.resolve_biome(1)
    assert biome == BIOME_DUNGEON


def test_resolve_biome_town_cobblestone():
    """A town-type parent resolves to cobblestone."""
    world = World(name="TownTest")
    town = Object(
        id=world.next_id(),
        parent=None,
        type="town",
        name="Riverdale",
        location=Location(),
        size=Size(),
        is_moveable=False,
    )
    world.add_object(town)
    gen = WorldGenerator(world, seed=1)
    assert gen.resolve_biome(town.id) == BIOME_COBBLESTONE


def test_resolve_biome_name_keyword_forest():
    """An object whose name contains 'forest' resolves to forest biome."""
    world = World(name="ForestTest")
    region = Object(
        id=world.next_id(),
        parent=None,
        type="region",
        name="Dense Forest Valley",
        location=Location(),
        size=Size(),
        is_moveable=False,
    )
    world.add_object(region)
    gen = WorldGenerator(world, seed=1)
    assert gen.resolve_biome(region.id) == BIOME_FOREST


def test_resolve_biome_walks_ancestors():
    """resolve_biome walks up the ancestor chain to find the biome."""
    world = World(name="AncestorTest")
    # Root is a dungeon
    dungeon = Object(
        id=world.next_id(),  # 1
        parent=None,
        type="dungeon",
        name="Dungeon",
        location=Location(),
        size=Size(),
        is_moveable=False,
    )
    world.add_object(dungeon)
    # A generic room inside the dungeon
    room = Object(
        id=world.next_id(),  # 2
        parent=dungeon.id,
        type="room",
        name="Storage Room",
        location=Location(),
        size=Size(),
        is_moveable=False,
    )
    world.add_object(room)
    gen = WorldGenerator(world, seed=1)
    # room type is 'room' → cobblestone, but that is a closer ancestor match
    assert gen.resolve_biome(room.id) == BIOME_COBBLESTONE


# ---------------------------------------------------------------------------
# fill — ground tile creation
# ---------------------------------------------------------------------------

def test_fill_creates_ground_for_empty_coords():
    """fill() creates at least one ground object for each empty coordinate."""
    world = _make_world()
    gen = WorldGenerator(world, seed=0)
    coords = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)]
    new_objs = gen.fill(coords, parent_id=1)
    # At minimum every coord gets a ground tile; large features may replace one
    coord_set = {(o.location.x, o.location.y) for o in new_objs}
    for c in coords:
        assert c in coord_set, f"Missing tile at {c}"


def test_fill_returns_empty_for_occupied_coords():
    """fill() returns no new objects when every coord is already occupied."""
    world = _make_world()
    gen = WorldGenerator(world, seed=1)
    coords = [(0.0, 0.0), (5.0, 0.0)]
    # Pre-populate those coords
    gen.fill(coords, parent_id=1)
    # Second call on the same coords must return nothing
    result = gen.fill(coords, parent_id=1)
    assert result == [], "Expected empty list for already-occupied coords"


def test_fill_does_not_duplicate_existing_objects():
    """Calling fill() twice on overlapping coords never creates duplicates."""
    world = _make_world()
    gen = WorldGenerator(world, seed=2)
    coords = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)]
    gen.fill(coords, parent_id=1)
    children_after_first = len(world.get_children(1))
    gen.fill(coords, parent_id=1)
    children_after_second = len(world.get_children(1))
    assert children_after_first == children_after_second


def test_fill_handles_negative_coords():
    """fill() handles negative (x, y) coordinates without error."""
    world = _make_world()
    gen = WorldGenerator(world, seed=3)
    coords = [(-5.0, -5.0), (-10.0, 0.0), (0.0, -10.0)]
    new_objs = gen.fill(coords, parent_id=1)
    assert len(new_objs) >= len(coords)


def test_fill_ground_tile_attributes():
    """Ground tiles produced by fill() have expected type and flags."""
    world = _make_world()
    # Force RNG so no large feature is placed (mock random to return 0.99)
    gen = WorldGenerator(world, seed=99)
    with patch.object(gen.rng, "random", return_value=0.99):
        new_objs = gen.fill([(0.0, 0.0)], parent_id=1)
    assert len(new_objs) == 1
    ground = new_objs[0]
    assert ground.type == "ground"
    assert ground.is_moveable is False
    assert ground.parent == 1


# ---------------------------------------------------------------------------
# fill — large feature placement
# ---------------------------------------------------------------------------

def test_fill_large_feature_placed_when_rng_forces_it():
    """When RNG is forced to return a low value, a large feature is placed."""
    world = _make_world()
    gen = WorldGenerator(world, seed=7)
    coords = _grid_coords(5)  # 25 tiles across multiple clusters
    feature_types = {"forest", "ruin", "cave_entrance"}
    with patch.object(gen.rng, "random", return_value=0.0):
        new_objs = gen.fill(coords, parent_id=1)
    features = [o for o in new_objs if o.type in feature_types]
    assert len(features) > 0, "Expected at least one large feature"


def test_fill_large_feature_has_generated_false():
    """Large features created by fill() have properties.generated == False."""
    world = _make_world()
    gen = WorldGenerator(world, seed=8)
    feature_types = {"forest", "ruin", "cave_entrance"}
    with patch.object(gen.rng, "random", return_value=0.0):
        new_objs = gen.fill(_grid_coords(5), parent_id=1)
    for obj in new_objs:
        if obj.type in feature_types:
            assert obj.properties.get("generated") is False


def test_fill_no_feature_when_rng_suppresses():
    """When RNG returns high value, no large feature is placed."""
    world = _make_world()
    gen = WorldGenerator(world, seed=9)
    feature_types = {"forest", "ruin", "cave_entrance"}
    with patch.object(gen.rng, "random", return_value=1.0):
        new_objs = gen.fill([(0.0, 0.0), (5.0, 0.0)], parent_id=1)
    assert all(o.type not in feature_types for o in new_objs)


# ---------------------------------------------------------------------------
# fill_interior
# ---------------------------------------------------------------------------

def test_fill_interior_generates_children():
    """fill_interior() creates floor/wall/door children for an ungenerated feature."""
    world = _make_world()
    # Create a large feature parent with generated=False
    feature = Object(
        id=world.next_id(),  # 2
        parent=1,
        type="ruin",
        name="Ancient Ruin",
        location=Location(x=0, y=0, z=0),
        size=Size(length=15.0, width=15.0, height=10.0),
        is_moveable=False,
        properties={"generated": False},
    )
    world.add_object(feature)

    gen = WorldGenerator(world, seed=10)
    new_objs = gen.fill_interior(feature.id)
    assert len(new_objs) > 0
    types = {o.type for o in new_objs}
    assert types & {"floor", "wall", "door"}, f"Expected interior types, got {types}"


def test_fill_interior_sets_generated_true():
    """fill_interior() marks the parent object's generated property as True."""
    world = _make_world()
    feature = Object(
        id=world.next_id(),
        parent=1,
        type="cave_entrance",
        name="Dark Cave",
        location=Location(x=0, y=0, z=0),
        size=Size(length=15.0, width=15.0, height=5.0),
        is_moveable=False,
        properties={"generated": False},
    )
    world.add_object(feature)

    gen = WorldGenerator(world, seed=11)
    gen.fill_interior(feature.id)
    parent_obj = world.get_object(feature.id)
    assert parent_obj.properties.get("generated") is True


def test_fill_interior_no_op_when_already_generated():
    """fill_interior() returns empty list if parent is already generated."""
    world = _make_world()
    feature = Object(
        id=world.next_id(),
        parent=1,
        type="forest",
        name="Forest Grove",
        location=Location(x=0, y=0, z=0),
        size=Size(length=15.0, width=15.0, height=0.0),
        is_moveable=False,
        properties={"generated": True},
    )
    world.add_object(feature)
    gen = WorldGenerator(world, seed=12)
    result = gen.fill_interior(feature.id)
    assert result == []


def test_fill_interior_missing_parent_returns_empty():
    """fill_interior() returns empty list for a non-existent parent id."""
    world = _make_world()
    gen = WorldGenerator(world, seed=13)
    result = gen.fill_interior(9999)
    assert result == []


# ---------------------------------------------------------------------------
# _coords_at_parent
# ---------------------------------------------------------------------------

def test_coords_at_parent_reflects_children():
    """_coords_at_parent() returns positions of all direct children."""
    world = _make_world()
    gen = WorldGenerator(world, seed=14)
    gen.fill([(0.0, 0.0), (5.0, 0.0)], parent_id=1)
    occupied = gen._coords_at_parent(1)
    assert (0.0, 0.0) in occupied
    assert (5.0, 0.0) in occupied


def test_coords_at_parent_empty_when_no_children():
    """_coords_at_parent() returns empty set when parent has no children."""
    world = _make_world()
    gen = WorldGenerator(world, seed=15)
    occupied = gen._coords_at_parent(1)
    assert occupied == set()


# ---------------------------------------------------------------------------
# Phase 17 — fill_coordinate (skip-if-occupied, mobile exemption)
# ---------------------------------------------------------------------------

def test_fill_coordinate_creates_ground_on_empty_tile():
    """fill_coordinate returns a ground object for an empty coordinate."""
    world = _make_world()
    gen = WorldGenerator(world, seed=20)
    obj = gen.fill_coordinate((5.0, 10.0), parent_id=1)
    assert obj is not None
    assert obj.type == "ground"
    assert obj.location.x == 5.0
    assert obj.location.y == 10.0
    assert obj.parent == 1


def test_fill_coordinate_skips_occupied_tile():
    """fill_coordinate returns None when a fixed object already occupies the coord."""
    world = _make_world()
    gen = WorldGenerator(world, seed=21)
    # Place a fixed object manually
    fixed = Object(
        id=world.next_id(),
        parent=1,
        type="wall",
        name="Wall",
        location=Location(x=0.0, y=0.0),
        size=Size(),
        is_moveable=False,
    )
    world.add_object(fixed)
    result = gen.fill_coordinate((0.0, 0.0), parent_id=1)
    assert result is None


def test_fill_coordinate_does_not_skip_mobile_objects():
    """fill_coordinate still generates a ground tile when only a mobile object is at the coord."""
    world = _make_world()
    gen = WorldGenerator(world, seed=22)
    # Place a mobile NPC
    npc = Object(
        id=world.next_id(),
        parent=1,
        type="NPC",
        name="Wanderer",
        location=Location(x=5.0, y=5.0),
        size=Size(),
        is_moveable=True,
        properties={"mobile": True},
    )
    world.add_object(npc)
    # Should still create a ground tile at that coord
    result = gen.fill_coordinate((5.0, 5.0), parent_id=1)
    assert result is not None
    assert result.type == "ground"


def test_fill_coordinate_idempotent_on_second_call():
    """Calling fill_coordinate twice on the same coord produces only one object."""
    world = _make_world()
    gen = WorldGenerator(world, seed=23)
    first = gen.fill_coordinate((0.0, 0.0), parent_id=1)
    assert first is not None
    second = gen.fill_coordinate((0.0, 0.0), parent_id=1)
    assert second is None
    # Only one ground object should exist at this coord
    children_at_coord = [
        c for c in world.get_children(1)
        if c.location.x == 0.0 and c.location.y == 0.0 and not c.properties.get("mobile")
    ]
    assert len(children_at_coord) == 1


# ---------------------------------------------------------------------------
# Phase 17 — fill_children (lazy interior generation)
# ---------------------------------------------------------------------------

def test_fill_children_creates_interior_layout():
    """fill_children populates wall/floor/door children for an ungenerated parent."""
    world = _make_world()
    feature = Object(
        id=world.next_id(),
        parent=1,
        type="ruin",
        name="Old Keep",
        location=Location(x=0, y=0),
        size=Size(length=15.0, width=15.0, height=10.0),
        is_moveable=False,
        properties={"generated": False},
    )
    world.add_object(feature)
    gen = WorldGenerator(world, seed=30)
    children = gen.fill_children(feature.id)
    assert len(children) > 0
    types = {c.type for c in children}
    assert "door" in types
    assert "wall" in types


def test_fill_children_marks_parent_generated():
    """fill_children sets generated=True on the parent after filling."""
    world = _make_world()
    feature = Object(
        id=world.next_id(),
        parent=1,
        type="cave_entrance",
        name="Dark Cave",
        location=Location(x=0, y=0),
        size=Size(length=15.0, width=15.0, height=5.0),
        is_moveable=False,
        properties={"generated": False},
    )
    world.add_object(feature)
    gen = WorldGenerator(world, seed=31)
    gen.fill_children(feature.id)
    assert world.get_object(feature.id).properties.get("generated") is True


def test_fill_children_idempotent_when_already_generated():
    """fill_children returns empty list if parent is already generated."""
    world = _make_world()
    feature = Object(
        id=world.next_id(),
        parent=1,
        type="forest",
        name="Forest",
        location=Location(x=0, y=0),
        size=Size(length=15.0, width=15.0),
        is_moveable=False,
        properties={"generated": True},
    )
    world.add_object(feature)
    gen = WorldGenerator(world, seed=32)
    result = gen.fill_children(feature.id)
    assert result == []


def test_fill_children_does_not_duplicate_on_second_call():
    """Calling fill_children twice creates no duplicate objects."""
    world = _make_world()
    feature = Object(
        id=world.next_id(),
        parent=1,
        type="ruin",
        name="Ruin",
        location=Location(x=0, y=0),
        size=Size(length=15.0, width=15.0, height=5.0),
        is_moveable=False,
        properties={"generated": False},
    )
    world.add_object(feature)
    gen = WorldGenerator(world, seed=33)
    first_pass = gen.fill_children(feature.id)
    count_after_first = len(world.get_children(feature.id))
    second_pass = gen.fill_children(feature.id)
    assert second_pass == []
    assert len(world.get_children(feature.id)) == count_after_first


# ---------------------------------------------------------------------------
# Phase 17 — find_ungenerated_parents_in_coords
# ---------------------------------------------------------------------------

def test_find_ungenerated_parents_in_coords_finds_match():
    """Returns IDs of child features whose generated flag is False at given coords."""
    world = _make_world()
    shell = Object(
        id=world.next_id(),
        parent=1,
        type="forest",
        name="Forest Shell",
        location=Location(x=10.0, y=10.0),
        size=Size(length=15.0, width=15.0),
        is_moveable=False,
        properties={"generated": False},
    )
    world.add_object(shell)
    gen = WorldGenerator(world, seed=40)
    result = gen.find_ungenerated_parents_in_coords([(10.0, 10.0)], parent_id=1)
    assert shell.id in result


def test_find_ungenerated_parents_skips_already_generated():
    """Does not return IDs for features that are already generated."""
    world = _make_world()
    shell = Object(
        id=world.next_id(),
        parent=1,
        type="forest",
        name="Forest",
        location=Location(x=5.0, y=5.0),
        size=Size(length=15.0, width=15.0),
        is_moveable=False,
        properties={"generated": True},
    )
    world.add_object(shell)
    gen = WorldGenerator(world, seed=41)
    result = gen.find_ungenerated_parents_in_coords([(5.0, 5.0)], parent_id=1)
    assert result == []


def test_find_ungenerated_parents_no_match():
    """Returns empty list when no features exist at the given coords."""
    world = _make_world()
    gen = WorldGenerator(world, seed=42)
    result = gen.find_ungenerated_parents_in_coords([(100.0, 200.0)], parent_id=1)
    assert result == []


# ---------------------------------------------------------------------------
# Phase 17 — mobile object exemption in fill()
# ---------------------------------------------------------------------------

def test_fill_ignores_mobile_objects_in_occupied_check():
    """fill() places a ground tile even when only mobile objects occupy the coord."""
    world = _make_world()
    # Place a mobile NPC at a coord
    npc = Object(
        id=world.next_id(),
        parent=1,
        type="NPC",
        name="Wanderer",
        location=Location(x=0.0, y=0.0),
        size=Size(),
        is_moveable=True,
        properties={"mobile": True},
    )
    world.add_object(npc)
    gen = WorldGenerator(world, seed=50)
    from unittest.mock import patch
    with patch.object(gen.rng, "random", return_value=1.0):  # suppress large features
        new_objs = gen.fill([(0.0, 0.0)], parent_id=1)
    assert len(new_objs) == 1
    assert new_objs[0].type == "ground"


def test_fill_skips_coord_with_existing_fixed_object():
    """fill() does not create a new tile when a fixed object already exists."""
    world = _make_world()
    fixed = Object(
        id=world.next_id(),
        parent=1,
        type="wall",
        name="Wall",
        location=Location(x=0.0, y=0.0),
        size=Size(),
        is_moveable=False,
    )
    world.add_object(fixed)
    gen = WorldGenerator(world, seed=51)
    from unittest.mock import patch
    with patch.object(gen.rng, "random", return_value=1.0):
        new_objs = gen.fill([(0.0, 0.0)], parent_id=1)
    assert new_objs == []


# ---------------------------------------------------------------------------
# Phase 17 — fill_interior alias
# ---------------------------------------------------------------------------

def test_fill_interior_is_alias_for_fill_children():
    """fill_interior and fill_children produce identical results."""
    def _make_feature(world):
        f = Object(
            id=world.next_id(),
            parent=1,
            type="ruin",
            name="Ruin",
            location=Location(x=0, y=0),
            size=Size(length=15.0, width=15.0, height=5.0),
            is_moveable=False,
            properties={"generated": False},
        )
        world.add_object(f)
        return f

    world_a = _make_world()
    feature_a = _make_feature(world_a)
    gen_a = WorldGenerator(world_a, seed=60)
    result_a = gen_a.fill_interior(feature_a.id)

    world_b = _make_world()
    feature_b = _make_feature(world_b)
    gen_b = WorldGenerator(world_b, seed=60)
    result_b = gen_b.fill_children(feature_b.id)

    assert len(result_a) == len(result_b)
    types_a = sorted(o.type for o in result_a)
    types_b = sorted(o.type for o in result_b)
    assert types_a == types_b
