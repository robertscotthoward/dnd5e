"""Tests for the campaign journal feature."""

import re
from pathlib import Path

import pytest

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.core.campaign_manager import (
    append_journal,
    campaign_path,
    create_campaign,
    get_journal,
    save_campaign_meta,
)
from src.backend.core.ai_client import AIClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(tmp_path, monkeypatch) -> str:
    """Create a minimal campaign folder and return the campaign_id."""
    monkeypatch.setattr(
        "src.backend.core.campaign_manager.campaigns_root",
        lambda: tmp_path,
    )
    meta = create_campaign("JournalTest", created_by="tester", seed=1)
    return meta.id


# ---------------------------------------------------------------------------
# append_journal / get_journal
# ---------------------------------------------------------------------------

def test_append_journal_creates_file(tmp_path, monkeypatch):
    cid = _make_campaign(tmp_path, monkeypatch)
    append_journal(cid, 1, "The adventurers entered the dungeon.")
    journal_file = tmp_path / cid / "journal.md"
    assert journal_file.exists()


def test_append_journal_includes_turn_number(tmp_path, monkeypatch):
    cid = _make_campaign(tmp_path, monkeypatch)
    append_journal(cid, 3, "A goblin was slain.")
    content = get_journal(cid)
    assert "Turn 3" in content


def test_append_journal_includes_entry_text(tmp_path, monkeypatch):
    cid = _make_campaign(tmp_path, monkeypatch)
    entry = "The party discovered a hidden passage behind the waterfall."
    append_journal(cid, 2, entry)
    content = get_journal(cid)
    assert entry in content


def test_append_journal_multiple_entries(tmp_path, monkeypatch):
    cid = _make_campaign(tmp_path, monkeypatch)
    append_journal(cid, 1, "Turn one events.")
    append_journal(cid, 2, "Turn two events.")
    append_journal(cid, 3, "Turn three events.")
    content = get_journal(cid)
    assert "Turn 1" in content
    assert "Turn 2" in content
    assert "Turn 3" in content


def test_get_journal_empty_when_no_entries(tmp_path, monkeypatch):
    cid = _make_campaign(tmp_path, monkeypatch)
    content = get_journal(cid)
    assert content == ""


def test_append_journal_uses_separator(tmp_path, monkeypatch):
    cid = _make_campaign(tmp_path, monkeypatch)
    append_journal(cid, 1, "First entry.")
    append_journal(cid, 2, "Second entry.")
    content = get_journal(cid)
    assert "---" in content


def test_journal_entries_ordered(tmp_path, monkeypatch):
    cid = _make_campaign(tmp_path, monkeypatch)
    for turn in range(1, 6):
        append_journal(cid, turn, f"Events of turn {turn}.")
    content = get_journal(cid)
    positions = [content.find(f"Turn {t}") for t in range(1, 6)]
    assert positions == sorted(positions)


# ---------------------------------------------------------------------------
# AIClient.generate_journal_entry (mocked LLM)
# ---------------------------------------------------------------------------

class _FakeLLM:
    def complete(self, prompt: str):
        class _Resp:
            text = "The heroes ventured forth into darkness."
        return _Resp()


def test_generate_journal_entry_returns_string(monkeypatch):
    client = AIClient()
    client._llm = _FakeLLM()
    result = client.generate_journal_entry(
        campaign_name="Test",
        turn_number=1,
        narration="The party fought goblins.",
        player_names=["Aric", "Lyra"],
    )
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_journal_entry_fallback_on_error(monkeypatch):
    class _BrokenLLM:
        def complete(self, prompt):
            raise RuntimeError("LLM offline")

    client = AIClient()
    client._llm = _BrokenLLM()
    narration = "The party crossed the river."
    result = client.generate_journal_entry(
        campaign_name="Test",
        turn_number=2,
        narration=narration,
        player_names=["Aric"],
    )
    # Fallback returns the narration (truncated to 500 chars)
    assert result in narration or narration[:500] in result


def test_generate_journal_entry_empty_players(monkeypatch):
    client = AIClient()
    client._llm = _FakeLLM()
    result = client.generate_journal_entry(
        campaign_name="Solo",
        turn_number=1,
        narration="A lone hero explores.",
        player_names=[],
    )
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Journal API endpoint (via TestClient)
# ---------------------------------------------------------------------------

def test_journal_api_endpoint(tmp_path, monkeypatch):
    """GET /api/campaigns/{id}/journal returns journal text."""
    from fastapi.testclient import TestClient
    from src.backend.main import app
    from src.backend.core import auth as auth_module

    monkeypatch.setattr(
        "src.backend.core.campaign_manager.campaigns_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "src.backend.api.campaign_routes.get_current_user",
        lambda req: type("S", (), {"user_id": "u1", "username": "tester"})(),
    )

    meta = create_campaign("ApiJournalTest", created_by="tester", seed=1)
    append_journal(meta.id, 1, "The feast began at dusk.")

    client = TestClient(app)
    resp = client.get(f"/api/campaigns/{meta.id}/journal")
    assert resp.status_code == 200
    data = resp.json()
    assert "journal" in data
    assert "feast" in data["journal"]


def test_journal_api_empty_before_entries(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from src.backend.main import app

    monkeypatch.setattr(
        "src.backend.core.campaign_manager.campaigns_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "src.backend.api.campaign_routes.get_current_user",
        lambda req: type("S", (), {"user_id": "u1", "username": "tester"})(),
    )

    meta = create_campaign("EmptyJournal", created_by="tester", seed=1)
    client = TestClient(app)
    resp = client.get(f"/api/campaigns/{meta.id}/journal")
    assert resp.status_code == 200
    assert resp.json()["journal"] == ""


def test_journal_api_returns_404_for_missing_campaign(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from src.backend.main import app

    monkeypatch.setattr(
        "src.backend.core.campaign_manager.campaigns_root",
        lambda: tmp_path,
    )

    client = TestClient(app)
    resp = client.get("/api/campaigns/nonexistent-campaign/journal")
    assert resp.status_code == 404
