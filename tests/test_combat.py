"""Tests for the combat engine and combat tools."""

import random
from pathlib import Path

import pytest

from src.backend.core.campaign_io import new_campaign_object, save_campaign
from src.backend.core.combat import CombatEngine, roll_dice, _ability_modifier
from src.backend.core.tools import CombatTools
from src.backend.models.user import CampaignMeta
from src.backend.models.world import Object


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(tmp_path: Path, name: str = "CombatTest"):
    campaign = new_campaign_object(name, seed=99)
    world_path = tmp_path / name / "world.yaml"
    world_path.parent.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, world_path)
    return campaign


def _make_meta(campaign_id: str = "combat-test") -> CampaignMeta:
    return CampaignMeta(
        id=campaign_id,
        name="CombatTest",
        seed=99,
        turn_number=0,
        game_mode="Exploration",
        created_by="test",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )


def _add_npc(campaign, hp: int = 10, dex: int = 14) -> Object:
    party = campaign.world.get_parties()[0]
    npc_id = campaign.world.next_id()
    npc = Object(
        id=npc_id,
        parent=party.id,
        type="NPC",
        name=f"Goblin_{npc_id}",
        properties={
            "creature_type": "goblin",
            "hp": {"current": hp, "max": hp},
            "ac": 13,
            "abilities": {"str": 8, "dex": dex, "con": 10, "int": 10, "wis": 8, "chr": 8},
        },
    )
    campaign.world.add_object(npc)
    return npc


# ---------------------------------------------------------------------------
# roll_dice tests
# ---------------------------------------------------------------------------

class TestRollDice:
    def test_d20_range(self):
        rng = random.Random(1)
        for _ in range(50):
            result = roll_dice("d20", rng)
            assert 1 <= result["total"] <= 20

    def test_2d6_plus_3_range(self):
        rng = random.Random(2)
        for _ in range(50):
            result = roll_dice("2d6+3", rng)
            assert 5 <= result["total"] <= 15

    def test_modifier_applied(self):
        rng = random.Random(42)
        result = roll_dice("1d6+5", rng)
        assert result["modifier"] == 5
        assert result["total"] == result["rolls"][0] + 5

    def test_negative_modifier(self):
        rng = random.Random(42)
        result = roll_dice("1d6-2", rng)
        assert result["modifier"] == -2
        assert result["total"] == result["rolls"][0] - 2

    def test_critical_hit_natural_20(self):
        # Seed until we get a 20
        found = False
        for seed in range(200):
            rng = random.Random(seed)
            result = roll_dice("d20", rng)
            if result["rolls"][0] == 20:
                assert result["critical_hit"] is True
                found = True
                break
        assert found, "Could not produce a natural 20 in 200 seeds"

    def test_critical_miss_natural_1(self):
        found = False
        for seed in range(200):
            rng = random.Random(seed)
            result = roll_dice("d20", rng)
            if result["rolls"][0] == 1:
                assert result["critical_miss"] is True
                found = True
                break
        assert found, "Could not produce a natural 1 in 200 seeds"

    def test_multi_die_not_critical(self):
        rng = random.Random(7)
        result = roll_dice("2d20", rng)
        assert result["critical_hit"] is False
        assert result["critical_miss"] is False

    def test_invalid_notation_raises(self):
        with pytest.raises(ValueError):
            roll_dice("notadice")

    def test_invalid_notation_zero_count_raises(self):
        with pytest.raises(ValueError):
            roll_dice("0d6")


# ---------------------------------------------------------------------------
# _ability_modifier tests
# ---------------------------------------------------------------------------

class TestAbilityModifier:
    def test_score_10_gives_0(self):
        assert _ability_modifier(10) == 0

    def test_score_8_gives_minus1(self):
        assert _ability_modifier(8) == -1

    def test_score_18_gives_4(self):
        assert _ability_modifier(18) == 4

    def test_score_20_gives_5(self):
        assert _ability_modifier(20) == 5

    def test_score_1_gives_minus5(self):
        assert _ability_modifier(1) == -5


# ---------------------------------------------------------------------------
# CombatEngine tests
# ---------------------------------------------------------------------------

class TestCombatEngine:
    def test_start_combat_sets_mode(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        pcs = campaign.world.get_pcs()
        combatant_ids = [pcs[0].id, npc.id]

        engine = CombatEngine(campaign.world, meta, seed=1)
        result = engine.start_combat(combatant_ids)

        assert meta.game_mode == "Combat"
        assert len(result["initiative_order"]) == 2
        assert meta.active_player_turn == result["active_turn"]
        assert len(meta.combat_queue) == 2

    def test_initiative_order_descending(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc1 = _add_npc(campaign, dex=14)
        npc2 = _add_npc(campaign, dex=8)
        pcs = campaign.world.get_pcs()

        engine = CombatEngine(campaign.world, meta, seed=5)
        result = engine.start_combat([pcs[0].id, npc1.id, npc2.id])

        initiatives = [e["initiative"] for e in result["initiative_order"]]
        assert initiatives == sorted(initiatives, reverse=True)

    def test_next_turn_rotates_queue(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        pcs = campaign.world.get_pcs()
        combatant_ids = [pcs[0].id, npc.id]

        engine = CombatEngine(campaign.world, meta, seed=1)
        engine.start_combat(combatant_ids)

        first = meta.active_player_turn
        engine.next_turn()
        second = meta.active_player_turn

        assert first != second

        engine.next_turn()
        assert meta.active_player_turn == first  # wrapped back

    def test_end_combat_resets_state(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        pcs = campaign.world.get_pcs()

        engine = CombatEngine(campaign.world, meta, seed=1)
        engine.start_combat([pcs[0].id, npc.id])
        engine.end_combat()

        assert meta.game_mode == "Exploration"
        assert meta.combat_queue == []
        assert meta.active_player_turn is None

    def test_roll_attack_hit_or_miss(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        pcs = campaign.world.get_pcs()

        engine = CombatEngine(campaign.world, meta, seed=42)
        result = engine.roll_attack(pcs[0].id, npc.id, attack_bonus=5)

        assert "hit" in result
        assert isinstance(result["hit"], bool)
        assert 1 <= result["d20_roll"] <= 20
        assert result["target_ac"] == 13

    def test_roll_attack_natural_20_always_hits(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        npc.properties["ac"] = 99  # impossible AC
        pcs = campaign.world.get_pcs()

        engine = CombatEngine(campaign.world, meta, seed=0)
        # Find a seed that rolls 20
        for seed in range(500):
            engine.rng = random.Random(seed)
            result = engine.roll_attack(pcs[0].id, npc.id, attack_bonus=0)
            if result["critical_hit"]:
                assert result["hit"] is True
                break

    def test_roll_attack_natural_1_always_misses(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        npc.properties["ac"] = 1  # trivially easy AC
        pcs = campaign.world.get_pcs()

        engine = CombatEngine(campaign.world, meta, seed=0)
        for seed in range(500):
            engine.rng = random.Random(seed)
            result = engine.roll_attack(pcs[0].id, npc.id, attack_bonus=0)
            if result["critical_miss"]:
                assert result["hit"] is False
                break

    def test_roll_attack_unknown_attacker(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)

        engine = CombatEngine(campaign.world, meta, seed=1)
        result = engine.roll_attack(99999, npc.id)
        assert "error" in result

    def test_roll_saving_throw_success(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)

        engine = CombatEngine(campaign.world, meta, seed=1)
        result = engine.roll_saving_throw(npc.id, "dex", dc=1)
        assert result["success"] is True

    def test_roll_saving_throw_failure(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign, dex=1)  # -5 modifier

        engine = CombatEngine(campaign.world, meta, seed=1)
        # Use a seed that rolls low; DC 30 is impossible to beat without natural 20
        found_fail = False
        for seed in range(200):
            engine.rng = random.Random(seed)
            result = engine.roll_saving_throw(npc.id, "dex", dc=30)
            if not result["success"] and not result["critical_hit"]:
                found_fail = True
                break
        assert found_fail

    def test_roll_saving_throw_unknown_target(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()

        engine = CombatEngine(campaign.world, meta, seed=1)
        result = engine.roll_saving_throw(99999, "dex", dc=15)
        assert "error" in result

    def test_start_combat_ignores_missing_ids(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        pcs = campaign.world.get_pcs()

        engine = CombatEngine(campaign.world, meta, seed=1)
        result = engine.start_combat([pcs[0].id, 99999])
        assert len(result["initiative_order"]) == 1


# ---------------------------------------------------------------------------
# CombatTools tests
# ---------------------------------------------------------------------------

class TestCombatTools:
    def test_start_combat_tool_success(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        pcs = campaign.world.get_pcs()

        ct = CombatTools(campaign.world, meta)
        result = ct.start_combat([pcs[0].id, npc.id])

        assert result.success is True
        assert meta.game_mode == "Combat"

    def test_next_turn_tool(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        pcs = campaign.world.get_pcs()

        ct = CombatTools(campaign.world, meta)
        ct.start_combat([pcs[0].id, npc.id])
        first = meta.active_player_turn

        result = ct.next_turn()
        assert result.success is True
        assert meta.active_player_turn != first

    def test_end_combat_tool(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        pcs = campaign.world.get_pcs()

        ct = CombatTools(campaign.world, meta)
        ct.start_combat([pcs[0].id, npc.id])
        result = ct.end_combat()

        assert result.success is True
        assert meta.game_mode == "Exploration"

    def test_roll_attack_tool(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)
        pcs = campaign.world.get_pcs()

        ct = CombatTools(campaign.world, meta)
        result = ct.roll_attack(pcs[0].id, npc.id, attack_bonus=3)

        assert result.success is True
        assert "HIT" in result.message or "MISS" in result.message

    def test_roll_saving_throw_tool(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)

        ct = CombatTools(campaign.world, meta)
        result = ct.roll_saving_throw(npc.id, "dex", dc=15)

        assert result.success is True
        assert "SUCCESS" in result.message or "FAILURE" in result.message

    def test_roll_damage_tool(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        pcs = campaign.world.get_pcs()

        ct = CombatTools(campaign.world, meta)
        result = ct.roll_damage(pcs[0].id, "2d6+3")

        assert result.success is True
        assert result.data is not None
        assert 5 <= result.data["total"] <= 15

    def test_roll_damage_invalid_notation(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        pcs = campaign.world.get_pcs()

        ct = CombatTools(campaign.world, meta)
        result = ct.roll_damage(pcs[0].id, "not_dice")

        assert result.success is False

    def test_next_turn_without_combat_fails(self, tmp_path):
        campaign = _make_campaign(tmp_path)
        meta = _make_meta()

        ct = CombatTools(campaign.world, meta)
        result = ct.next_turn()

        assert result.success is False

    def test_ai_client_creates_combat_tools(self, tmp_path):
        """create_combat_tools includes all combat tool names."""
        from src.backend.core.ai_client import AIClient
        from src.backend.core.tools import WorldTools

        campaign = _make_campaign(tmp_path)
        meta = _make_meta()
        npc = _add_npc(campaign)

        client = AIClient()
        wt = WorldTools(campaign.world)
        ct = CombatTools(campaign.world, meta)
        tools = client.create_combat_tools(wt, ct)
        tool_names = {t.metadata.name for t in tools}

        assert "start_combat" in tool_names
        assert "next_turn" in tool_names
        assert "end_combat" in tool_names
        assert "roll_attack" in tool_names
        assert "roll_saving_throw" in tool_names
        assert "roll_damage" in tool_names
        # Standard world tools must also be present
        assert "add_hp" in tool_names
        assert "get_object" in tool_names
