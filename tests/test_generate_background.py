"""Tests for the AI-generated character background endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.backend.main import create_app
from src.backend.models.user import CampaignMeta

CAMPAIGN_ID = "test-bg-campaign"
FAKE_META = CampaignMeta(
    id=CAMPAIGN_ID,
    name="Test Campaign",
    seed=1,
    created_by="tester",
    created_at="2026-01-01T00:00:00",
    updated_at="2026-01-01T00:00:00",
)
FAKE_SESSION = MagicMock()
FAKE_SESSION.user_id = "u1"
FAKE_SESSION.username = "tester"


@pytest.fixture
def client():
    app = create_app()
    with patch("src.backend.api.campaign_routes.get_current_user", return_value=FAKE_SESSION):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


def _post_bg(client, campaign_id=CAMPAIGN_ID, **overrides):
    payload = {
        "name": "Elara",
        "race": "Elf",
        "class_type": "Wizard",
        "region": "Neverwinter",
        **overrides,
    }
    return client.post(f"/api/campaigns/{campaign_id}/generate-background", json=payload)


def test_generate_background_returns_text(client):
    """Endpoint returns the LLM-generated background string."""
    fake_completion = MagicMock()
    fake_completion.text = "A wandering elf wizard seeking lost arcane tomes."

    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.ai_client") as mock_ai:
        mock_ai.llm.complete.return_value = fake_completion
        res = _post_bg(client)

    assert res.status_code == 200
    assert res.json()["background"] == fake_completion.text.strip()


def test_generate_background_fallback_on_llm_error(client):
    """When LLM raises, endpoint returns a generic fallback background."""
    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.ai_client") as mock_ai:
        mock_ai.llm.complete.side_effect = RuntimeError("Ollama offline")
        res = _post_bg(client, race="Half-Orc", class_type="Barbarian", region="The North")

    assert res.status_code == 200
    bg = res.json()["background"]
    assert "Half-Orc" in bg
    assert "Barbarian" in bg


def test_generate_background_404_unknown_campaign(client):
    """Returns 404 when the campaign does not exist."""
    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=None):
        res = _post_bg(client, campaign_id="nonexistent")
    assert res.status_code == 404


def test_generate_background_prompt_includes_character_details(client):
    """LLM is called with a prompt containing the character's name, race, class, and region."""
    fake_completion = MagicMock()
    fake_completion.text = "Some story."

    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.ai_client") as mock_ai:
        mock_ai.llm.complete.return_value = fake_completion
        _post_bg(client, name="Miriel", race="Gnome", class_type="Bard", region="Waterdeep")
        prompt = mock_ai.llm.complete.call_args[0][0]

    assert "Miriel" in prompt
    assert "Gnome" in prompt
    assert "Bard" in prompt
    assert "Waterdeep" in prompt


def test_generate_background_strips_whitespace(client):
    """Background text has leading/trailing whitespace stripped."""
    fake_completion = MagicMock()
    fake_completion.text = "  A noble fighter. \n"

    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.ai_client") as mock_ai:
        mock_ai.llm.complete.return_value = fake_completion
        res = _post_bg(client)

    assert res.json()["background"] == "A noble fighter."
