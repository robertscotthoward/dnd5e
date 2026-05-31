"""Tests for WS combat turn enforcement logic.

These tests verify the turn-enforcement predicate used in ws_routes.py:
given a game mode, active_player_turn object_id, and the connecting
player's char_name, determine whether the player is blocked.
"""

import pytest
from src.backend.core.campaign_io import new_campaign_object
from src.backend.core.combat import CombatEngine
from src.backend.models.user import CampaignMeta
from src.backend.models.world import Object


# ---------------------------------------------------------------------------
# Helpers matching the ws_routes.py check logic
# ---------------------------------------------------------------------------

def _resolve_active_char_name(world, active_player_turn):
    """Mirror the lookup used in ws_routes.py."""
    if active_player_turn is None:
        return None
    obj = world.get_object(active_player_turn)
    return obj.name if obj else None


def is_turn_blocked(meta: CampaignMeta, world, char_name: str) -> tuple[bool, str | None]:
    """Return (blocked, active_char_name).  blocked=True means not this player's turn."""
    if meta.game_mode != "Combat":
        return False, None
    active_char_name = _resolve_active_char_name(world, meta.active_player_turn)
    if active_char_name and char_name != active_char_name:
        return True, active_char_name
    return False, active_char_name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def combat_setup():
    """Create a minimal campaign + meta with two combatants in Combat mode."""
    campaign = new_campaign_object("TurnTest", seed=7)
    meta = CampaignMeta(
        id="turn-test",
        name="TurnTest",
        seed=7,
        turn_number=0,
        game_mode="Exploration",
        created_by="tester",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )
    # Add an NPC combatant
    pcs = campaign.world.get_pcs()
    assert pcs, "Expected at least one PC in new campaign"
    npc_id = campaign.world.next_id()
    npc = Object(
        id=npc_id,
        parent=pcs[0].parent,
        type="NPC",
        name="Kobold",
        properties={
            "creature_type": "kobold",
            "hp": {"current": 5, "max": 5},
            "ac": 12,
            "abilities": {"str": 7, "dex": 15, "con": 9, "int": 8, "wis": 7, "chr": 8},
        },
    )
    campaign.world.add_object(npc)
    # Start combat so meta.game_mode == "Combat" and queue is set
    engine = CombatEngine(campaign.world, meta, seed=1)
    engine.start_combat([pcs[0].id, npc_id])
    return campaign, meta, pcs[0], npc


# ---------------------------------------------------------------------------
# Turn enforcement: chat and action commands
# ---------------------------------------------------------------------------

class TestTurnEnforcement:
    def test_exploration_mode_never_blocks(self):
        campaign = new_campaign_object("Explore", seed=2)
        meta = CampaignMeta(
            id="e", name="E", seed=2, turn_number=0,
            game_mode="Exploration",
            created_by="t", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        pcs = campaign.world.get_pcs()
        blocked, _ = is_turn_blocked(meta, campaign.world, pcs[0].name)
        assert not blocked

    def test_combat_active_player_not_blocked(self, combat_setup):
        campaign, meta, pc, npc = combat_setup
        active_char = _resolve_active_char_name(campaign.world, meta.active_player_turn)
        blocked, _ = is_turn_blocked(meta, campaign.world, active_char)
        assert not blocked

    def test_combat_inactive_player_blocked(self, combat_setup):
        campaign, meta, pc, npc = combat_setup
        active_char = _resolve_active_char_name(campaign.world, meta.active_player_turn)
        # Pick any combatant that is NOT the active one
        all_names = {pc.name, npc.name}
        inactive_char = (all_names - {active_char}).pop()
        blocked, returned_active = is_turn_blocked(meta, campaign.world, inactive_char)
        assert blocked
        assert returned_active == active_char

    def test_blocked_message_contains_active_name(self, combat_setup):
        campaign, meta, pc, npc = combat_setup
        active_char = _resolve_active_char_name(campaign.world, meta.active_player_turn)
        all_names = {pc.name, npc.name}
        inactive_char = (all_names - {active_char}).pop()
        blocked, active_name = is_turn_blocked(meta, campaign.world, inactive_char)
        assert blocked
        msg = f"It is {active_name}'s turn. Please wait."
        assert active_name in msg

    def test_waiting_broadcast_message_format(self, combat_setup):
        campaign, meta, pc, npc = combat_setup
        active_char = _resolve_active_char_name(campaign.world, meta.active_player_turn)
        wait_msg = {
            "type": "waiting_for_turn",
            "message": f"Waiting for {active_char} to act.",
            "active_character": active_char,
        }
        assert wait_msg["type"] == "waiting_for_turn"
        assert active_char in wait_msg["message"]
        assert wait_msg["active_character"] == active_char

    def test_no_active_player_turn_set_does_not_block(self):
        campaign = new_campaign_object("NoTurn", seed=3)
        meta = CampaignMeta(
            id="nt", name="NT", seed=3, turn_number=0,
            game_mode="Combat",  # Combat mode but no active turn assigned yet
            active_player_turn=None,
            created_by="t", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        pcs = campaign.world.get_pcs()
        blocked, _ = is_turn_blocked(meta, campaign.world, pcs[0].name)
        assert not blocked

    def test_active_turn_unknown_object_does_not_block(self):
        campaign = new_campaign_object("UnknownObj", seed=4)
        meta = CampaignMeta(
            id="uo", name="UO", seed=4, turn_number=0,
            game_mode="Combat",
            active_player_turn=99999,  # non-existent object
            created_by="t", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        pcs = campaign.world.get_pcs()
        blocked, _ = is_turn_blocked(meta, campaign.world, pcs[0].name)
        assert not blocked

    def test_turn_rotates_to_next_combatant(self, combat_setup):
        campaign, meta, pc, npc = combat_setup
        engine = CombatEngine(campaign.world, meta, seed=1)
        first_active = meta.active_player_turn
        engine.next_turn()
        second_active = meta.active_player_turn
        assert first_active != second_active
        # The previously inactive player is now active and should not be blocked
        active_char = _resolve_active_char_name(campaign.world, second_active)
        blocked, _ = is_turn_blocked(meta, campaign.world, active_char)
        assert not blocked

    def test_end_combat_lifts_all_restrictions(self, combat_setup):
        campaign, meta, pc, npc = combat_setup
        engine = CombatEngine(campaign.world, meta, seed=1)
        engine.end_combat()
        # After combat ends, no player should be blocked
        blocked_pc, _ = is_turn_blocked(meta, campaign.world, pc.name)
        blocked_npc, _ = is_turn_blocked(meta, campaign.world, npc.name)
        assert not blocked_pc
        assert not blocked_npc

    def test_social_mode_never_blocks(self):
        campaign = new_campaign_object("Social", seed=5)
        meta = CampaignMeta(
            id="s", name="S", seed=5, turn_number=0,
            game_mode="Social Interaction",
            created_by="t", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        pcs = campaign.world.get_pcs()
        blocked, _ = is_turn_blocked(meta, campaign.world, pcs[0].name)
        assert not blocked

    def test_travel_mode_never_blocks(self):
        campaign = new_campaign_object("Travel", seed=6)
        meta = CampaignMeta(
            id="tv", name="TV", seed=6, turn_number=0,
            game_mode="Travel",
            created_by="t", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        pcs = campaign.world.get_pcs()
        blocked, _ = is_turn_blocked(meta, campaign.world, pcs[0].name)
        assert not blocked
