"""Tests for death saving throw mechanics."""

import pytest
from pathlib import Path
from unittest.mock import patch

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.core.tools import WorldTools
from src.backend.models.world import Object
from src.backend.models.user import CampaignPlayer, DeathSaves


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(tmp_path: Path, name: str = "DSTest"):
    campaign = new_campaign_object(name, seed=1)
    world_path = tmp_path / name / "world.yaml"
    world_path.parent.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, world_path)
    return campaign


def _add_pc(campaign, name: str = "Hero", hp_current: int = 10, hp_max: int = 10) -> Object:
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
            "abilities": {"str": 15, "dex": 13, "con": 14, "int": 10, "wis": 12, "chr": 8},
            "hp": {"current": hp_current, "max": hp_max},
            "experience": 0,
        },
    )
    campaign.world.add_object(pc)
    return pc


# ---------------------------------------------------------------------------
# add_hp initializes death_saves when HP reaches 0
# ---------------------------------------------------------------------------

def test_add_hp_to_zero_initializes_death_saves(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=5, hp_max=10)
    tools = WorldTools(campaign.world)

    result = tools.add_hp(pc.id, -5)  # Bring to 0

    assert result.success
    assert result.data["new_hp"] == 0
    obj = campaign.world.get_object(pc.id)
    ds = obj.properties.get("death_saves")
    assert ds is not None
    assert ds["successes"] == 0
    assert ds["failures"] == 0


def test_add_hp_already_zero_does_not_reset_death_saves(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=0, hp_max=10)
    pc.properties["death_saves"] = {"successes": 2, "failures": 1}
    tools = WorldTools(campaign.world)

    tools.add_hp(pc.id, -1)  # damage while already at 0 (stays 0)

    obj = campaign.world.get_object(pc.id)
    ds = obj.properties.get("death_saves")
    # Death saves must NOT be reset because old_hp was already 0
    assert ds["successes"] == 2


# ---------------------------------------------------------------------------
# roll_death_save — basic success / failure
# ---------------------------------------------------------------------------

def test_roll_death_save_success(tmp_path):
    """Roll >= 10 counts as a success."""
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=0, hp_max=10)
    tools = WorldTools(campaign.world)

    with patch("src.backend.core.tools.random.randint", return_value=15):
        result = tools.roll_death_save(pc.id)

    assert result.success
    assert result.data["roll"] == 15
    assert result.data["result"] == "success"
    assert result.data["successes"] == 1
    assert result.data["failures"] == 0
    assert not result.data["stable"]
    assert not result.data["dead"]


def test_roll_death_save_failure(tmp_path):
    """Roll < 10 counts as a failure."""
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=0, hp_max=10)
    tools = WorldTools(campaign.world)

    with patch("src.backend.core.tools.random.randint", return_value=5):
        result = tools.roll_death_save(pc.id)

    assert result.success
    assert result.data["result"] == "failure"
    assert result.data["failures"] == 1
    assert result.data["successes"] == 0
    assert not result.data["dead"]


def test_roll_death_save_natural_20_instant_stable(tmp_path):
    """Natural 20 immediately stabilizes the character."""
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=0, hp_max=10)
    tools = WorldTools(campaign.world)

    with patch("src.backend.core.tools.random.randint", return_value=20):
        result = tools.roll_death_save(pc.id)

    assert result.success
    assert result.data["stable"] is True
    assert result.data["dead"] is False
    assert result.data["successes"] == 3


def test_roll_death_save_three_successes_stable(tmp_path):
    """Three successful saves stabilizes the character."""
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=0, hp_max=10)
    pc.properties["death_saves"] = {"successes": 2, "failures": 0}
    tools = WorldTools(campaign.world)

    with patch("src.backend.core.tools.random.randint", return_value=12):
        result = tools.roll_death_save(pc.id)

    assert result.data["successes"] == 3
    assert result.data["stable"] is True
    assert result.data["dead"] is False


def test_roll_death_save_two_failures_dead(tmp_path):
    """Two failed saves kills the character."""
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=0, hp_max=10)
    pc.properties["death_saves"] = {"successes": 0, "failures": 1}
    tools = WorldTools(campaign.world)

    with patch("src.backend.core.tools.random.randint", return_value=3):
        result = tools.roll_death_save(pc.id)

    assert result.data["failures"] == 2
    assert result.data["dead"] is True
    assert result.data["stable"] is False


# ---------------------------------------------------------------------------
# roll_death_save — guard conditions
# ---------------------------------------------------------------------------

def test_roll_death_save_fails_when_hp_positive(tmp_path):
    """Cannot roll death save when PC is alive."""
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=5, hp_max=10)
    tools = WorldTools(campaign.world)

    result = tools.roll_death_save(pc.id)

    assert not result.success
    assert "not unconscious" in result.message.lower()


def test_roll_death_save_fails_for_unknown_id(tmp_path):
    campaign = _make_campaign(tmp_path)
    tools = WorldTools(campaign.world)

    result = tools.roll_death_save(9999)

    assert not result.success


# ---------------------------------------------------------------------------
# Persistence: death_saves stored in world object
# ---------------------------------------------------------------------------

def test_death_saves_persisted_in_properties(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=0, hp_max=10)
    tools = WorldTools(campaign.world)

    with patch("src.backend.core.tools.random.randint", return_value=15):
        tools.roll_death_save(pc.id)

    obj = campaign.world.get_object(pc.id)
    assert obj.properties["death_saves"]["successes"] == 1


def test_death_saves_accumulate_across_rolls(tmp_path):
    campaign = _make_campaign(tmp_path)
    pc = _add_pc(campaign, hp_current=0, hp_max=10)
    tools = WorldTools(campaign.world)

    with patch("src.backend.core.tools.random.randint", return_value=12):
        tools.roll_death_save(pc.id)
    with patch("src.backend.core.tools.random.randint", return_value=4):
        tools.roll_death_save(pc.id)

    obj = campaign.world.get_object(pc.id)
    ds = obj.properties["death_saves"]
    assert ds["successes"] == 1
    assert ds["failures"] == 1


# ---------------------------------------------------------------------------
# CampaignPlayer death_saves field
# ---------------------------------------------------------------------------

def test_death_saves_model_defaults():
    ds = DeathSaves()
    assert ds.successes == 0
    assert ds.failures == 0


def test_campaign_player_death_saves_serialization():
    """CampaignPlayer serializes death_saves correctly."""
    player = CampaignPlayer(
        user_id="u1",
        username="bob",
        hp_current=0,
        hp_max=10,
        death_saves=DeathSaves(successes=1, failures=1),
        joined_at="2026-01-01",
    )
    d = player.model_dump(mode="json")
    assert d["death_saves"]["successes"] == 1
    assert d["death_saves"]["failures"] == 1


def test_health_status_dead_when_two_failures():
    """health_status computed field returns 'dead' with 2+ failures."""
    player = CampaignPlayer(
        user_id="u1",
        username="bob",
        hp_current=0,
        hp_max=10,
        death_saves=DeathSaves(successes=0, failures=2),
        joined_at="2026-01-01",
    )
    assert player.health_status == "dead"


def test_health_status_unconscious_with_one_failure():
    """health_status is 'unconscious' with only one failure."""
    player = CampaignPlayer(
        user_id="u1",
        username="bob",
        hp_current=0,
        hp_max=10,
        death_saves=DeathSaves(successes=0, failures=1),
        joined_at="2026-01-01",
    )
    assert player.health_status == "unconscious"
