"""Tests for the returning-player DM recap on join."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.backend.main import create_app
from src.backend.models.user import CampaignMeta, ChatMessage

CAMPAIGN_ID = "test-recap-campaign"
FAKE_META = CampaignMeta(
    id=CAMPAIGN_ID,
    name="Recap Campaign",
    seed=42,
    turn_number=7,
    created_by="tester",
    created_at="2026-01-01T00:00:00",
    updated_at="2026-01-01T00:00:00",
)
FAKE_SESSION = MagicMock()
FAKE_SESSION.user_id = "u1"
FAKE_SESSION.username = "tester"

RETURNING_PLAYER = {
    "user_id": "u1",
    "username": "tester",
    "character_object_id": 10,
    "character_name": "Elara",
    "race": "Elf",
    "class_type": "Wizard",
    "hp_current": 28,
    "hp_max": 30,
    "encumbrance_current": 5.0,
    "encumbrance_max": 150.0,
    "joined_at": "2026-01-01T00:00:00",
    "last_seen": "2026-01-01T00:00:00",
}

NEW_PLAYER = {
    "user_id": "u1",
    "username": "tester",
    "character_object_id": None,
    "character_name": None,
    "race": None,
    "class_type": None,
    "hp_current": 0,
    "hp_max": 0,
    "encumbrance_current": 0.0,
    "encumbrance_max": 150.0,
    "joined_at": "2026-01-01T00:00:00",
    "last_seen": "2026-01-01T00:00:00",
}


def _make_char_obj(char_id=10, parent=5):
    obj = MagicMock()
    obj.id = char_id
    obj.parent = parent
    obj.properties = {
        "race": "Elf",
        "classes": [{"type": "Wizard", "level": 3}],
        "hp": {"current": 28, "max": 30},
    }
    return obj


def _make_location(name="Neverwinter"):
    loc = MagicMock()
    loc.name = name
    return loc


@pytest.fixture
def client():
    app = create_app()
    with patch("src.backend.api.campaign_routes.get_current_user", return_value=FAKE_SESSION):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


def test_join_new_player_no_recap(client):
    """New players (no character yet) do not receive a DM recap."""
    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.add_player", return_value=NEW_PLAYER):
        res = client.post(f"/api/campaigns/{CAMPAIGN_ID}/join")

    assert res.status_code == 200
    data = res.json()
    assert data["needs_character"] is True
    assert data["summary"] is None


def test_join_returning_player_gets_ai_recap(client):
    """Returning players receive an AI-generated narrative recap."""
    fake_campaign = MagicMock()
    fake_campaign.world.get_object.side_effect = lambda cid: (
        _make_char_obj() if cid == 10 else _make_location("Neverwinter")
    )

    recap_text = "Last time, Elara uncovered a dark secret in the library. The shadows still stir."

    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.add_player", return_value=RETURNING_PLAYER), \
         patch("src.backend.api.campaign_routes.load_campaign_world", return_value=fake_campaign), \
         patch("src.backend.api.campaign_routes.get_chat", return_value=[]), \
         patch("src.backend.api.campaign_routes.ai_client") as mock_ai:
        mock_ai.generate_dm_recap.return_value = recap_text
        res = client.post(f"/api/campaigns/{CAMPAIGN_ID}/join")

    assert res.status_code == 200
    data = res.json()
    assert data["needs_character"] is False
    assert data["summary"] == recap_text


def test_join_recap_uses_recent_chat(client):
    """The recap call is passed recent chat messages from the campaign."""
    fake_campaign = MagicMock()
    fake_campaign.world.get_object.side_effect = lambda cid: (
        _make_char_obj() if cid == 10 else _make_location("Waterdeep")
    )

    chat_msgs = [
        ChatMessage(sender="DM", sender_type="DM", text="The goblin attacks!", turn_number=5),
        ChatMessage(sender="Elara", sender_type="PC", text="I cast fireball.", turn_number=5),
    ]

    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.add_player", return_value=RETURNING_PLAYER), \
         patch("src.backend.api.campaign_routes.load_campaign_world", return_value=fake_campaign), \
         patch("src.backend.api.campaign_routes.get_chat", return_value=chat_msgs), \
         patch("src.backend.api.campaign_routes.ai_client") as mock_ai:
        mock_ai.generate_dm_recap.return_value = "A fiery recap."
        res = client.post(f"/api/campaigns/{CAMPAIGN_ID}/join")

    assert res.status_code == 200
    call_kwargs = mock_ai.generate_dm_recap.call_args[1]
    assert len(call_kwargs["recent_messages"]) == 2
    assert call_kwargs["recent_messages"][0]["text"] == "The goblin attacks!"


def test_join_recap_fallback_when_world_missing(client):
    """When world.yaml is missing, join still succeeds with a fallback summary."""
    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.add_player", return_value=RETURNING_PLAYER), \
         patch("src.backend.api.campaign_routes.load_campaign_world", return_value=None):
        res = client.post(f"/api/campaigns/{CAMPAIGN_ID}/join")

    assert res.status_code == 200
    data = res.json()
    assert data["summary"] is not None
    assert "Elara" in data["summary"]


def test_join_recap_includes_character_details(client):
    """Recap call receives the character's name, race, class, location, and turn number."""
    fake_campaign = MagicMock()
    fake_campaign.world.get_object.side_effect = lambda cid: (
        _make_char_obj() if cid == 10 else _make_location("Baldur's Gate")
    )

    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.add_player", return_value=RETURNING_PLAYER), \
         patch("src.backend.api.campaign_routes.load_campaign_world", return_value=fake_campaign), \
         patch("src.backend.api.campaign_routes.get_chat", return_value=[]), \
         patch("src.backend.api.campaign_routes.ai_client") as mock_ai:
        mock_ai.generate_dm_recap.return_value = "A tale of wonder."
        client.post(f"/api/campaigns/{CAMPAIGN_ID}/join")

    kw = mock_ai.generate_dm_recap.call_args[1]
    assert kw["character_name"] == "Elara"
    assert kw["race"] == "Elf"
    assert kw["class_str"] == "Wizard"
    assert kw["location_name"] == "Baldur's Gate"
    assert kw["turn_number"] == 7


def test_generate_dm_recap_method_llm_call():
    """generate_dm_recap builds a prompt containing key character details and calls llm.complete."""
    from src.backend.core.ai_client import AIClient

    client_instance = AIClient()
    fake_llm = MagicMock()
    fake_llm.complete.return_value = MagicMock(text="  You fought bravely.  ")
    client_instance._llm = fake_llm

    result = client_instance.generate_dm_recap(
        character_name="Thorin",
        race="Dwarf",
        class_str="Fighter",
        location_name="The Underdark",
        turn_number=3,
        recent_messages=[{"sender": "DM", "text": "The troll roars."}],
    )

    assert result == "You fought bravely."
    prompt = fake_llm.complete.call_args[0][0]
    assert "Thorin" in prompt
    assert "Dwarf" in prompt
    assert "Fighter" in prompt
    assert "The Underdark" in prompt
    assert "The troll roars" in prompt


def test_generate_dm_recap_method_fallback_on_error():
    """generate_dm_recap returns a contextual fallback when LLM raises."""
    from src.backend.core.ai_client import AIClient

    client_instance = AIClient()
    fake_llm = MagicMock()
    fake_llm.complete.side_effect = RuntimeError("offline")
    client_instance._llm = fake_llm

    result = client_instance.generate_dm_recap(
        character_name="Lirien",
        race="Half-Elf",
        class_str="Rogue",
        location_name="Shadowfell",
        turn_number=2,
        recent_messages=[],
    )

    assert "Lirien" in result
    assert "Shadowfell" in result
