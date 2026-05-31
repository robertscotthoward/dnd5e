"""Tests for the day/night cycle feature."""

import pytest

from src.backend.core.time_cycle import (
    advance_time,
    has_darkvision,
    is_night_hour,
    perception_disadvantage,
    time_description,
    NIGHT_START,
    NIGHT_END,
    HOURS_PER_TURN,
)
from src.backend.models.user import CampaignMeta
from src.backend.core.campaign_io import new_campaign_object


# ---------------------------------------------------------------------------
# is_night_hour
# ---------------------------------------------------------------------------

def test_is_night_hour_midnight():
    assert is_night_hour(0) is True


def test_is_night_hour_night_start():
    assert is_night_hour(NIGHT_START) is True


def test_is_night_hour_before_night_start():
    assert is_night_hour(NIGHT_START - 1) is False


def test_is_night_hour_dawn_boundary():
    # NIGHT_END is exclusive — 6 AM is dawn (daylight)
    assert is_night_hour(NIGHT_END) is False


def test_is_night_hour_pre_dawn():
    assert is_night_hour(NIGHT_END - 1) is True


def test_is_night_hour_midday():
    assert is_night_hour(12) is False


# ---------------------------------------------------------------------------
# time_description
# ---------------------------------------------------------------------------

def test_time_description_night():
    assert time_description(0) == "night"
    assert time_description(NIGHT_START) == "night"


def test_time_description_dawn():
    assert time_description(6) == "dawn"


def test_time_description_morning():
    assert time_description(9) == "morning"


def test_time_description_midday():
    assert time_description(13) == "midday"


def test_time_description_afternoon():
    assert time_description(15) == "afternoon"


def test_time_description_dusk():
    assert time_description(18) == "dusk"


# ---------------------------------------------------------------------------
# advance_time
# ---------------------------------------------------------------------------

def test_advance_time_basic():
    result = advance_time(day_number=1, hour_of_day=9, hours=1)
    assert result["day_number"] == 1
    assert result["hour_of_day"] == 10
    assert result["is_night"] is False


def test_advance_time_into_night():
    result = advance_time(day_number=1, hour_of_day=19, hours=1)
    assert result["hour_of_day"] == 20
    assert result["is_night"] is True


def test_advance_time_midnight_wrap():
    result = advance_time(day_number=1, hour_of_day=23, hours=1)
    assert result["day_number"] == 2
    assert result["hour_of_day"] == 0
    assert result["is_night"] is True


def test_advance_time_multi_day():
    result = advance_time(day_number=3, hour_of_day=22, hours=5)
    # 22 + 5 = 27 hours → day 4, hour 3
    assert result["day_number"] == 4
    assert result["hour_of_day"] == 3
    assert result["is_night"] is True


def test_advance_time_no_day_increment():
    result = advance_time(day_number=5, hour_of_day=8, hours=HOURS_PER_TURN)
    assert result["day_number"] == 5
    assert result["hour_of_day"] == 8 + HOURS_PER_TURN


def test_advance_time_includes_description():
    result = advance_time(day_number=1, hour_of_day=9, hours=1)
    assert "time_description" in result
    assert result["time_description"] == time_description(10)


# ---------------------------------------------------------------------------
# has_darkvision
# ---------------------------------------------------------------------------

def test_has_darkvision_elf():
    assert has_darkvision("elf") is True


def test_has_darkvision_dwarf():
    assert has_darkvision("dwarf") is True


def test_has_darkvision_tiefling():
    assert has_darkvision("tiefling") is True


def test_has_darkvision_human():
    assert has_darkvision("human") is False


def test_has_darkvision_case_insensitive():
    assert has_darkvision("Elf") is True
    assert has_darkvision("HALF-ORC") is True


def test_has_darkvision_halfling():
    assert has_darkvision("halfling") is False


# ---------------------------------------------------------------------------
# perception_disadvantage
# ---------------------------------------------------------------------------

def test_no_disadvantage_during_day():
    assert perception_disadvantage(is_night=False, race="human") is False


def test_no_disadvantage_night_darkvision():
    assert perception_disadvantage(is_night=True, race="elf") is False


def test_disadvantage_night_no_darkvision():
    assert perception_disadvantage(is_night=True, race="human") is True


def test_disadvantage_night_halfling():
    assert perception_disadvantage(is_night=True, race="halfling") is True


# ---------------------------------------------------------------------------
# CampaignMeta fields
# ---------------------------------------------------------------------------

def test_campaign_meta_defaults():
    meta = CampaignMeta(
        id="test",
        name="Test",
        created_at="2026-01-01",
        updated_at="2026-01-01",
    )
    assert meta.day_number == 1
    assert meta.hour_of_day == 9
    assert meta.is_night is False


def test_campaign_meta_serializes_time():
    meta = CampaignMeta(
        id="test",
        name="Test",
        created_at="2026-01-01",
        updated_at="2026-01-01",
        day_number=3,
        hour_of_day=22,
        is_night=True,
    )
    d = meta.model_dump()
    assert d["day_number"] == 3
    assert d["hour_of_day"] == 22
    assert d["is_night"] is True


# ---------------------------------------------------------------------------
# get_visible_world night perception penalty
# ---------------------------------------------------------------------------

def _make_world_with_two_chars():
    """Return a World with two sibling characters placed at [0,0,0]."""
    campaign = new_campaign_object("NightTest", seed=1)
    world = campaign.world
    pcs = world.get_pcs()
    if len(pcs) < 2:
        pytest.skip("Need at least 2 PCs to test visibility")
    return world, pcs[0], pcs[1]


def test_night_penalty_reduces_passive_perception():
    """Non-darkvision race at night has lower passive perception (cannot see stealth objects as easily)."""
    world, observer, target = _make_world_with_two_chars()
    # Set a stealth DC of 13 on the target — visible in daylight (PP=10 >= 13? no, let's use 12)
    stealth_dc = 12  # base PP 10 + 0 bonus = 10, can't beat 12 even in day, adjust
    # Use stealth_dc=10: should be visible in day (PP=10 >= 10) but hidden at night (PP=5 < 10)
    target.properties["stealth_dc"] = 10
    # Daytime: observer with 0 bonus can see (PP=10 >= 10)
    day_world = world.get_visible_world(observer.id, perception_bonus=0, is_night=False, observer_race="human")
    # Nighttime with non-darkvision: PP = 10 - 5 = 5, cannot beat DC 10
    night_world = world.get_visible_world(observer.id, perception_bonus=0, is_night=True, observer_race="human")
    assert target.id in day_world.objects
    assert target.id not in night_world.objects


def test_night_no_penalty_for_darkvision():
    """Darkvision race does not suffer the night perception penalty."""
    world, observer, target = _make_world_with_two_chars()
    target.properties["stealth_dc"] = 10
    # Elf (darkvision): PP = 10 + 0 - 0 = 10, beats DC 10 even at night
    night_world = world.get_visible_world(observer.id, perception_bonus=0, is_night=True, observer_race="elf")
    assert target.id in night_world.objects
