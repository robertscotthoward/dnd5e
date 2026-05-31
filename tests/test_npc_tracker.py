"""Tests for NPC relationship tracker tools and API endpoint."""

import pytest
from fastapi.testclient import TestClient

from src.backend.core.campaign_io import new_campaign_object
from src.backend.core.tools import WorldTools
from src.backend.models.world import World


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world() -> World:
    campaign = new_campaign_object("NpcTest", seed=1)
    return campaign.world


def _get_root(world: World):
    return next(obj for obj in world.objects.values() if obj.parent is None)


def _add_npc(world: World, name: str = "Gandalf") -> int:
    """Create a simple NPC object and return its ID."""
    tools = WorldTools(world)
    root = _get_root(world)
    result = tools.create_object(type="npc", parent_id=root.id, name=name)
    assert result.success
    return result.data["id"]


# ---------------------------------------------------------------------------
# set_npc_disposition
# ---------------------------------------------------------------------------

def test_set_npc_disposition_basic():
    world = _make_world()
    npc_id = _add_npc(world, "Elara")
    tools = WorldTools(world)
    result = tools.set_npc_disposition(npc_id, "friendly")
    assert result.success
    assert result.data["npc"]["disposition"] == "friendly"
    assert result.data["npc"]["name"] == "Elara"


def test_set_npc_disposition_all_valid_values():
    world = _make_world()
    for disposition in ("friendly", "neutral", "hostile", "allied"):
        npc_id = _add_npc(world, f"NPC_{disposition}")
        tools = WorldTools(world)
        result = tools.set_npc_disposition(npc_id, disposition)
        assert result.success, f"Failed for disposition: {disposition}"
        assert result.data["npc"]["disposition"] == disposition


def test_set_npc_disposition_invalid():
    world = _make_world()
    npc_id = _add_npc(world, "Shadow")
    tools = WorldTools(world)
    result = tools.set_npc_disposition(npc_id, "angry")
    assert not result.success
    assert "invalid" in result.message.lower()


def test_set_npc_disposition_nonexistent_id():
    world = _make_world()
    tools = WorldTools(world)
    result = tools.set_npc_disposition(9999, "friendly")
    assert not result.success
    assert "not found" in result.message.lower()


def test_set_npc_disposition_stores_on_root():
    world = _make_world()
    npc_id = _add_npc(world, "Merlin")
    tools = WorldTools(world)
    tools.set_npc_disposition(npc_id, "allied", notes="Helped us cross the bridge")
    root = _get_root(world)
    assert "known_npcs" in root.properties
    key = str(npc_id)
    assert key in root.properties["known_npcs"]
    stored = root.properties["known_npcs"][key]
    assert stored["disposition"] == "allied"
    assert stored["notes"] == "Helped us cross the bridge"


def test_set_npc_disposition_update_preserves_notes():
    world = _make_world()
    npc_id = _add_npc(world, "Bard")
    tools = WorldTools(world)
    tools.set_npc_disposition(npc_id, "neutral", notes="Sings for coins")
    tools.set_npc_disposition(npc_id, "friendly")  # update without new notes
    root = _get_root(world)
    stored = root.properties["known_npcs"][str(npc_id)]
    assert stored["disposition"] == "friendly"
    assert stored["notes"] == "Sings for coins"


def test_set_npc_disposition_overwrite_notes():
    world = _make_world()
    npc_id = _add_npc(world, "Guard")
    tools = WorldTools(world)
    tools.set_npc_disposition(npc_id, "hostile", notes="Attacked us on sight")
    tools.set_npc_disposition(npc_id, "neutral", notes="Bribed him")
    root = _get_root(world)
    stored = root.properties["known_npcs"][str(npc_id)]
    assert stored["notes"] == "Bribed him"


def test_multiple_npcs_tracked_independently():
    world = _make_world()
    id1 = _add_npc(world, "Alice")
    id2 = _add_npc(world, "Bob")
    tools = WorldTools(world)
    tools.set_npc_disposition(id1, "friendly")
    tools.set_npc_disposition(id2, "hostile")
    root = _get_root(world)
    assert root.properties["known_npcs"][str(id1)]["disposition"] == "friendly"
    assert root.properties["known_npcs"][str(id2)]["disposition"] == "hostile"


# ---------------------------------------------------------------------------
# get_npc_relationships
# ---------------------------------------------------------------------------

def test_get_npc_relationships_empty():
    world = _make_world()
    tools = WorldTools(world)
    result = tools.get_npc_relationships()
    assert result.success
    assert result.data["npcs"] == []


def test_get_npc_relationships_returns_all():
    world = _make_world()
    id1 = _add_npc(world, "Tavern Keeper")
    id2 = _add_npc(world, "City Guard")
    tools = WorldTools(world)
    tools.set_npc_disposition(id1, "friendly")
    tools.set_npc_disposition(id2, "neutral")
    result = tools.get_npc_relationships()
    assert result.success
    assert len(result.data["npcs"]) == 2
    names = {n["name"] for n in result.data["npcs"]}
    assert "Tavern Keeper" in names
    assert "City Guard" in names


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

def _setup_client(tmp_path, monkeypatch):
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

    meta = create_campaign("NpcAPITest", created_by="tester", seed=42)
    campaign = new_campaign_object("NpcAPITest", seed=42)
    save_campaign_world(meta.id, campaign)

    from src.backend.main import app
    client = TestClient(app)
    return client, meta.id, campaign


def test_get_npcs_endpoint_empty(tmp_path, monkeypatch):
    client, cid, _ = _setup_client(tmp_path, monkeypatch)
    resp = client.get(f"/api/campaigns/{cid}/npcs")
    assert resp.status_code == 200
    assert resp.json()["npcs"] == []


def test_get_npcs_endpoint_returns_known_npcs(tmp_path, monkeypatch):
    from src.backend.core.campaign_manager import load_campaign_world, save_campaign_world
    from src.backend.core.tools import WorldTools as WT

    client, cid, _ = _setup_client(tmp_path, monkeypatch)

    campaign = load_campaign_world(cid)
    tools = WT(campaign.world)
    root = _get_root(campaign.world)
    npc_result = tools.create_object(type="npc", parent_id=root.id, name="Innkeeper")
    npc_id = npc_result.data["id"]
    tools.set_npc_disposition(npc_id, "friendly", notes="Gave us free ale")
    save_campaign_world(cid, campaign)

    resp = client.get(f"/api/campaigns/{cid}/npcs")
    assert resp.status_code == 200
    npcs = resp.json()["npcs"]
    assert len(npcs) == 1
    assert npcs[0]["name"] == "Innkeeper"
    assert npcs[0]["disposition"] == "friendly"
    assert npcs[0]["notes"] == "Gave us free ale"


def test_get_npcs_endpoint_campaign_not_found(tmp_path, monkeypatch):
    client, _, _ = _setup_client(tmp_path, monkeypatch)
    resp = client.get("/api/campaigns/nonexistent-id/npcs")
    assert resp.status_code == 404
