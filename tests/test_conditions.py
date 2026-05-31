"""Tests for the conditions badge system."""

import json
import pytest
from pathlib import Path

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.core.campaign_manager import (
    get_players,
    save_raw_players,
)
from src.backend.core.tools import WorldTools
from src.backend.models.world import Object
from src.backend.models.user import CampaignPlayer, DeathSaves


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(tmp_path: Path, name: str = "CondTest"):
    campaign = new_campaign_object(name, seed=42)
    world_path = tmp_path / name / "world.yaml"
    world_path.parent.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, world_path)
    return campaign, tmp_path / name


def _add_pc(campaign, name: str = "Hero", hp: int = 10) -> Object:
    party = campaign.world.get_parties()[0]
    pc_id = campaign.world.next_id()
    pc = Object(
        id=pc_id,
        parent=party.id,
        type="PC",
        name=name,
        properties={
            "race": "Human",
            "classes": [{"type": "Fighter", "level": 1}],
            "abilities": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "chr": 10},
            "hp": {"current": hp, "max": hp},
            "experience": 0,
        },
    )
    campaign.world.add_object(pc)
    return pc


def _write_player(campaign_dir: Path, user_id: str, username: str, char_id: int):
    players_file = campaign_dir / "players.json"
    data = {
        "players": [
            {
                "user_id": user_id,
                "username": username,
                "character_object_id": char_id,
                "character_name": None,
                "race": None,
                "class_type": None,
                "hp_current": 0,
                "hp_max": 0,
                "encumbrance_current": 0.0,
                "encumbrance_max": 150.0,
                "joined_at": "2026-01-01T00:00:00",
                "last_seen": None,
            }
        ]
    }
    with open(players_file, "w") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# set_object_property stores conditions list
# ---------------------------------------------------------------------------

def test_set_conditions_via_tool(tmp_path):
    """DM agent can set a conditions list on a PC via set_object_property."""
    campaign, _ = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    result = tools.set_object_property(pc.id, "conditions", ["Poisoned", "Prone"])

    assert result.success
    obj = campaign.world.get_object(pc.id)
    assert obj.properties["conditions"] == ["Poisoned", "Prone"]


def test_set_conditions_overwrites_previous(tmp_path):
    """Setting conditions replaces the previous list."""
    campaign, _ = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    pc.properties["conditions"] = ["Blinded"]
    tools = WorldTools(campaign.world)

    tools.set_object_property(pc.id, "conditions", ["Restrained"])

    obj = campaign.world.get_object(pc.id)
    assert obj.properties["conditions"] == ["Restrained"]
    assert "Blinded" not in obj.properties["conditions"]


def test_clear_conditions(tmp_path):
    """Conditions can be cleared by setting an empty list."""
    campaign, _ = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    pc.properties["conditions"] = ["Stunned"]
    tools = WorldTools(campaign.world)

    result = tools.set_object_property(pc.id, "conditions", [])

    assert result.success
    obj = campaign.world.get_object(pc.id)
    assert obj.properties["conditions"] == []


def test_set_conditions_unknown_object(tmp_path):
    """set_object_property fails gracefully for a missing object."""
    campaign, _ = _make_campaign(tmp_path)
    tools = WorldTools(campaign.world)

    result = tools.set_object_property(9999, "conditions", ["Poisoned"])

    assert not result.success


# ---------------------------------------------------------------------------
# get_players enriches conditions from world object
# ---------------------------------------------------------------------------

def test_get_players_exposes_conditions(tmp_path, monkeypatch):
    """CampaignPlayer.conditions is populated from world object properties."""
    campaign, campaign_dir = _make_campaign(tmp_path)
    pc = _add_pc(campaign, name="Thorn")
    pc.properties["conditions"] = ["Poisoned", "Prone"]
    save_campaign(campaign, campaign_dir / "world.yaml")
    _write_player(campaign_dir, "u1", "alice", pc.id)

    monkeypatch.setattr(
        "src.backend.core.campaign_manager.campaign_path",
        lambda cid: campaign_dir,
    )

    players = get_players("CondTest")
    assert len(players) == 1
    assert "Poisoned" in players[0].conditions
    assert "Prone" in players[0].conditions


def test_get_players_empty_conditions_when_none_set(tmp_path, monkeypatch):
    """CampaignPlayer.conditions is empty when no conditions are on the world object."""
    campaign, campaign_dir = _make_campaign(tmp_path)
    pc = _add_pc(campaign, name="Bard")
    save_campaign(campaign, campaign_dir / "world.yaml")
    _write_player(campaign_dir, "u2", "bob", pc.id)

    monkeypatch.setattr(
        "src.backend.core.campaign_manager.campaign_path",
        lambda cid: campaign_dir,
    )

    players = get_players("CondTest")
    assert players[0].conditions == []


def test_get_players_unconscious_auto_added(tmp_path, monkeypatch):
    """'unconscious' is appended automatically when HP is 0."""
    campaign, campaign_dir = _make_campaign(tmp_path)
    pc = _add_pc(campaign, name="Fallen", hp=10)
    pc.properties["hp"]["current"] = 0
    pc.properties["conditions"] = ["Prone"]
    save_campaign(campaign, campaign_dir / "world.yaml")
    _write_player(campaign_dir, "u3", "carol", pc.id)

    monkeypatch.setattr(
        "src.backend.core.campaign_manager.campaign_path",
        lambda cid: campaign_dir,
    )

    players = get_players("CondTest")
    assert "unconscious" in players[0].conditions
    assert "Prone" in players[0].conditions


def test_get_players_unconscious_not_duplicated(tmp_path, monkeypatch):
    """'unconscious' is not added twice if already in conditions list."""
    campaign, campaign_dir = _make_campaign(tmp_path)
    pc = _add_pc(campaign, name="Ghost", hp=10)
    pc.properties["hp"]["current"] = 0
    pc.properties["conditions"] = ["unconscious"]
    save_campaign(campaign, campaign_dir / "world.yaml")
    _write_player(campaign_dir, "u4", "dave", pc.id)

    monkeypatch.setattr(
        "src.backend.core.campaign_manager.campaign_path",
        lambda cid: campaign_dir,
    )

    players = get_players("CondTest")
    assert players[0].conditions.count("unconscious") == 1


# ---------------------------------------------------------------------------
# CampaignPlayer model conditions field
# ---------------------------------------------------------------------------

def test_campaign_player_conditions_default_empty():
    player = CampaignPlayer(
        user_id="u1",
        username="test",
        joined_at="2026-01-01",
    )
    assert player.conditions == []


def test_campaign_player_conditions_serialization():
    player = CampaignPlayer(
        user_id="u1",
        username="test",
        conditions=["Blinded", "Restrained"],
        joined_at="2026-01-01",
    )
    d = player.model_dump(mode="json")
    assert d["conditions"] == ["Blinded", "Restrained"]


def test_campaign_player_multiple_conditions():
    player = CampaignPlayer(
        user_id="u1",
        username="test",
        conditions=["Poisoned", "Prone", "Restrained", "Blinded"],
        joined_at="2026-01-01",
    )
    assert len(player.conditions) == 4
    assert "Poisoned" in player.conditions
