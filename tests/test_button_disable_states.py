"""Tests for button disable state logic driven by character conditions.

Verifies that:
  1. CampaignPlayer.conditions is populated from world object properties.
  2. 'unconscious' is auto-appended when hp_current <= 0 and hp_max > 0.
  3. Conditions from world properties are preserved as-is.
  4. Characters with no conditions have an empty list.
"""

import pytest
from src.backend.core.campaign_io import new_campaign_object
from src.backend.models.user import CampaignPlayer
from src.backend.models.world import Object


# ---------------------------------------------------------------------------
# Helper: build a minimal CampaignPlayer and enrich it like get_players() does
# ---------------------------------------------------------------------------

def _enrich_player(world, char_obj) -> CampaignPlayer:
    """Mirror the enrichment logic in campaign_manager.get_players()."""
    cp = CampaignPlayer(
        user_id="u1",
        username="tester",
        character_object_id=char_obj.id,
        character_name=char_obj.name,
        joined_at="2026-01-01T00:00:00",
    )
    hp = char_obj.properties.get("hp", {})
    cp.hp_current = hp.get("current", 0)
    cp.hp_max = hp.get("max", 0)
    children = world.get_children(char_obj.id)
    total_weight = sum(c.weight for c in children)
    str_score = char_obj.properties.get("abilities", {}).get("str", 10)
    cp.encumbrance_current = total_weight
    cp.encumbrance_max = str_score * 15.0
    # Conditions logic (mirrors campaign_manager.get_players)
    world_conditions = list(char_obj.properties.get("conditions", []))
    if cp.hp_current <= 0 and cp.hp_max > 0 and "unconscious" not in world_conditions:
        world_conditions.append("unconscious")
    cp.conditions = world_conditions
    return cp


@pytest.fixture()
def world_with_pc():
    campaign = new_campaign_object("CondTest", seed=42)
    pcs = campaign.world.get_pcs()
    assert pcs, "Expected at least one PC"
    return campaign.world, pcs[0]


# ---------------------------------------------------------------------------
# Condition population
# ---------------------------------------------------------------------------

class TestConditionPopulation:
    def test_healthy_pc_has_no_conditions(self, world_with_pc):
        world, pc = world_with_pc
        hp = pc.properties.get("hp", {})
        # Ensure PC is alive
        pc.properties["hp"] = {"current": hp.get("max", 10), "max": hp.get("max", 10)}
        cp = _enrich_player(world, pc)
        assert "unconscious" not in cp.conditions

    def test_zero_hp_adds_unconscious(self, world_with_pc):
        world, pc = world_with_pc
        pc.properties["hp"] = {"current": 0, "max": 10}
        cp = _enrich_player(world, pc)
        assert "unconscious" in cp.conditions

    def test_negative_hp_adds_unconscious(self, world_with_pc):
        world, pc = world_with_pc
        pc.properties["hp"] = {"current": -5, "max": 10}
        cp = _enrich_player(world, pc)
        assert "unconscious" in cp.conditions

    def test_hp_zero_with_zero_max_does_not_add_unconscious(self, world_with_pc):
        """Characters without a max HP (e.g. no health) should not be auto-marked unconscious."""
        world, pc = world_with_pc
        pc.properties["hp"] = {"current": 0, "max": 0}
        cp = _enrich_player(world, pc)
        assert "unconscious" not in cp.conditions

    def test_explicit_conditions_from_world(self, world_with_pc):
        world, pc = world_with_pc
        pc.properties["hp"] = {"current": 8, "max": 10}
        pc.properties["conditions"] = ["silenced", "poisoned"]
        cp = _enrich_player(world, pc)
        assert "silenced" in cp.conditions
        assert "poisoned" in cp.conditions

    def test_no_duplicate_unconscious_when_already_set(self, world_with_pc):
        world, pc = world_with_pc
        pc.properties["hp"] = {"current": 0, "max": 10}
        pc.properties["conditions"] = ["unconscious"]
        cp = _enrich_player(world, pc)
        assert cp.conditions.count("unconscious") == 1

    def test_conditions_empty_list_by_default(self, world_with_pc):
        world, pc = world_with_pc
        pc.properties["hp"] = {"current": 10, "max": 10}
        pc.properties.pop("conditions", None)
        cp = _enrich_player(world, pc)
        assert cp.conditions == []

    def test_all_standard_conditions_preserved(self, world_with_pc):
        world, pc = world_with_pc
        all_conds = [
            "silenced", "unconscious", "paralyzed", "blinded", "prone",
            "restrained", "petrified", "incapacitated", "stunned",
            "poisoned", "frightened", "charmed", "exhaustion",
        ]
        pc.properties["hp"] = {"current": 10, "max": 10}
        pc.properties["conditions"] = all_conds
        cp = _enrich_player(world, pc)
        for cond in all_conds:
            assert cond in cp.conditions


# ---------------------------------------------------------------------------
# Button disable logic (pure Python mirror of frontend logic)
# ---------------------------------------------------------------------------

# Actions that block on specific conditions (matches ActionBar.vue ACTIONS)
COMBAT_ACTIONS = {
    "Attack":     ["unconscious", "paralyzed", "petrified", "incapacitated"],
    "Cast Spell": ["silenced", "unconscious", "paralyzed", "petrified", "incapacitated"],
    "Dash":       ["unconscious", "paralyzed", "petrified", "restrained", "incapacitated"],
    "Dodge":      ["unconscious", "paralyzed", "petrified", "incapacitated"],
    "Help":       ["unconscious", "paralyzed", "petrified", "incapacitated"],
}


def _is_button_disabled(action_blocked_by: list[str], conditions: list[str], not_my_turn: bool = False) -> bool:
    if not_my_turn:
        return True
    return any(c in conditions for c in action_blocked_by)


class TestButtonDisableLogic:
    def test_attack_disabled_when_unconscious(self):
        assert _is_button_disabled(COMBAT_ACTIONS["Attack"], ["unconscious"])

    def test_attack_disabled_when_paralyzed(self):
        assert _is_button_disabled(COMBAT_ACTIONS["Attack"], ["paralyzed"])

    def test_attack_enabled_when_healthy(self):
        assert not _is_button_disabled(COMBAT_ACTIONS["Attack"], [])

    def test_cast_spell_disabled_when_silenced(self):
        assert _is_button_disabled(COMBAT_ACTIONS["Cast Spell"], ["silenced"])

    def test_cast_spell_enabled_without_silenced(self):
        assert not _is_button_disabled(COMBAT_ACTIONS["Cast Spell"], ["poisoned"])

    def test_dash_disabled_when_restrained(self):
        assert _is_button_disabled(COMBAT_ACTIONS["Dash"], ["restrained"])

    def test_all_combat_actions_disabled_when_unconscious(self):
        for action, blocked_by in COMBAT_ACTIONS.items():
            assert _is_button_disabled(blocked_by, ["unconscious"]), f"{action} should be disabled"

    def test_not_my_turn_disables_regardless_of_conditions(self):
        assert _is_button_disabled(COMBAT_ACTIONS["Attack"], [], not_my_turn=True)
        assert _is_button_disabled([], [], not_my_turn=True)

    def test_poisoned_does_not_block_attack(self):
        assert not _is_button_disabled(COMBAT_ACTIONS["Attack"], ["poisoned"])

    def test_incapacitated_disables_help(self):
        assert _is_button_disabled(COMBAT_ACTIONS["Help"], ["incapacitated"])
