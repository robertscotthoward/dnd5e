"""Tests for Memgraph sync on world-mutating tool calls.

WorldTools must call upsert_object / delete_object in memgraph_client
after create_object, move_object, and delete_object succeed.
Memgraph must not be running; tests use mocks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from src.backend.core.tools import WorldTools
from src.backend.models.world import Object, World


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world() -> World:
    world = World(name="TestWorld")
    root = Object(id=1, parent=None, type="system", name="Root", is_moveable=False)
    tavern = Object(id=2, parent=1, type="building", name="Tavern")
    pc = Object(id=3, parent=2, type="PC", name="Arin", is_moveable=True)
    world.objects[1] = root
    world.objects[2] = tavern
    world.objects[3] = pc
    world.max_id = 3
    return world


_MEMGRAPH_URL = "bolt://localhost:7687"


# ---------------------------------------------------------------------------
# create_object — upsert called on success
# ---------------------------------------------------------------------------

class TestCreateObjectSync:
    def test_upsert_called_on_success(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch("src.backend.core.tools.WorldTools._sync_upsert") as mock_upsert:
            result = tools.create_object(type="sword", parent_id=3, name="Longsword")

        assert result.success
        mock_upsert.assert_called_once()
        synced_obj = mock_upsert.call_args[0][0]
        assert synced_obj.type == "sword"
        assert synced_obj.name == "Longsword"
        assert synced_obj.parent == 3

    def test_upsert_not_called_on_failure(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch("src.backend.core.tools.WorldTools._sync_upsert") as mock_upsert:
            result = tools.create_object(type="sword", parent_id=999, name="Orphan")

        assert not result.success
        mock_upsert.assert_not_called()

    def test_no_upsert_when_memgraph_url_is_none(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=None)

        with patch("src.backend.core.memgraph_client.upsert_object") as mock_mg:
            result = tools.create_object(type="dagger", parent_id=3, name="Dagger")

        assert result.success
        mock_mg.assert_not_called()


# ---------------------------------------------------------------------------
# move_object — upsert called with updated parent
# ---------------------------------------------------------------------------

class TestMoveObjectSync:
    def test_upsert_called_after_move(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch("src.backend.core.tools.WorldTools._sync_upsert") as mock_upsert:
            result = tools.move_object(id=3, parent_id=1)

        assert result.success
        mock_upsert.assert_called_once()
        synced_obj = mock_upsert.call_args[0][0]
        assert synced_obj.id == 3
        assert synced_obj.parent == 1

    def test_upsert_not_called_on_failure(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch("src.backend.core.tools.WorldTools._sync_upsert") as mock_upsert:
            result = tools.move_object(id=999, parent_id=1)

        assert not result.success
        mock_upsert.assert_not_called()

    def test_no_upsert_when_memgraph_url_is_none(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=None)

        with patch("src.backend.core.memgraph_client.upsert_object") as mock_mg:
            result = tools.move_object(id=3, parent_id=1)

        assert result.success
        mock_mg.assert_not_called()


# ---------------------------------------------------------------------------
# delete_object — delete_object (graph) called for deleted IDs
# ---------------------------------------------------------------------------

class TestDeleteObjectSync:
    def test_sync_delete_called_for_single_object(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch("src.backend.core.tools.WorldTools._sync_delete") as mock_del:
            result = tools.delete_object(id=3, cascade=False)

        assert result.success
        mock_del.assert_called_once_with(3)

    def test_sync_delete_called_for_cascade(self):
        """Cascade delete must remove the parent node and all descendants."""
        world = _make_world()
        # Add a child of the tavern to exercise cascade
        from src.backend.models.world import Object as WObj
        item = WObj(id=4, parent=2, type="item", name="Barrel")
        world.objects[4] = item
        world.max_id = 4

        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch("src.backend.core.tools.WorldTools._sync_delete") as mock_del:
            result = tools.delete_object(id=2, cascade=True)

        assert result.success
        deleted = {c[0][0] for c in mock_del.call_args_list}
        # tavern (2), pc (3), item (4)
        assert 2 in deleted
        assert 3 in deleted
        assert 4 in deleted

    def test_sync_delete_not_called_on_failure(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch("src.backend.core.tools.WorldTools._sync_delete") as mock_del:
            result = tools.delete_object(id=999)

        assert not result.success
        mock_del.assert_not_called()

    def test_no_delete_when_memgraph_url_is_none(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=None)

        with patch("src.backend.core.memgraph_client.delete_object") as mock_mg:
            result = tools.delete_object(id=3)

        assert result.success
        mock_mg.assert_not_called()


# ---------------------------------------------------------------------------
# _sync_upsert / _sync_delete — graceful failure (no raise)
# ---------------------------------------------------------------------------

class TestSyncGracefulFailure:
    def test_upsert_logs_warning_on_exception(self, caplog):
        import logging
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch(
            "src.backend.core.memgraph_client.upsert_object",
            side_effect=Exception("connection refused"),
        ):
            with caplog.at_level(logging.WARNING, logger="src.backend.core.tools"):
                tools._sync_upsert(world.objects[3])

        assert any("Memgraph upsert failed" in r.message for r in caplog.records)

    def test_delete_logs_warning_on_exception(self, caplog):
        import logging
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch(
            "src.backend.core.memgraph_client.delete_object",
            side_effect=Exception("bolt error"),
        ):
            with caplog.at_level(logging.WARNING, logger="src.backend.core.tools"):
                tools._sync_delete(3)

        assert any("Memgraph delete failed" in r.message for r in caplog.records)

    def test_upsert_failure_does_not_affect_tool_result(self):
        """A Memgraph failure must not propagate to the caller."""
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch(
            "src.backend.core.memgraph_client.upsert_object",
            side_effect=Exception("unreachable"),
        ):
            result = tools.create_object(type="torch", parent_id=2, name="Torch")

        assert result.success

    def test_delete_failure_does_not_affect_tool_result(self):
        world = _make_world()
        tools = WorldTools(world, memgraph_url=_MEMGRAPH_URL)

        with patch(
            "src.backend.core.memgraph_client.delete_object",
            side_effect=Exception("unreachable"),
        ):
            result = tools.delete_object(id=3)

        assert result.success


# ---------------------------------------------------------------------------
# _obj_to_props helper used by _sync_upsert
# ---------------------------------------------------------------------------

class TestObjToProps:
    def test_obj_to_props_contains_required_fields(self):
        from src.backend.core.memgraph_client import _obj_to_props

        obj = Object(id=5, parent=2, type="NPC", name="Barkeep", weight=180.0, cost=0)
        props = _obj_to_props(obj)

        for field in ("obj_id", "type", "name", "weight", "is_moveable", "loc_x", "loc_y", "loc_z"):
            assert field in props, f"Missing {field!r}"
        assert props["obj_id"] == 5
        assert props["type"] == "NPC"
        assert props["name"] == "Barkeep"
