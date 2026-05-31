"""Tests for get_visible_world / get_sub_world visibility logic."""

import pytest

from src.backend.models.world import Object, World, Location


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _world(name: str = "Test") -> World:
    return World(name=name)


def _add(world: World, obj_id: int, parent: int | None, obj_type: str = "room",
         loc: list[float] | None = None, **props) -> Object:
    obj = Object(
        id=obj_id,
        parent=parent,
        type=obj_type,
        name=f"{obj_type}_{obj_id}",
        location=Location.from_list(loc) if loc else Location(),
        properties=props,
    )
    world.objects[obj_id] = obj
    world.max_id = max(world.max_id, obj_id)
    return obj


# ---------------------------------------------------------------------------
# _is_location_dark
# ---------------------------------------------------------------------------

class TestIsLocationDark:
    def test_unlit_world_is_not_dark(self):
        w = _world()
        root = _add(w, 1, None, "planet")
        room = _add(w, 2, 1, "room")
        pc = _add(w, 3, 2, "PC")
        assert w._is_location_dark(3) is False

    def test_dark_room(self):
        w = _world()
        root = _add(w, 1, None, "planet")
        room = _add(w, 2, 1, "room", light="dark")
        pc = _add(w, 3, 2, "PC")
        assert w._is_location_dark(3) is True

    def test_lit_room(self):
        w = _world()
        root = _add(w, 1, None, "planet")
        room = _add(w, 2, 1, "room", light="bright")
        pc = _add(w, 3, 2, "PC")
        assert w._is_location_dark(3) is False

    def test_nearest_ancestor_wins(self):
        """Inner room light state overrides outer."""
        w = _world()
        outer = _add(w, 1, None, "dungeon", light="dark")
        inner = _add(w, 2, 1, "room", light="bright")
        pc = _add(w, 3, 2, "PC")
        assert w._is_location_dark(3) is False

    def test_no_parent_returns_false(self):
        w = _world()
        root = _add(w, 1, None, "system")
        assert w._is_location_dark(1) is False


# ---------------------------------------------------------------------------
# Ancestors always visible
# ---------------------------------------------------------------------------

class TestAncestorsAlwaysVisible:
    def test_ancestors_included(self):
        w = _world()
        _add(w, 1, None, "planet")
        _add(w, 2, 1, "continent")
        _add(w, 3, 2, "town")
        pc = _add(w, 4, 3, "PC")
        vis = w.get_visible_world(4)
        assert 1 in vis.objects
        assert 2 in vis.objects
        assert 3 in vis.objects
        assert 4 in vis.objects

    def test_observer_always_visible(self):
        w = _world()
        _add(w, 1, None, "planet")
        pc = _add(w, 2, 1, "PC")
        vis = w.get_visible_world(2)
        assert 2 in vis.objects

    def test_unknown_observer_returns_empty(self):
        w = _world()
        vis = w.get_visible_world(999)
        assert len(vis.objects) == 0


# ---------------------------------------------------------------------------
# Range filtering (lit room)
# ---------------------------------------------------------------------------

class TestRangeFiltering:
    def _setup_room(self) -> tuple[World, Object, Object]:
        """Room + observer at origin; returns world, room, observer."""
        w = _world()
        _add(w, 1, None, "planet")
        room = _add(w, 2, 1, "room")
        pc = _add(w, 3, 2, "PC", loc=[0.0, 0.0, 0.0])
        return w, room, pc

    def test_sibling_within_range_visible(self):
        w, room, pc = self._setup_room()
        _add(w, 4, 2, "NPC", loc=[30.0, 0.0, 0.0])
        vis = w.get_visible_world(3, vision_range=60.0)
        assert 4 in vis.objects

    def test_sibling_beyond_range_not_visible(self):
        w, room, pc = self._setup_room()
        _add(w, 4, 2, "NPC", loc=[90.0, 0.0, 0.0])
        vis = w.get_visible_world(3, vision_range=60.0)
        assert 4 not in vis.objects

    def test_sibling_exactly_at_range_visible(self):
        w, room, pc = self._setup_room()
        _add(w, 4, 2, "NPC", loc=[60.0, 0.0, 0.0])
        vis = w.get_visible_world(3, vision_range=60.0)
        assert 4 in vis.objects

    def test_same_position_always_visible(self):
        """Two objects at [0,0,0] — distance is 0, always visible regardless of range."""
        w, room, pc = self._setup_room()
        _add(w, 4, 2, "NPC", loc=[0.0, 0.0, 0.0])
        vis = w.get_visible_world(3, vision_range=0.0)
        assert 4 in vis.objects


# ---------------------------------------------------------------------------
# Dark / darkvision filtering
# ---------------------------------------------------------------------------

class TestDarkVision:
    def _dark_room(self) -> tuple[World, Object, Object]:
        w = _world()
        _add(w, 1, None, "planet")
        room = _add(w, 2, 1, "room", light="dark")
        pc = _add(w, 3, 2, "PC", loc=[0.0, 0.0, 0.0])
        return w, room, pc

    def test_dark_room_no_darkvision_blocks_ranged_target(self):
        w, room, pc = self._dark_room()
        _add(w, 4, 2, "NPC", loc=[30.0, 0.0, 0.0])
        vis = w.get_visible_world(3, vision_range=60.0, darkvision_range=0.0)
        assert 4 not in vis.objects

    def test_dark_room_with_darkvision_sees_within_range(self):
        w, room, pc = self._dark_room()
        _add(w, 4, 2, "NPC", loc=[30.0, 0.0, 0.0])
        vis = w.get_visible_world(3, vision_range=60.0, darkvision_range=60.0)
        assert 4 in vis.objects

    def test_dark_room_darkvision_limited_by_range(self):
        w, room, pc = self._dark_room()
        _add(w, 4, 2, "NPC", loc=[70.0, 0.0, 0.0])
        vis = w.get_visible_world(3, vision_range=60.0, darkvision_range=60.0)
        assert 4 not in vis.objects

    def test_dark_room_same_position_always_visible(self):
        w, room, pc = self._dark_room()
        _add(w, 4, 2, "NPC", loc=[0.0, 0.0, 0.0])
        vis = w.get_visible_world(3, vision_range=60.0, darkvision_range=0.0)
        assert 4 in vis.objects


# ---------------------------------------------------------------------------
# Stealth / perception filtering
# ---------------------------------------------------------------------------

class TestStealthFiltering:
    def _lit_room(self) -> tuple[World, Object, Object]:
        w = _world()
        _add(w, 1, None, "planet")
        room = _add(w, 2, 1, "room", light="bright")
        pc = _add(w, 3, 2, "PC", loc=[0.0, 0.0, 0.0])
        return w, room, pc

    def test_hidden_object_below_passive_perception_not_visible(self):
        w, room, pc = self._lit_room()
        # stealth_dc=20, observer passive perception = 10+3=13
        _add(w, 4, 2, "NPC", stealth_dc=20)
        vis = w.get_visible_world(3, perception_bonus=3)
        assert 4 not in vis.objects

    def test_hidden_object_met_passive_perception_visible(self):
        w, room, pc = self._lit_room()
        # stealth_dc=13, observer passive perception = 10+3=13 — ties pass
        _add(w, 4, 2, "NPC", stealth_dc=13)
        vis = w.get_visible_world(3, perception_bonus=3)
        assert 4 in vis.objects

    def test_no_stealth_dc_always_visible(self):
        w, room, pc = self._lit_room()
        _add(w, 4, 2, "NPC")
        vis = w.get_visible_world(3, perception_bonus=0)
        assert 4 in vis.objects

    def test_hidden_child_of_open_container_filtered(self):
        """Child inside an open chest must also pass stealth check."""
        w, room, pc = self._lit_room()
        chest = _add(w, 4, 2, "chest")  # open by default (closed=False)
        # Item hiding inside chest with high stealth_dc
        _add(w, 5, 4, "item", stealth_dc=25)
        vis = w.get_visible_world(3, perception_bonus=0)
        assert 4 in vis.objects   # chest visible
        assert 5 not in vis.objects  # hidden item inside chest not visible


# ---------------------------------------------------------------------------
# Closed container occlusion
# ---------------------------------------------------------------------------

class TestClosedContainerOcclusion:
    def _room_with_chest(self, closed: bool) -> tuple[World, Object, Object, Object, Object]:
        w = _world()
        _add(w, 1, None, "planet")
        room = _add(w, 2, 1, "room")
        pc = _add(w, 3, 2, "PC")
        chest = _add(w, 4, 2, "chest", closed=closed)
        sword = _add(w, 5, 4, "sword")
        return w, room, pc, chest, sword

    def test_closed_chest_hides_contents(self):
        w, room, pc, chest, sword = self._room_with_chest(closed=True)
        vis = w.get_visible_world(3)
        assert 4 in vis.objects   # chest itself is visible
        assert 5 not in vis.objects  # sword inside closed chest not visible

    def test_open_chest_reveals_contents(self):
        w, room, pc, chest, sword = self._room_with_chest(closed=False)
        vis = w.get_visible_world(3)
        assert 4 in vis.objects
        assert 5 in vis.objects


# ---------------------------------------------------------------------------
# get_sub_world tool wrapper
# ---------------------------------------------------------------------------

class TestGetSubWorldTool:
    def test_tool_returns_success(self):
        from src.backend.core.tools import WorldTools
        w = _world()
        _add(w, 1, None, "planet")
        _add(w, 2, 1, "room")
        _add(w, 3, 2, "PC")
        tools = WorldTools(w)
        result = tools.get_sub_world(3)
        assert result.success is True
        assert "objects" in result.data

    def test_tool_unknown_observer_returns_empty(self):
        from src.backend.core.tools import WorldTools
        w = _world()
        tools = WorldTools(w)
        result = tools.get_sub_world(999)
        assert result.success is True
        assert result.data["objects"] == {}

    def test_tool_passes_perception_bonus(self):
        from src.backend.core.tools import WorldTools
        w = _world()
        _add(w, 1, None, "planet")
        _add(w, 2, 1, "room")
        _add(w, 3, 2, "PC")
        # Rogue hidden with DC 18 — needs perception >= 18
        _add(w, 4, 2, "NPC", stealth_dc=18)
        tools = WorldTools(w)
        low = tools.get_sub_world(3, perception_bonus=0)
        high = tools.get_sub_world(3, perception_bonus=8)
        assert 4 not in low.data["objects"]
        assert "4" in high.data["objects"] or 4 in high.data["objects"]

    def test_tool_passes_darkvision(self):
        from src.backend.core.tools import WorldTools
        w = _world()
        _add(w, 1, None, "planet")
        _add(w, 2, 1, "room", light="dark")
        _add(w, 3, 2, "PC", loc=[0.0, 0.0, 0.0])
        _add(w, 4, 2, "NPC", loc=[30.0, 0.0, 0.0])
        tools = WorldTools(w)
        no_darkvision = tools.get_sub_world(3)
        with_darkvision = tools.get_sub_world(3, darkvision_range=60.0)
        # NPC absent without darkvision
        assert "4" not in no_darkvision.data["objects"] and 4 not in no_darkvision.data["objects"]
        # NPC present with darkvision
        assert "4" in with_darkvision.data["objects"] or 4 in with_darkvision.data["objects"]
