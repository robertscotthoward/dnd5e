"""Tests for DM chat integration — every player message triggers the DM agent."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backend.api.ws_routes import ConnectionManager, _run_dm_response


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# ConnectionManager unit tests
# ---------------------------------------------------------------------------


def test_connection_manager_connect_and_get_users():
    manager = ConnectionManager()
    ws = AsyncMock()
    _run(manager.connect(ws, "camp1", "alice", "Aragorn"))
    users = manager.get_users("camp1")
    assert len(users) == 1
    assert users[0]["username"] == "alice"
    assert users[0]["character_name"] == "Aragorn"


def test_connection_manager_disconnect():
    manager = ConnectionManager()
    ws = AsyncMock()
    _run(manager.connect(ws, "camp1", "bob", "Gimli"))
    manager.disconnect(ws, "camp1")
    assert manager.get_users("camp1") == []


def test_connection_manager_broadcast_sends_to_all():
    manager = ConnectionManager()
    ws1, ws2 = AsyncMock(), AsyncMock()
    _run(manager.connect(ws1, "camp1", "alice", "Alice"))
    _run(manager.connect(ws2, "camp1", "bob", "Bob"))
    msg = {"type": "chat", "text": "hello"}
    _run(manager.broadcast("camp1", msg))
    ws1.send_json.assert_called_once_with(msg)
    ws2.send_json.assert_called_once_with(msg)


def test_broadcast_removes_dead_connections():
    """Dead WebSocket connections should be pruned during broadcast."""
    manager = ConnectionManager()
    dead_ws = AsyncMock()
    dead_ws.send_json.side_effect = Exception("closed")
    live_ws = AsyncMock()
    _run(manager.connect(dead_ws, "camp1", "dead", "Dead"))
    _run(manager.connect(live_ws, "camp1", "live", "Live"))
    _run(manager.broadcast("camp1", {"type": "ping"}))
    users = manager.get_users("camp1")
    assert len(users) == 1
    assert users[0]["username"] == "live"


# ---------------------------------------------------------------------------
# DM trigger: every message must invoke _run_dm_response
# ---------------------------------------------------------------------------


def test_every_chat_message_triggers_dm():
    """
    Verify that _run_dm_response produces a dm_response broadcast for a plain message,
    not just ones starting with 'DM:'.
    """
    broadcasted = []

    mock_manager = MagicMock()
    mock_manager.broadcast = AsyncMock(side_effect=lambda cid, msg: broadcasted.append(msg))

    mock_meta = MagicMock()
    mock_meta.game_mode = "Exploration"
    mock_meta.turn_number = 1
    mock_meta.active_player_turn = None
    mock_meta.combat_queue = []
    mock_meta.model_dump = MagicMock(return_value={})

    mock_campaign = MagicMock()
    mock_campaign.turn_number = 1
    mock_campaign.world = MagicMock()

    with (
        patch("src.backend.api.ws_routes.get_campaign_meta", return_value=mock_meta),
        patch("src.backend.api.ws_routes.load_campaign_world", return_value=mock_campaign),
        patch("src.backend.api.ws_routes.save_campaign_world"),
        patch("src.backend.api.ws_routes.save_campaign_meta"),
        patch("src.backend.api.ws_routes.append_chat"),
        patch("src.backend.api.ws_routes.get_players", return_value=[]),
        patch("src.backend.api.ws_routes.WorldTools"),
        patch(
            "src.backend.api.ws_routes.ai_client.generate_dm_response",
            return_value="The DM speaks.",
        ),
        patch("src.backend.api.ws_routes.manager", mock_manager),
    ):
        _run(_run_dm_response("camp1", "I look around the room", "alice", "Alice"))

    dm_responses = [m for m in broadcasted if m.get("type") == "dm_response"]
    assert len(dm_responses) == 1
    assert dm_responses[0]["message"]["text"] == "The DM speaks."
    assert dm_responses[0]["message"]["sender"] == "DM"


def test_dm_response_message_prefixed_as_dm():
    """DM broadcast message must have sender='DM' and sender_type='DM'."""
    broadcasted = []

    mock_manager = MagicMock()
    mock_manager.broadcast = AsyncMock(side_effect=lambda cid, msg: broadcasted.append(msg))

    mock_meta = MagicMock()
    mock_meta.game_mode = "Exploration"
    mock_meta.turn_number = 2
    mock_meta.active_player_turn = None
    mock_meta.combat_queue = []
    mock_meta.model_dump = MagicMock(return_value={})

    mock_campaign = MagicMock()
    mock_campaign.turn_number = 2
    mock_campaign.world = MagicMock()

    with (
        patch("src.backend.api.ws_routes.get_campaign_meta", return_value=mock_meta),
        patch("src.backend.api.ws_routes.load_campaign_world", return_value=mock_campaign),
        patch("src.backend.api.ws_routes.save_campaign_world"),
        patch("src.backend.api.ws_routes.save_campaign_meta"),
        patch("src.backend.api.ws_routes.append_chat"),
        patch("src.backend.api.ws_routes.get_players", return_value=[]),
        patch("src.backend.api.ws_routes.WorldTools"),
        patch(
            "src.backend.api.ws_routes.ai_client.generate_dm_response",
            return_value="You see a goblin!",
        ),
        patch("src.backend.api.ws_routes.manager", mock_manager),
    ):
        _run(_run_dm_response("camp1", "DM: what do I see?", "bob", "Bob"))

    dm_responses = [m for m in broadcasted if m.get("type") == "dm_response"]
    assert len(dm_responses) == 1
    msg = dm_responses[0]["message"]
    assert msg["sender"] == "DM"
    assert msg["sender_type"] == "DM"
    assert msg["text"] == "You see a goblin!"


def test_dm_unavailable_broadcasts_error_message():
    """When the AI client raises, a [DM is unavailable] message is still broadcast."""
    broadcasted = []

    mock_manager = MagicMock()
    mock_manager.broadcast = AsyncMock(side_effect=lambda cid, msg: broadcasted.append(msg))

    mock_meta = MagicMock()
    mock_meta.game_mode = "Exploration"
    mock_meta.turn_number = 1
    mock_meta.active_player_turn = None
    mock_meta.combat_queue = []
    mock_meta.model_dump = MagicMock(return_value={})

    mock_campaign = MagicMock()
    mock_campaign.turn_number = 1
    mock_campaign.world = MagicMock()

    with (
        patch("src.backend.api.ws_routes.get_campaign_meta", return_value=mock_meta),
        patch("src.backend.api.ws_routes.load_campaign_world", return_value=mock_campaign),
        patch("src.backend.api.ws_routes.save_campaign_world"),
        patch("src.backend.api.ws_routes.save_campaign_meta"),
        patch("src.backend.api.ws_routes.append_chat"),
        patch("src.backend.api.ws_routes.get_players", return_value=[]),
        patch("src.backend.api.ws_routes.WorldTools"),
        patch(
            "src.backend.api.ws_routes.ai_client.generate_dm_response",
            side_effect=RuntimeError("Ollama down"),
        ),
        patch("src.backend.api.ws_routes.manager", mock_manager),
    ):
        _run(_run_dm_response("camp1", "Hello", "eve", "Eve"))

    dm_responses = [m for m in broadcasted if m.get("type") == "dm_response"]
    assert len(dm_responses) == 1
    assert "[DM is unavailable" in dm_responses[0]["message"]["text"]
