"""Tests for graph query helpers: get_path_between and get_nearby_objects.

Uses fake Bolt drivers so Memgraph does not need to be running.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.backend.core.memgraph_client import get_path_between, get_nearby_objects


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_session():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


def _mock_driver(session):
    driver = MagicMock()
    driver.session.return_value = session
    return driver


def _make_record(data: dict):
    """Return a MagicMock that behaves like a neo4j Record for the given keys."""
    record = MagicMock()
    record.__getitem__ = MagicMock(side_effect=lambda k: data[k])
    return record


# ---------------------------------------------------------------------------
# get_path_between
# ---------------------------------------------------------------------------

class TestGetPathBetween:
    def test_returns_hops_list_on_success(self):
        hops = [
            {"obj_id": 1, "type": "system", "name": "Root"},
            {"obj_id": 2, "type": "building", "name": "Tavern"},
            {"obj_id": 3, "type": "PC", "name": "Arin"},
        ]
        record = _make_record({"hops": hops})
        session = _mock_session()
        session.run.return_value.single.return_value = record
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            result = get_path_between(1, 3)

        assert result == hops

    def test_returns_empty_list_when_no_path(self):
        session = _mock_session()
        session.run.return_value.single.return_value = None
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            result = get_path_between(1, 99)

        assert result == []

    def test_cypher_uses_shortest_path(self):
        session = _mock_session()
        session.run.return_value.single.return_value = None
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            get_path_between(1, 2)

        query = session.run.call_args[0][0]
        assert "shortestPath" in query
        assert "CHILD_OF" in query

    def test_passes_both_ids_as_params(self):
        session = _mock_session()
        session.run.return_value.single.return_value = None
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            get_path_between(7, 42)

        kwargs = session.run.call_args[1]
        assert kwargs["id1"] == 7
        assert kwargs["id2"] == 42

    def test_closes_driver_on_success(self):
        session = _mock_session()
        session.run.return_value.single.return_value = None
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            get_path_between(1, 2)

        driver.close.assert_called_once()

    def test_closes_driver_on_exception(self):
        session = _mock_session()
        session.run.side_effect = RuntimeError("bolt error")
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            with pytest.raises(RuntimeError):
                get_path_between(1, 2)

        driver.close.assert_called_once()

    def test_result_is_list_of_dicts(self):
        hops = [{"obj_id": 5, "type": "NPC", "name": "Barkeep"}]
        record = _make_record({"hops": hops})
        session = _mock_session()
        session.run.return_value.single.return_value = record
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            result = get_path_between(5, 5)

        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_single_node_path(self):
        """A path from a node to itself resolves to one hop."""
        hops = [{"obj_id": 3, "type": "PC", "name": "Arin"}]
        record = _make_record({"hops": hops})
        session = _mock_session()
        session.run.return_value.single.return_value = record
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            result = get_path_between(3, 3)

        assert len(result) == 1
        assert result[0]["obj_id"] == 3


# ---------------------------------------------------------------------------
# get_nearby_objects
# ---------------------------------------------------------------------------

class TestGetNearbyObjects:
    def _make_row(self, obj_id: int, type_: str, name: str, distance: float):
        row = MagicMock()
        row.__getitem__ = MagicMock(
            side_effect=lambda k: {"obj_id": obj_id, "type": type_, "name": name, "distance": distance}[k]
        )
        return row

    def test_returns_list_of_dicts_with_required_keys(self):
        row = self._make_row(2, "building", "Tavern", 15.0)
        session = _mock_session()
        session.run.return_value.__iter__ = MagicMock(return_value=iter([row]))
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            result = get_nearby_objects(1, 30.0)

        assert len(result) == 1
        for key in ("obj_id", "type", "name", "distance"):
            assert key in result[0]

    def test_returns_empty_list_when_no_results(self):
        session = _mock_session()
        session.run.return_value.__iter__ = MagicMock(return_value=iter([]))
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            result = get_nearby_objects(1, 5.0)

        assert result == []

    def test_cypher_filters_by_radius_param(self):
        session = _mock_session()
        session.run.return_value.__iter__ = MagicMock(return_value=iter([]))
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            get_nearby_objects(3, 60.0)

        kwargs = session.run.call_args[1]
        assert kwargs["radius"] == 60.0
        assert kwargs["obj_id"] == 3

    def test_cypher_excludes_source_object(self):
        session = _mock_session()
        session.run.return_value.__iter__ = MagicMock(return_value=iter([]))
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            get_nearby_objects(3, 60.0)

        query = session.run.call_args[0][0]
        assert "<>" in query

    def test_cypher_uses_euclidean_distance(self):
        session = _mock_session()
        session.run.return_value.__iter__ = MagicMock(return_value=iter([]))
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            get_nearby_objects(1, 10.0)

        query = session.run.call_args[0][0]
        assert "sqrt" in query
        assert "loc_x" in query
        assert "loc_y" in query

    def test_closes_driver_on_success(self):
        session = _mock_session()
        session.run.return_value.__iter__ = MagicMock(return_value=iter([]))
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            get_nearby_objects(1, 10.0)

        driver.close.assert_called_once()

    def test_closes_driver_on_exception(self):
        session = _mock_session()
        session.run.side_effect = RuntimeError("bolt error")
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            with pytest.raises(RuntimeError):
                get_nearby_objects(1, 10.0)

        driver.close.assert_called_once()

    def test_multiple_results_returned_in_order(self):
        rows = [
            self._make_row(4, "NPC", "Guard", 10.0),
            self._make_row(5, "item", "Torch", 25.0),
            self._make_row(6, "PC", "Arin", 30.0),
        ]
        session = _mock_session()
        session.run.return_value.__iter__ = MagicMock(return_value=iter(rows))
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            result = get_nearby_objects(1, 60.0)

        assert len(result) == 3
        assert result[0]["distance"] == 10.0
        assert result[1]["distance"] == 25.0
        assert result[2]["distance"] == 30.0

    def test_distance_field_is_numeric(self):
        row = self._make_row(2, "PC", "Bob", 5.5)
        session = _mock_session()
        session.run.return_value.__iter__ = MagicMock(return_value=iter([row]))
        driver = _mock_driver(session)

        with patch("src.backend.core.memgraph_client._get_driver", return_value=driver):
            result = get_nearby_objects(1, 10.0)

        assert isinstance(result[0]["distance"], float)
