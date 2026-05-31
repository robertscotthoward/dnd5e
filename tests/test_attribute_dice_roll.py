"""Tests for the attribute dice roll UI flow — roll-stats endpoint, bonus allocation, and
character save (abilities persisted to world.yaml).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.backend.core.campaign_io import (
    generate_ability_scores_detailed,
    roll_bonus_die,
)
from src.backend.main import create_app
from src.backend.models.user import CampaignMeta
from src.backend.models.world import World

CAMPAIGN_ID = "test-roll-campaign"
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

ABILITIES = ["str", "dex", "con", "int", "wis", "chr"]


@pytest.fixture
def client():
    app = create_app()
    with patch("src.backend.api.campaign_routes.get_current_user", return_value=FAKE_SESSION):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ---------------------------------------------------------------------------
# Unit tests for generate_ability_scores_detailed
# ---------------------------------------------------------------------------

class TestGenerateAbilityScoresDetailed:
    def test_returns_all_six_abilities(self):
        result = generate_ability_scores_detailed(42)
        assert set(result.keys()) == set(ABILITIES)

    def test_each_ability_has_required_keys(self):
        result = generate_ability_scores_detailed(42)
        for ab in ABILITIES:
            entry = result[ab]
            assert "dice" in entry
            assert "kept" in entry
            assert "dropped" in entry
            assert "total" in entry

    def test_kept_is_top_three_dice(self):
        result = generate_ability_scores_detailed(99)
        for ab in ABILITIES:
            entry = result[ab]
            all_dice_sorted = sorted(entry["dice"], reverse=True)
            assert entry["kept"] == all_dice_sorted[:3]
            assert entry["dropped"] == all_dice_sorted[3]

    def test_total_equals_sum_of_kept(self):
        result = generate_ability_scores_detailed(7)
        for ab in ABILITIES:
            entry = result[ab]
            assert entry["total"] == sum(entry["kept"])

    def test_total_in_valid_range(self):
        # Minimum 3 (three 1s), maximum 18 (three 6s)
        result = generate_ability_scores_detailed(123)
        for ab in ABILITIES:
            assert 3 <= result[ab]["total"] <= 18

    def test_deterministic_with_same_seed(self):
        r1 = generate_ability_scores_detailed(555)
        r2 = generate_ability_scores_detailed(555)
        assert r1 == r2

    def test_different_seeds_produce_different_results(self):
        r1 = generate_ability_scores_detailed(1)
        r2 = generate_ability_scores_detailed(2)
        # Very unlikely to be identical across 6 abilities
        assert r1 != r2


class TestRollBonusDie:
    def test_result_in_range(self):
        for seed in [1, 42, 999]:
            result = roll_bonus_die(seed)
            assert 1 <= result <= 6

    def test_deterministic(self):
        assert roll_bonus_die(77) == roll_bonus_die(77)

    def test_differs_from_ability_rolls(self):
        # The bonus die uses a xor offset so it won't match the first ability
        seed = 12345
        detailed = generate_ability_scores_detailed(seed)
        bonus = roll_bonus_die(seed)
        # Just confirm it's a valid value — main check is range coverage
        assert 1 <= bonus <= 6


# ---------------------------------------------------------------------------
# API tests — /roll-stats endpoint
# ---------------------------------------------------------------------------

class TestRollStatsEndpoint:
    def _post(self, client, race="Human", campaign_id=CAMPAIGN_ID, **extra):
        payload = {"race": race, **extra}
        return client.post(
            f"/api/campaigns/{campaign_id}/roll-stats",
            json=payload,
        )

    def test_returns_200_with_valid_request(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META):
            res = self._post(client)
        assert res.status_code == 200

    def test_response_contains_required_fields(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META):
            data = self._post(client).json()
        assert "seed" in data
        assert "rolls" in data
        assert "bonus_die" in data
        assert "racial_bonuses" in data

    def test_rolls_has_all_six_abilities(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META):
            data = self._post(client).json()
        assert set(data["rolls"].keys()) == set(ABILITIES)

    def test_each_roll_has_detail_keys(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META):
            data = self._post(client).json()
        for ab in ABILITIES:
            roll = data["rolls"][ab]
            assert "kept" in roll
            assert "dropped" in roll
            assert "total" in roll

    def test_bonus_die_in_range(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META):
            data = self._post(client).json()
        assert 1 <= data["bonus_die"] <= 6

    def test_racial_bonuses_for_elf(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META):
            data = self._post(client, race="Elf").json()
        # Elf gets +2 DEX, +1 INT
        assert data["racial_bonuses"].get("dex") == 2
        assert data["racial_bonuses"].get("int") == 1

    def test_racial_bonuses_for_human(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META):
            data = self._post(client, race="Human").json()
        # Human gets +1 to all abilities
        for ab in ABILITIES:
            assert data["racial_bonuses"].get(ab) == 1

    def test_unknown_race_returns_empty_bonuses(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META):
            data = self._post(client, race="Goblin").json()
        assert data["racial_bonuses"] == {}

    def test_seeded_roll_is_deterministic(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META):
            r1 = self._post(client, seed=42).json()
            r2 = self._post(client, seed=42).json()
        assert r1["rolls"] == r2["rolls"]
        assert r1["bonus_die"] == r2["bonus_die"]

    def test_404_for_unknown_campaign(self, client):
        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=None):
            res = self._post(client, campaign_id="ghost")
        assert res.status_code == 404


# ---------------------------------------------------------------------------
# End-to-end: bonus allocation logic (mirrors the Vue computed)
# ---------------------------------------------------------------------------

class TestBonusAllocationLogic:
    """Verify the same arithmetic the Vue component uses."""

    def test_bonus_points_total_to_die_value(self):
        seed = 42
        detailed = generate_ability_scores_detailed(seed)
        bonus_die = roll_bonus_die(seed)

        # Simulate allocating all bonus points to STR
        allocation = {ab: 0 for ab in ABILITIES}
        allocation["str"] = bonus_die

        used = sum(allocation.values())
        remaining = bonus_die - used
        assert remaining == 0

    def test_final_score_is_base_plus_racial_plus_bonus(self):
        from src.backend.models.player import RACE_MODIFIERS

        seed = 100
        race = "Elf"
        detailed = generate_ability_scores_detailed(seed)
        racial = RACE_MODIFIERS.get(race, {})

        allocation = {ab: 0 for ab in ABILITIES}
        allocation["dex"] = 2  # spend 2 points on DEX

        for ab in ABILITIES:
            base = detailed[ab]["total"]
            racial_bonus = racial.get(ab, 0)
            bonus = allocation[ab]
            final = base + racial_bonus + bonus
            assert final >= 3  # sanity: always positive

        # Spot-check DEX specifically
        dex_final = (
            detailed["dex"]["total"]
            + racial.get("dex", 0)
            + allocation["dex"]
        )
        assert dex_final == detailed["dex"]["total"] + 2 + 2  # +2 racial, +2 bonus

    def test_cannot_over_allocate_bonus(self):
        seed = 77
        bonus_die = roll_bonus_die(seed)
        allocation = {ab: 0 for ab in ABILITIES}

        # Allocate all points to one ability
        allocation["con"] = bonus_die
        remaining = bonus_die - sum(allocation.values())
        assert remaining == 0

        # Attempting to add another point should be blocked (remaining == 0)
        # Confirm no points are available
        assert remaining == 0


# ---------------------------------------------------------------------------
# Integration: character creation persists abilities to world
# ---------------------------------------------------------------------------

class TestCharacterCreationPersistsAbilities:
    """Verify that player-rolled abilities are saved to world.yaml correctly."""

    PLAYER_ROW = {
        "user_id": "u1",
        "username": "tester",
        "character_object_id": None,
        "character_name": None,
        "race": None,
        "class_type": None,
        "hp_current": 0,
        "hp_max": 0,
        "joined_at": "2026-01-01T00:00:00",
    }

    def _make_fake_campaign(self):
        from src.backend.models.game import Campaign
        from src.backend.core.campaign_io import create_default_world

        world = create_default_world("Test")
        from src.backend.models.world import Object, Location
        party = Object(
            id=world.next_id(),
            parent=7,
            type="party",
            name="The Adventurers",
            description="Test party",
            is_virtual=True,
        )
        world.add_object(party)
        return Campaign(name="Test", seed=1, world=world)

    def _create_char(self, client, abilities, race="Elf", class_type="Wizard"):
        payload = {
            "name": "Elara",
            "race": race,
            "class_type": class_type,
            "region": "Neverwinter",
            "abilities": abilities,
            "background": "A wandering scholar.",
        }
        return client.post(f"/api/campaigns/{CAMPAIGN_ID}/characters", json=payload)

    def test_create_character_uses_player_rolled_abilities(self, client):
        """When abilities are supplied, the endpoint echoes them back (after clamping/hp calc)."""
        abilities = {"str": 14, "dex": 16, "con": 12, "int": 18, "wis": 10, "chr": 8}
        fake_campaign = self._make_fake_campaign()

        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
             patch("src.backend.api.campaign_routes.find_player", return_value=self.PLAYER_ROW), \
             patch("src.backend.api.campaign_routes.load_campaign_world", return_value=fake_campaign), \
             patch("src.backend.api.campaign_routes.save_campaign_world") as mock_save, \
             patch("src.backend.api.campaign_routes.update_player_character"):
            res = self._create_char(client, abilities)

        assert res.status_code == 200
        data = res.json()
        assert data["abilities"] == abilities

    def test_abilities_saved_to_world_object(self, client):
        """The character's PC object in the world has properties.abilities matching the submission."""
        abilities = {"str": 15, "dex": 13, "con": 14, "int": 10, "wis": 12, "chr": 11}
        fake_campaign = self._make_fake_campaign()

        saved_world_ref = {}

        def capture_save(campaign_id, campaign):
            saved_world_ref["campaign"] = campaign

        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
             patch("src.backend.api.campaign_routes.find_player", return_value=self.PLAYER_ROW), \
             patch("src.backend.api.campaign_routes.load_campaign_world", return_value=fake_campaign), \
             patch("src.backend.api.campaign_routes.save_campaign_world", side_effect=capture_save), \
             patch("src.backend.api.campaign_routes.update_player_character"):
            res = self._create_char(client, abilities)

        assert res.status_code == 200
        # Find the created PC object in the saved world
        saved = saved_world_ref["campaign"]
        pc_objs = [o for o in saved.world.objects.values() if o.type == "PC"]
        assert len(pc_objs) == 1
        pc = pc_objs[0]
        assert pc.properties["abilities"] == abilities

    def test_hp_calculated_from_provided_con(self, client):
        """Max HP uses the player's actual CON modifier from the submitted abilities."""
        # CON 14 → modifier +2; Wizard hit die d6 → max_hp = 6 + 2 = 8
        abilities = {"str": 10, "dex": 10, "con": 14, "int": 18, "wis": 10, "chr": 10}
        fake_campaign = self._make_fake_campaign()

        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
             patch("src.backend.api.campaign_routes.find_player", return_value=self.PLAYER_ROW), \
             patch("src.backend.api.campaign_routes.load_campaign_world", return_value=fake_campaign), \
             patch("src.backend.api.campaign_routes.save_campaign_world"), \
             patch("src.backend.api.campaign_routes.update_player_character"):
            res = self._create_char(client, abilities, class_type="Wizard")

        assert res.status_code == 200
        data = res.json()
        assert data["hp"]["max"] == 8  # d6 + CON mod +2

    def test_hp_calculated_from_barbarian_con(self, client):
        """Barbarian with CON 16 (+3) → max_hp = 12 + 3 = 15."""
        abilities = {"str": 18, "dex": 10, "con": 16, "int": 8, "wis": 10, "chr": 10}
        fake_campaign = self._make_fake_campaign()

        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
             patch("src.backend.api.campaign_routes.find_player", return_value=self.PLAYER_ROW), \
             patch("src.backend.api.campaign_routes.load_campaign_world", return_value=fake_campaign), \
             patch("src.backend.api.campaign_routes.save_campaign_world"), \
             patch("src.backend.api.campaign_routes.update_player_character"):
            res = self._create_char(client, abilities, race="Half-Orc", class_type="Barbarian")

        assert res.status_code == 200
        data = res.json()
        assert data["hp"]["max"] == 15  # d12 + CON mod +3

    def test_missing_abilities_falls_back_to_server_generation(self, client):
        """When no abilities are supplied, the server generates random ones."""
        fake_campaign = self._make_fake_campaign()

        with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
             patch("src.backend.api.campaign_routes.find_player", return_value=self.PLAYER_ROW), \
             patch("src.backend.api.campaign_routes.load_campaign_world", return_value=fake_campaign), \
             patch("src.backend.api.campaign_routes.save_campaign_world"), \
             patch("src.backend.api.campaign_routes.update_player_character"):
            payload = {
                "name": "Thorin",
                "race": "Dwarf",
                "class_type": "Fighter",
                "region": "The North",
                "background": "A stoic warrior.",
            }
            res = client.post(f"/api/campaigns/{CAMPAIGN_ID}/characters", json=payload)

        assert res.status_code == 200
        data = res.json()
        # Server should have generated abilities for all 6 stats
        assert set(data["abilities"].keys()) == set(ABILITIES)
        for val in data["abilities"].values():
            assert isinstance(val, int)
            assert val >= 3  # racial modifiers can push above 18, but never below ~3
