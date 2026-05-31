"""Tests for random encounter roll during Travel mode."""

import pytest
from unittest.mock import patch

from src.backend.core.campaign_io import new_campaign_object
from src.backend.core.tools import WorldTools
from src.backend.core.travel_encounter import (
    TravelEncounterEngine,
    ENCOUNTER_DC,
    ENCOUNTER_TABLES,
    get_encounter_table,
)
from src.backend.models.world import World


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_world() -> World:
    campaign = new_campaign_object("TravelTest", seed=1)
    return campaign.world


# ---------------------------------------------------------------------------
# TravelEncounterEngine unit tests
# ---------------------------------------------------------------------------

def test_encounter_not_triggered_low_roll():
    """A roll below DC should not trigger an encounter."""
    engine = TravelEncounterEngine(seed=999)
    # Force the roll to be 1 (always misses)
    with patch.object(engine.rng, "randint", return_value=1):
        result = engine.roll_encounter("forest")
    assert result["triggered"] is False
    assert result["encounter"] is None
    assert result["d20_roll"] == 1


def test_encounter_triggered_high_roll():
    """A roll at or above DC should trigger an encounter."""
    engine = TravelEncounterEngine(seed=42)
    with patch.object(engine.rng, "randint", return_value=20):
        result = engine.roll_encounter("forest")
    assert result["triggered"] is True
    assert result["encounter"] is not None
    assert result["encounter"]["count"] >= 1
    assert "enemy_name" in result["encounter"]


def test_encounter_dc_boundary():
    """Exactly ENCOUNTER_DC should trigger."""
    engine = TravelEncounterEngine(seed=1)
    with patch.object(engine.rng, "randint", return_value=ENCOUNTER_DC):
        result = engine.roll_encounter("road")
    assert result["triggered"] is True


def test_encounter_dc_boundary_below():
    """One below ENCOUNTER_DC should not trigger."""
    engine = TravelEncounterEngine(seed=1)
    with patch.object(engine.rng, "randint", return_value=ENCOUNTER_DC - 1):
        result = engine.roll_encounter("road")
    assert result["triggered"] is False


def test_result_contains_required_keys():
    """Roll result always contains the expected schema keys."""
    engine = TravelEncounterEngine(seed=7)
    result = engine.roll_encounter("dungeon")
    for key in ("d20_roll", "encounter_dc", "triggered", "location_type", "encounter"):
        assert key in result, f"Missing key: {key}"


def test_encounter_data_structure():
    """Triggered encounter data has all required fields."""
    engine = TravelEncounterEngine(seed=42)
    with patch.object(engine.rng, "randint", return_value=20):
        result = engine.roll_encounter("dungeon")
    enc = result["encounter"]
    for key in ("enemy_type", "enemy_name", "cr", "count", "spawn_instructions"):
        assert key in enc, f"Missing encounter key: {key}"
    assert enc["count"] >= 1
    assert isinstance(enc["spawn_instructions"], str)


def test_location_type_propagated():
    """location_type in result matches what was passed in."""
    engine = TravelEncounterEngine(seed=3)
    result = engine.roll_encounter("mountain")
    assert result["location_type"] == "mountain"


# ---------------------------------------------------------------------------
# Encounter table lookup
# ---------------------------------------------------------------------------

def test_get_encounter_table_exact_match():
    """Known location types return their specific table."""
    for location in ("forest", "dungeon", "road", "mountain", "swamp", "plains", "desert", "urban"):
        table = get_encounter_table(location)
        assert table is ENCOUNTER_TABLES[location]


def test_get_encounter_table_fallback():
    """Unknown location types fall back to the default table."""
    table = get_encounter_table("volcano")
    assert table is ENCOUNTER_TABLES["default"]


def test_get_encounter_table_case_insensitive():
    """Location type lookup is case-insensitive."""
    table = get_encounter_table("Forest")
    assert table is ENCOUNTER_TABLES["forest"]


def test_get_encounter_table_empty_string():
    """Empty string falls back to default."""
    table = get_encounter_table("")
    assert table is ENCOUNTER_TABLES["default"]


def test_all_tables_have_entries():
    """Every table in ENCOUNTER_TABLES is non-empty."""
    for key, table in ENCOUNTER_TABLES.items():
        assert len(table) > 0, f"Table '{key}' is empty"


def test_all_entries_have_required_fields():
    """Every entry in every table has the required fields."""
    for key, table in ENCOUNTER_TABLES.items():
        for entry in table:
            for field in ("cr", "type", "name", "count"):
                assert field in entry, f"Table '{key}' entry missing field '{field}': {entry}"


# ---------------------------------------------------------------------------
# WorldTools.trigger_travel_encounter
# ---------------------------------------------------------------------------

def test_world_tools_no_encounter():
    """trigger_travel_encounter returns success with triggered=False on low roll."""
    world = _make_world()
    tools = WorldTools(world)
    # seed=0 produces low rolls in most cases; patch to be deterministic
    with patch("src.backend.core.travel_encounter.random.Random") as mock_rng_cls:
        mock_rng = mock_rng_cls.return_value
        mock_rng.randint.return_value = 1
        result = tools.trigger_travel_encounter(location_type="forest", seed=0)
    assert result.success is True
    assert result.data["triggered"] is False
    assert "uneventful" in result.message.lower()


def test_world_tools_encounter_triggered():
    """trigger_travel_encounter returns encounter data when triggered."""
    world = _make_world()
    tools = WorldTools(world)

    with patch("src.backend.core.travel_encounter.random.Random") as mock_rng_cls:
        mock_rng = mock_rng_cls.return_value
        # First randint call = d20 roll (>=DC), subsequent = count roll
        mock_rng.randint.side_effect = [20, 3]
        mock_rng.choice.return_value = {
            "cr": "1/4",
            "type": "NPC",
            "name": "Goblin",
            "count": "1d4",
        }
        result = tools.trigger_travel_encounter(location_type="forest", seed=42)

    assert result.success is True
    assert result.data["triggered"] is True
    enc = result.data["encounter"]
    assert enc["enemy_name"] == "Goblin"
    assert "Goblin" in result.message


def test_world_tools_default_location():
    """trigger_travel_encounter works with no location_type argument."""
    world = _make_world()
    tools = WorldTools(world)
    result = tools.trigger_travel_encounter()
    assert result.success is True
    assert "triggered" in result.data


def test_world_tools_all_location_types():
    """trigger_travel_encounter accepts all defined location types without error."""
    world = _make_world()
    tools = WorldTools(world)
    for loc in ("forest", "dungeon", "road", "mountain", "swamp", "plains", "desert", "urban", "default"):
        result = tools.trigger_travel_encounter(location_type=loc)
        assert result.success is True, f"Failed for location: {loc}"


def test_world_tools_unknown_location_type():
    """Unknown location type falls back gracefully to default table."""
    world = _make_world()
    tools = WorldTools(world)
    result = tools.trigger_travel_encounter(location_type="lava_tube")
    assert result.success is True
    assert result.data is not None


# ---------------------------------------------------------------------------
# Reproducibility with seed
# ---------------------------------------------------------------------------

def test_same_seed_same_result():
    """Same seed always produces the same outcome."""
    engine1 = TravelEncounterEngine(seed=12345)
    engine2 = TravelEncounterEngine(seed=12345)
    r1 = engine1.roll_encounter("forest")
    r2 = engine2.roll_encounter("forest")
    assert r1["d20_roll"] == r2["d20_roll"]
    assert r1["triggered"] == r2["triggered"]
    if r1["triggered"]:
        assert r1["encounter"]["enemy_name"] == r2["encounter"]["enemy_name"]
        assert r1["encounter"]["count"] == r2["encounter"]["count"]


def test_different_seeds_can_differ():
    """Different seeds can produce different results (not guaranteed but highly likely)."""
    results = set()
    for seed in range(50):
        engine = TravelEncounterEngine(seed=seed)
        r = engine.roll_encounter("road")
        results.add(r["triggered"])
    # Should have seen both True and False across 50 seeds
    assert len(results) == 2, "Expected both triggered and not-triggered results across 50 seeds"
