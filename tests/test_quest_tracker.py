"""Tests for quest tracker tools and API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.backend.core.campaign_io import new_campaign_object
from src.backend.core.tools import WorldTools
from src.backend.models.world import World


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world() -> World:
    campaign = new_campaign_object("QuestTest", seed=1)
    return campaign.world


def _get_root(world: World):
    return next(obj for obj in world.objects.values() if obj.parent is None)


# ---------------------------------------------------------------------------
# add_quest
# ---------------------------------------------------------------------------

def test_add_quest_basic():
    world = _make_world()
    tools = WorldTools(world)
    result = tools.add_quest("Find the MacGuffin", ["Locate clues", "Enter the dungeon", "Retrieve artifact"])
    assert result.success
    assert result.data["quest"]["title"] == "Find the MacGuffin"
    assert len(result.data["quest"]["milestones"]) == 3
    assert result.data["quest"]["milestones"][0]["completed"] is False


def test_add_quest_stores_on_root():
    world = _make_world()
    tools = WorldTools(world)
    tools.add_quest("Save the Village", ["Rescue hostages"])
    root = _get_root(world)
    assert "quests" in root.properties
    assert len(root.properties["quests"]) == 1


def test_add_multiple_quests():
    world = _make_world()
    tools = WorldTools(world)
    tools.add_quest("Quest A", ["Step 1"])
    tools.add_quest("Quest B", ["Step 1", "Step 2"])
    root = _get_root(world)
    assert len(root.properties["quests"]) == 2
    assert root.properties["quests"][0]["id"] == 0
    assert root.properties["quests"][1]["id"] == 1


def test_add_quest_empty_milestones():
    world = _make_world()
    tools = WorldTools(world)
    result = tools.add_quest("Empty Quest", [])
    assert result.success
    assert result.data["quest"]["milestones"] == []


# ---------------------------------------------------------------------------
# complete_milestone
# ---------------------------------------------------------------------------

def test_complete_milestone_basic():
    world = _make_world()
    tools = WorldTools(world)
    tools.add_quest("Main Quest", ["Talk to innkeeper", "Find the cave", "Defeat the troll"])
    result = tools.complete_milestone(0, 1)
    assert result.success
    root = _get_root(world)
    milestone = root.properties["quests"][0]["milestones"][1]
    assert milestone["completed"] is True


def test_complete_milestone_does_not_affect_others():
    world = _make_world()
    tools = WorldTools(world)
    tools.add_quest("Quest", ["A", "B", "C"])
    tools.complete_milestone(0, 1)
    root = _get_root(world)
    milestones = root.properties["quests"][0]["milestones"]
    assert milestones[0]["completed"] is False
    assert milestones[1]["completed"] is True
    assert milestones[2]["completed"] is False


def test_complete_milestone_invalid_quest_id():
    world = _make_world()
    tools = WorldTools(world)
    result = tools.complete_milestone(99, 0)
    assert not result.success
    assert "not found" in result.message.lower()


def test_complete_milestone_invalid_milestone_idx():
    world = _make_world()
    tools = WorldTools(world)
    tools.add_quest("Quest", ["Only one"])
    result = tools.complete_milestone(0, 5)
    assert not result.success
    assert "not found" in result.message.lower()


def test_complete_milestone_already_done():
    world = _make_world()
    tools = WorldTools(world)
    tools.add_quest("Quest", ["Do the thing"])
    tools.complete_milestone(0, 0)
    result = tools.complete_milestone(0, 0)
    assert result.success
    assert "already completed" in result.message.lower()


# ---------------------------------------------------------------------------
# get_quests
# ---------------------------------------------------------------------------

def test_get_quests_empty():
    world = _make_world()
    tools = WorldTools(world)
    result = tools.get_quests()
    assert result.success
    assert result.data["quests"] == []


def test_get_quests_returns_all():
    world = _make_world()
    tools = WorldTools(world)
    tools.add_quest("Quest 1", ["A"])
    tools.add_quest("Quest 2", ["B", "C"])
    result = tools.get_quests()
    assert result.success
    assert len(result.data["quests"]) == 2


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

def _setup_client(tmp_path, monkeypatch):
    """Create a test client with a temporary campaigns directory."""
    monkeypatch.setattr(
        "src.backend.core.campaign_manager.campaigns_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "src.backend.api.campaign_routes.get_current_user",
        lambda req: type("S", (), {"user_id": "u1", "username": "tester"})(),
    )

    from src.backend.core.campaign_manager import create_campaign, save_campaign_world
    from src.backend.core.campaign_io import new_campaign_object

    meta = create_campaign("QuestAPITest", created_by="tester", seed=42)
    campaign = new_campaign_object("QuestAPITest", seed=42)
    save_campaign_world(meta.id, campaign)

    from src.backend.main import app
    client = TestClient(app)
    return client, meta.id


def test_get_quests_endpoint_empty(tmp_path, monkeypatch):
    client, cid = _setup_client(tmp_path, monkeypatch)
    resp = client.get(f"/api/campaigns/{cid}/quests")
    assert resp.status_code == 200
    assert resp.json()["quests"] == []


def test_post_quest_endpoint(tmp_path, monkeypatch):
    client, cid = _setup_client(tmp_path, monkeypatch)
    resp = client.post(
        f"/api/campaigns/{cid}/quests",
        json={"title": "API Quest", "milestones": ["Step 1", "Step 2"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quest"]["title"] == "API Quest"
    assert len(data["quest"]["milestones"]) == 2


def test_post_quest_then_get(tmp_path, monkeypatch):
    client, cid = _setup_client(tmp_path, monkeypatch)
    client.post(
        f"/api/campaigns/{cid}/quests",
        json={"title": "Persisted Quest", "milestones": ["Do it"]},
    )
    resp = client.get(f"/api/campaigns/{cid}/quests")
    assert resp.status_code == 200
    assert len(resp.json()["quests"]) == 1


def test_complete_milestone_endpoint(tmp_path, monkeypatch):
    client, cid = _setup_client(tmp_path, monkeypatch)
    client.post(
        f"/api/campaigns/{cid}/quests",
        json={"title": "Test Quest", "milestones": ["First", "Second"]},
    )
    resp = client.post(
        f"/api/campaigns/{cid}/quests/complete-milestone",
        json={"quest_id": 0, "milestone_idx": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quest"]["milestones"][0]["completed"] is True
    assert data["quest"]["milestones"][1]["completed"] is False


def test_complete_milestone_endpoint_invalid(tmp_path, monkeypatch):
    client, cid = _setup_client(tmp_path, monkeypatch)
    resp = client.post(
        f"/api/campaigns/{cid}/quests/complete-milestone",
        json={"quest_id": 99, "milestone_idx": 0},
    )
    assert resp.status_code == 400
