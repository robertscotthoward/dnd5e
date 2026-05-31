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
