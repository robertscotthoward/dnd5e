"""Tests for admin PC creation with auto-rolled attributes.

Verifies that when creating a PC via the admin API, the abilities dict
from properties is saved verbatim to the world object.
"""

import random
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.backend.main import create_app
from src.backend.models.user import CampaignMeta
from src.backend.models.world import Object, World
from src.backend.models.game import Campaign
from src.backend.core.campaign_io import create_default_world

CAMPAIGN_ID = "admin-char-test"
FAKE_META = CampaignMeta(
    id=CAMPAIGN_ID,
    name="Admin Char Test",
    seed=1,
    created_by="admin",
    created_at="2026-01-01T00:00:00",
    updated_at="2026-01-01T00:00:00",
)
FAKE_ADMIN = MagicMock()
FAKE_ADMIN.user_id = "admin1"
FAKE_ADMIN.username = "admin"
FAKE_ADMIN.is_admin = True

ABILITIES = ["str", "dex", "con", "int", "wis", "chr"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roll_abilities_4d6_drop_lowest(seed: int) -> dict:
    """Mirror the rollAbilities() function in AdminWorldView.vue."""
    rng = random.Random(seed)

    def roll_one():
        dice = sorted([rng.randint(1, 6) for _ in range(4)])
        return sum(dice[1:])  # drop lowest

    return {ab: roll_one() for ab in ABILITIES}


def _make_campaign_with_party() -> Campaign:
    world = create_default_world("AdminCharTest")
    party = Object(
        id=world.next_id(),
        parent=7,
        type="party",
        name="Test Party",
        description="A test party",
        is_virtual=True,
    )
    world.add_object(party)
    return Campaign(name="AdminCharTest", seed=1, world=world)


@pytest.fixture
def client():
    app = create_app()
    with patch("src.backend.api.admin_routes.get_current_admin", return_value=FAKE_ADMIN):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ---------------------------------------------------------------------------
# Unit tests: 4d6-drop-lowest roll mechanics
# ---------------------------------------------------------------------------

class TestAdminRollAbilitiesMechanics:
    def test_each_ability_in_valid_range(self):
        scores = _roll_abilities_4d6_drop_lowest(42)
        for ab in ABILITIES:
            assert 3 <= scores[ab] <= 18, f"{ab}={scores[ab]} out of range"

    def test_all_six_abilities_present(self):
        scores = _roll_abilities_4d6_drop_lowest(99)
        assert set(scores.keys()) == set(ABILITIES)

    def test_deterministic_with_same_seed(self):
        s1 = _roll_abilities_4d6_drop_lowest(123)
        s2 = _roll_abilities_4d6_drop_lowest(123)
        assert s1 == s2

    def test_different_seeds_differ(self):
        s1 = _roll_abilities_4d6_drop_lowest(1)
        s2 = _roll_abilities_4d6_drop_lowest(2)
        assert s1 != s2

    def test_values_are_integers(self):
        scores = _roll_abilities_4d6_drop_lowest(7)
        for ab in ABILITIES:
            assert isinstance(scores[ab], int)


# ---------------------------------------------------------------------------
# Backend: admin create PC with abilities
# ---------------------------------------------------------------------------

class TestAdminCreatePCWithAbilities:
    def _post_pc(self, client, abilities: dict, parent_id: int = None):
        body = {
            "parent": parent_id,
            "type": "PC",
            "name": "Aria",
            "description": "A brave adventurer",
            "properties": {
                "race": "Elf",
                "class_type": "Wizard",
                "abilities": abilities,
            },
        }
        return client.post(
            f"/api/admin/world/{CAMPAIGN_ID}/objects",
            json=body,
        )

    def test_create_pc_returns_200(self, client):
        campaign = _make_campaign_with_party()
        abilities = _roll_abilities_4d6_drop_lowest(42)
        with patch("src.backend.api.admin_routes.load_campaign_world", return_value=campaign), \
             patch("src.backend.api.admin_routes.save_campaign_world"):
            res = self._post_pc(client, abilities)
        assert res.status_code == 200

    def test_abilities_echoed_in_response(self, client):
        campaign = _make_campaign_with_party()
        abilities = _roll_abilities_4d6_drop_lowest(42)
        with patch("src.backend.api.admin_routes.load_campaign_world", return_value=campaign), \
             patch("src.backend.api.admin_routes.save_campaign_world"):
            data = self._post_pc(client, abilities).json()
        assert data["properties"]["abilities"] == abilities

    def test_abilities_saved_to_world_object(self, client):
        campaign = _make_campaign_with_party()
        abilities = _roll_abilities_4d6_drop_lowest(77)
        saved_ref = {}

        def capture(campaign_id, camp):
            saved_ref["campaign"] = camp

        with patch("src.backend.api.admin_routes.load_campaign_world", return_value=campaign), \
             patch("src.backend.api.admin_routes.save_campaign_world", side_effect=capture):
            self._post_pc(client, abilities)

        saved = saved_ref["campaign"]
        pc_objs = [o for o in saved.world.objects.values() if o.type == "PC"]
        assert len(pc_objs) == 1
        assert pc_objs[0].properties["abilities"] == abilities

    def test_all_six_stat_keys_preserved(self, client):
        campaign = _make_campaign_with_party()
        abilities = _roll_abilities_4d6_drop_lowest(55)
        with patch("src.backend.api.admin_routes.load_campaign_world", return_value=campaign), \
             patch("src.backend.api.admin_routes.save_campaign_world"):
            data = self._post_pc(client, abilities).json()
        assert set(data["properties"]["abilities"].keys()) == set(ABILITIES)

    def test_stat_values_are_within_valid_range(self, client):
        campaign = _make_campaign_with_party()
        abilities = _roll_abilities_4d6_drop_lowest(333)
        with patch("src.backend.api.admin_routes.load_campaign_world", return_value=campaign), \
             patch("src.backend.api.admin_routes.save_campaign_world"):
            data = self._post_pc(client, abilities).json()
        for ab in ABILITIES:
            val = data["properties"]["abilities"][ab]
            assert 3 <= val <= 18, f"{ab}={val} out of valid range"

    def test_different_roll_seeds_produce_different_abilities(self, client):
        campaign_a = _make_campaign_with_party()
        campaign_b = _make_campaign_with_party()
        abilities_a = _roll_abilities_4d6_drop_lowest(1)
        abilities_b = _roll_abilities_4d6_drop_lowest(999)
        assert abilities_a != abilities_b

        with patch("src.backend.api.admin_routes.load_campaign_world", return_value=campaign_a), \
             patch("src.backend.api.admin_routes.save_campaign_world"):
            data_a = self._post_pc(client, abilities_a).json()

        with patch("src.backend.api.admin_routes.load_campaign_world", return_value=campaign_b), \
             patch("src.backend.api.admin_routes.save_campaign_world"):
            data_b = self._post_pc(client, abilities_b).json()

        assert data_a["properties"]["abilities"] != data_b["properties"]["abilities"]

    def test_pc_type_is_set_correctly(self, client):
        campaign = _make_campaign_with_party()
        abilities = _roll_abilities_4d6_drop_lowest(42)
        with patch("src.backend.api.admin_routes.load_campaign_world", return_value=campaign), \
             patch("src.backend.api.admin_routes.save_campaign_world"):
            data = self._post_pc(client, abilities).json()
        assert data["type"] == "PC"

    def test_race_and_class_preserved_in_properties(self, client):
        campaign = _make_campaign_with_party()
        abilities = _roll_abilities_4d6_drop_lowest(42)
        with patch("src.backend.api.admin_routes.load_campaign_world", return_value=campaign), \
             patch("src.backend.api.admin_routes.save_campaign_world"):
            data = self._post_pc(client, abilities).json()
        assert data["properties"]["race"] == "Elf"
        assert data["properties"]["class_type"] == "Wizard"
