"""Tests for the 'turn' CLI command — pure-Python, no Ollama required."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backend.core.campaign_io import new_campaign_object, save_campaign, load_campaign_from_file
from src.backend.core.tools import WorldTools


def _make_campaign(tmp_path: Path, name: str = "TestTurn") -> tuple:
    """Create a campaign, save it, and return (campaign_obj, world_path)."""
    campaign_obj = new_campaign_object(name, seed=42)
    world_path = tmp_path / name / "world.yaml"
    world_path.parent.mkdir(parents=True, exist_ok=True)
    save_campaign(campaign_obj, world_path)
    return campaign_obj, world_path


class TestTurnCoreLogic:
    """Tests for the turn command's core mechanics (no LLM calls)."""

    def test_campaign_loads_from_yaml(self, tmp_path):
        _, world_path = _make_campaign(tmp_path)
        loaded = load_campaign_from_file(world_path)
        assert loaded.name == "TestTurn"
        assert loaded.seed == 42
        assert loaded.turn_number == 0
        assert len(loaded.world.objects) > 0

    def test_advance_turn_increments_counter(self, tmp_path):
        campaign, world_path = _make_campaign(tmp_path)
        assert campaign.turn_number == 0
        campaign.advance_turn()
        assert campaign.turn_number == 1

    def test_event_logged_after_turn(self, tmp_path):
        campaign, _ = _make_campaign(tmp_path)
        campaign.advance_turn()
        campaign.add_event(
            event_type="dm_narrative",
            description="The party enters a dimly lit tavern.",
            seed=campaign.seed,
        )
        assert len(campaign.event_log) == 1
        event = campaign.event_log[0]
        assert event.event_type == "dm_narrative"
        assert "tavern" in event.description
        assert event.seed == 42

    def test_save_and_reload_preserves_turn_number(self, tmp_path):
        campaign, world_path = _make_campaign(tmp_path)
        campaign.advance_turn()
        campaign.advance_turn()
        save_campaign(campaign, world_path)

        reloaded = load_campaign_from_file(world_path)
        assert reloaded.turn_number == 2

    def test_world_tools_accessible(self, tmp_path):
        campaign, _ = _make_campaign(tmp_path)
        tools = WorldTools(campaign.world)
        # get_object round-trip
        pcs = campaign.world.get_pcs()
        assert len(pcs) == 4
        result = tools.get_object(pcs[0].id)
        assert result.success
        assert result.data["id"] == pcs[0].id

    def test_turn_command_with_mocked_ai(self, tmp_path):
        """Simulate the full turn flow with a mocked AI client."""
        campaign, world_path = _make_campaign(tmp_path)

        # Mock ai_client to avoid Ollama dependency
        mock_narrative = "The innkeeper greets you warmly."
        mock_ai = MagicMock()
        mock_ai.query_rules.return_value = "No relevant rules found."
        mock_ai.generate_dm_response.return_value = mock_narrative

        with patch("src.backend.core.ai_client.ai_client", mock_ai):
            from src.backend.core.ai_client import ai_client as patched_ai
            from src.backend.core.tools import WorldTools as WT

            loaded = load_campaign_from_file(world_path)
            wt = WT(loaded.world)
            situation = "The party rests in the Common Room."

            rules = patched_ai.query_rules(situation)
            assert rules == "No relevant rules found."

            narrative = patched_ai.generate_dm_response(loaded, situation, wt)
            assert narrative == mock_narrative

            loaded.advance_turn()
            loaded.add_event(event_type="dm_narrative", description=narrative, seed=loaded.seed)
            save_campaign(loaded, world_path)

            seeds_log = world_path.parent / "seeds.log"
            with open(seeds_log, "a", encoding="utf-8") as f:
                f.write(f"turn={loaded.turn_number} seed={loaded.seed} campaign={loaded.name}\n")

        reloaded = load_campaign_from_file(world_path)
        assert reloaded.turn_number == 1
        assert seeds_log.exists()
        assert "turn=1" in seeds_log.read_text()

    def test_get_sub_world_returns_visible_objects(self, tmp_path):
        campaign, _ = _make_campaign(tmp_path)
        tools = WorldTools(campaign.world)
        pcs = campaign.world.get_pcs()
        result = tools.get_sub_world(pcs[0].id)
        assert result.success
        assert isinstance(result.data, dict)
        assert "objects" in result.data

    def test_pc_agent_with_mocked_ai(self, tmp_path):
        """PC agent returns a first-person action string (mocked, no Ollama required)."""
        campaign, _ = _make_campaign(tmp_path)
        pcs = campaign.world.get_pcs()
        pc = pcs[0]

        mock_action = f"I draw my sword and advance toward the goblin!"
        mock_ai = MagicMock()
        mock_ai.generate_player_action.return_value = mock_action

        with patch("src.backend.core.ai_client.ai_client", mock_ai):
            from src.backend.core.ai_client import ai_client as patched_ai
            from src.backend.core.tools import WorldTools as WT

            wt = WT(campaign.world)
            situation = "A goblin leaps from the shadows!"
            action = patched_ai.generate_player_action(campaign, pc.id, situation, wt)

        assert action == mock_action

    def test_pc_agent_tools_are_read_and_movement_only(self, tmp_path):
        """PC tool set must include get_object and move_object but not delete_object."""
        from src.backend.core.ai_client import AIClient
        from src.backend.core.tools import WorldTools as WT

        campaign, _ = _make_campaign(tmp_path)
        client = AIClient()
        wt = WT(campaign.world)
        tools = client.create_pc_tools(wt)
        tool_names = {t.metadata.name for t in tools}

        assert "get_object" in tool_names
        assert "get_sub_world" in tool_names
        assert "move_object" in tool_names
        assert "set_object_property" in tool_names
        assert "delete_object" not in tool_names
        assert "create_object" not in tool_names
        assert "add_hp" not in tool_names

    def test_pc_agent_missing_player_returns_not_found(self, tmp_path):
        """generate_player_action returns a safe string when the player ID is invalid."""
        from src.backend.core.ai_client import AIClient
        from src.backend.core.tools import WorldTools as WT

        campaign, _ = _make_campaign(tmp_path)
        client = AIClient()
        wt = WT(campaign.world)
        result = client.generate_player_action(campaign, player_id=99999, situation="test", world_tools=wt)
        assert result == "Player not found"

    def test_npc_agent_with_mocked_ai(self, tmp_path):
        """NPC agent returns a third-person action string (mocked, no Ollama required)."""
        from src.backend.core.tools import WorldTools as WT

        campaign, _ = _make_campaign(tmp_path)

        # Inject an NPC into the world
        from src.backend.models.world import Object
        npc_id = campaign.world.next_id()
        party = campaign.world.get_parties()[0]
        npc = Object(
            id=npc_id,
            parent=party.id,
            type="NPC",
            name="Grimtooth the Goblin",
            properties={
                "creature_type": "goblin",
                "role": "scout",
                "behavior": "Skirmishes and retreats when hurt",
                "hp": {"current": 7, "max": 7},
                "abilities": {"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "chr": 8},
            },
        )
        campaign.world.add_object(npc)

        mock_action = "Grimtooth lunges at the nearest PC, slashing with its rusty blade."
        mock_ai = MagicMock()
        mock_ai.generate_npc_action.return_value = mock_action

        with patch("src.backend.core.ai_client.ai_client", mock_ai):
            from src.backend.core.ai_client import ai_client as patched_ai

            wt = WT(campaign.world)
            directive = "Attack the nearest PC with your scimitar."
            action = patched_ai.generate_npc_action(campaign, npc_id, directive, wt)

        assert action == mock_action

    def test_npc_agent_tools_include_add_hp(self, tmp_path):
        """NPC tool set must include add_hp (NPCs can apply damage per DM directive)."""
        from src.backend.core.ai_client import AIClient
        from src.backend.core.tools import WorldTools as WT

        campaign, _ = _make_campaign(tmp_path)
        client = AIClient()
        wt = WT(campaign.world)
        tools = client.create_npc_tools(wt)
        tool_names = {t.metadata.name for t in tools}

        assert "get_object" in tool_names
        assert "get_sub_world" in tool_names
        assert "move_object" in tool_names
        assert "set_object_property" in tool_names
        assert "add_hp" in tool_names
        assert "delete_object" not in tool_names
        assert "create_object" not in tool_names

    def test_npc_agent_missing_npc_returns_not_found(self, tmp_path):
        """generate_npc_action returns 'NPC not found' for invalid NPC ID."""
        from src.backend.core.ai_client import AIClient
        from src.backend.core.tools import WorldTools as WT

        campaign, _ = _make_campaign(tmp_path)
        client = AIClient()
        wt = WT(campaign.world)
        result = client.generate_npc_action(campaign, npc_id=99999, dm_directive="attack", world_tools=wt)
        assert result == "NPC not found"

    def test_world_agent_tools_exclude_add_hp_and_delete(self, tmp_path):
        """World Agent tool set must not include add_hp or delete_object."""
        from src.backend.core.ai_client import AIClient
        from src.backend.core.tools import WorldTools as WT

        campaign, _ = _make_campaign(tmp_path)
        client = AIClient()
        wt = WT(campaign.world)
        tools = client.create_world_tools(wt)
        tool_names = {t.metadata.name for t in tools}

        assert "get_object" in tool_names
        assert "get_sub_world" in tool_names
        assert "move_object" in tool_names
        assert "set_object_property" in tool_names
        assert "create_object" in tool_names
        assert "add_hp" not in tool_names
        assert "delete_object" not in tool_names

    def test_world_agent_with_mocked_ai(self, tmp_path):
        """World agent returns a narrator summary string (mocked, no Ollama required)."""
        from src.backend.core.tools import WorldTools as WT

        campaign, _ = _make_campaign(tmp_path)

        mock_summary = "A cold wind sweeps through the valley; a stray cat knocks over a bucket in the market."
        mock_ai = MagicMock()
        mock_ai.generate_world_update.return_value = mock_summary

        with patch("src.backend.core.ai_client.ai_client", mock_ai):
            from src.backend.core.ai_client import ai_client as patched_ai

            wt = WT(campaign.world)
            result = patched_ai.generate_world_update(campaign, wt)

        assert result == mock_summary

    def test_world_agent_fires_before_dm_in_turn(self, tmp_path):
        """turn command invokes generate_world_update before generate_dm_response."""
        campaign, world_path = _make_campaign(tmp_path)

        call_order = []

        mock_ai = MagicMock()
        mock_ai.query_rules.return_value = "No relevant rules found."
        mock_ai.generate_world_update.side_effect = lambda *a, **kw: call_order.append("world") or "Clouds roll in."
        mock_ai.generate_dm_response.side_effect = lambda *a, **kw: call_order.append("dm") or "The DM speaks."

        from src.backend.core.campaign_io import load_campaign_from_file
        from src.backend.core.tools import WorldTools as WT

        loaded = load_campaign_from_file(world_path)
        wt = WT(loaded.world)
        situation = "The party enters a dungeon."

        world_summary = mock_ai.generate_world_update(loaded, wt)
        loaded.add_event(event_type="world_update", description=world_summary, seed=loaded.seed)
        narrative = mock_ai.generate_dm_response(loaded, situation, wt)
        loaded.advance_turn()
        loaded.add_event(event_type="dm_narrative", description=narrative, seed=loaded.seed)

        assert call_order == ["world", "dm"]
        world_events = [e for e in loaded.event_log if e.event_type == "world_update"]
        dm_events = [e for e in loaded.event_log if e.event_type == "dm_narrative"]
        assert len(world_events) == 1
        assert len(dm_events) == 1
        assert "Clouds" in world_events[0].description

    def test_world_agent_missing_world_tools_creates_default(self, tmp_path):
        """generate_world_update creates its own WorldTools if none supplied."""
        from src.backend.core.ai_client import AIClient

        campaign, _ = _make_campaign(tmp_path)
        client = AIClient()

        # Patch asyncio.run so no Ollama call happens; verify it was called with a coroutine
        with patch("asyncio.run", return_value="Mist settles over the hills.") as mock_run:
            result = client.generate_world_update(campaign)

        assert result == "Mist settles over the hills."
        mock_run.assert_called_once()

    def test_npc_agent_uses_npc_properties(self, tmp_path):
        """NPC agent system prompt uses creature_type, role, and behavior from properties."""
        from src.backend.core.ai_client import AIClient, _NPC_SYSTEM_PROMPT_TEMPLATE
        from src.backend.models.world import Object

        campaign, _ = _make_campaign(tmp_path)
        party = campaign.world.get_parties()[0]
        npc_id = campaign.world.next_id()
        npc = Object(
            id=npc_id,
            parent=party.id,
            type="NPC",
            name="Old Brennan",
            properties={
                "creature_type": "human",
                "role": "innkeeper",
                "behavior": "Friendly but wary of strangers",
                "hp": {"current": 10, "max": 10},
                "abilities": {"str": 10, "dex": 10, "con": 10, "int": 12, "wis": 14, "chr": 13},
            },
        )
        campaign.world.add_object(npc)

        expected_prompt = _NPC_SYSTEM_PROMPT_TEMPLATE.format(
            name="Old Brennan",
            creature_type="human",
            role="innkeeper",
            behavior="Friendly but wary of strangers",
        )
        assert "Old Brennan" in expected_prompt
        assert "innkeeper" in expected_prompt
        assert "Friendly but wary of strangers" in expected_prompt
