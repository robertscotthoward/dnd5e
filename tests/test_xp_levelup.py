"""Tests for XP award and level-up flow."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.core.tools import (
    WorldTools,
    XP_THRESHOLDS,
    xp_level_for,
    xp_to_next_level,
    ASI_LEVELS,
    MAX_LEVEL,
)
from src.backend.models.world import Object


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(tmp_path: Path, name: str = "XPTest"):
    campaign = new_campaign_object(name, seed=42)
    world_path = tmp_path / name / "world.yaml"
    world_path.parent.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, world_path)
    return campaign


def _add_pc(campaign, name: str = "Hero", class_type: str = "Fighter") -> Object:
    party = campaign.world.get_parties()[0]
    pc_id = campaign.world.next_id()
    pc = Object(
        id=pc_id,
        parent=party.id,
        type="PC",
        name=name,
        properties={
            "race": "Human",
            "classes": [{"type": class_type, "level": 1}],
            "abilities": {"str": 15, "dex": 13, "con": 14, "int": 10, "wis": 12, "chr": 8},
            "hp": {"current": 12, "max": 12},
            "experience": 0,
        },
    )
    campaign.world.add_object(pc)
    return pc


# ---------------------------------------------------------------------------
# xp_level_for and xp_to_next_level helpers
# ---------------------------------------------------------------------------

def test_xp_level_for_level1():
    assert xp_level_for(0) == 1


def test_xp_level_for_exactly_at_threshold():
    assert xp_level_for(300) == 2
    assert xp_level_for(900) == 3
    assert xp_level_for(2700) == 4


def test_xp_level_for_between_thresholds():
    assert xp_level_for(150) == 1
    assert xp_level_for(500) == 2
    assert xp_level_for(1500) == 3


def test_xp_level_for_max():
    assert xp_level_for(355000) == 20
    assert xp_level_for(999999) == 20


def test_xp_to_next_level_level1():
    remaining = xp_to_next_level(0)
    assert remaining == XP_THRESHOLDS[2]  # 300


def test_xp_to_next_level_at_max():
    assert xp_to_next_level(355000) == 0


def test_xp_to_next_level_mid():
    # At 200 XP (level 1), need 100 more to reach level 2 (300)
    assert xp_to_next_level(200) == 100


# ---------------------------------------------------------------------------
# award_xp tool
# ---------------------------------------------------------------------------

def test_award_xp_basic(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    result = tools.award_xp(pc.id, 100)

    assert result.success
    assert result.data["new_xp"] == 100
    assert result.data["old_xp"] == 0
    assert result.data["new_level"] == 1
    assert result.data["level_up"] is None
    assert result.data["xp_to_next"] == 200  # 300 - 100


def test_award_xp_level_up(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    result = tools.award_xp(pc.id, 300)

    assert result.success
    assert result.data["new_level"] == 2
    assert result.data["level_up"] is not None
    lu = result.data["level_up"]
    assert lu["old_level"] == 1
    assert lu["new_level"] == 2
    assert lu["character_name"] == "Hero"
    assert lu["hit_die"] == 10  # Fighter


def test_award_xp_updates_class_level(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    tools.award_xp(pc.id, 300)

    obj = campaign.world.get_object(pc.id)
    assert obj.properties["classes"][0]["level"] == 2


def test_award_xp_no_level_up_below_threshold(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    result = tools.award_xp(pc.id, 299)

    assert result.data["new_level"] == 1
    assert result.data["level_up"] is None


def test_award_xp_invalid_amount(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    result = tools.award_xp(pc.id, 0)
    assert not result.success

    result2 = tools.award_xp(pc.id, -50)
    assert not result2.success


def test_award_xp_invalid_id(tmp_path):
    campaign = _make_campaign(tmp_path)
    tools = WorldTools(campaign.world)

    result = tools.award_xp(9999, 100)
    assert not result.success


def test_award_xp_cumulative(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    tools.award_xp(pc.id, 200)
    result = tools.award_xp(pc.id, 100)

    assert result.data["new_xp"] == 300
    assert result.data["new_level"] == 2


def test_award_xp_multiple_level_jumps(tmp_path):
    """Awarding a large XP block that skips multiple levels."""
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    # 6500 XP should bring a fresh character to level 5
    result = tools.award_xp(pc.id, 6500)

    assert result.data["new_level"] == 5
    assert result.data["level_up"] is not None
    obj = campaign.world.get_object(pc.id)
    assert obj.properties["classes"][0]["level"] == 5


# ---------------------------------------------------------------------------
# ASI level flag
# ---------------------------------------------------------------------------

def test_asi_flag_at_level_4(tmp_path):
    """Level-up to 4 must set has_asi=True."""
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    # Get to level 3 first
    tools.award_xp(pc.id, 900)
    # Now push to level 4
    result = tools.award_xp(pc.id, 1800)

    assert result.data["new_level"] == 4
    assert result.data["level_up"]["has_asi"] is True


def test_asi_flag_not_set_at_level_2(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)
    tools = WorldTools(campaign.world)

    result = tools.award_xp(pc.id, 300)

    assert result.data["new_level"] == 2
    assert result.data["level_up"]["has_asi"] is False


# ---------------------------------------------------------------------------
# API endpoint (via TestClient)
# ---------------------------------------------------------------------------

FAKE_META_XP = MagicMock()
FAKE_META_XP.turn_number = 0

FAKE_SESSION_XP = MagicMock()
FAKE_SESSION_XP.user_id = "u1"
FAKE_SESSION_XP.username = "tester"


@pytest.fixture
def xp_client(tmp_path):
    from fastapi.testclient import TestClient
    from src.backend.main import create_app

    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign)

    app = create_app()
    with patch("src.backend.api.campaign_routes.get_current_user", return_value=FAKE_SESSION_XP), \
         patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META_XP), \
         patch("src.backend.api.campaign_routes.load_campaign_world", return_value=campaign), \
         patch("src.backend.api.campaign_routes.save_campaign_world"), \
         patch("src.backend.api.campaign_routes.append_chat"), \
         patch("src.backend.api.campaign_routes.update_player_character"):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c, pc, campaign


def test_award_xp_endpoint(xp_client):
    """Smoke-test the award-xp REST endpoint."""
    client, pc, campaign = xp_client

    resp = client.post(
        "/api/campaigns/xp-test/award-xp",
        json={"character_id": pc.id, "amount": 300, "reason": "combat victory"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["new_xp"] == 300
    assert data["new_level"] == 2
    assert data["level_up"] is not None


def test_apply_level_up_endpoint(xp_client):
    """Smoke-test the apply-level-up REST endpoint."""
    client, pc, campaign = xp_client

    resp = client.post(
        f"/api/campaigns/xp-test/characters/{pc.id}/level-up",
        json={"hp_gain": 8, "asi_choices": {"str": 1, "dex": 1}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["hp"]["max"] == 20  # 12 + 8
    assert data["abilities"]["str"] == 16  # 15 + 1
    assert data["abilities"]["dex"] == 14  # 13 + 1
