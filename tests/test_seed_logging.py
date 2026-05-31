"""Tests for seed logging utilities in campaign_io."""

from pathlib import Path

import pytest

from src.backend.core.campaign_io import (
    append_seed_log,
    get_turn_seed,
    new_campaign_object,
    save_campaign,
)
from src.backend.core.campaign_manager import create_campaign


class TestGetTurnSeed:
    def test_deterministic(self):
        assert get_turn_seed(42, 1) == get_turn_seed(42, 1)

    def test_different_turns_differ(self):
        assert get_turn_seed(42, 1) != get_turn_seed(42, 2)

    def test_different_campaigns_differ(self):
        assert get_turn_seed(42, 1) != get_turn_seed(99, 1)

    def test_within_valid_range(self):
        seed = get_turn_seed(123456, 7)
        assert 1 <= seed <= 999_999

    def test_turn_zero_valid(self):
        seed = get_turn_seed(1, 0)
        assert 1 <= seed <= 999_999


class TestAppendSeedLog:
    def test_creates_file_if_absent(self, tmp_path):
        append_seed_log(tmp_path, "campaign_created seed=42 name=Test")
        log = tmp_path / "seeds.log"
        assert log.exists()

    def test_content_is_correct(self, tmp_path):
        append_seed_log(tmp_path, "campaign_created seed=42 name=Test")
        text = (tmp_path / "seeds.log").read_text(encoding="utf-8")
        assert "campaign_created seed=42 name=Test" in text

    def test_appends_multiple_lines(self, tmp_path):
        append_seed_log(tmp_path, "line1")
        append_seed_log(tmp_path, "line2")
        lines = (tmp_path / "seeds.log").read_text(encoding="utf-8").splitlines()
        assert "line1" in lines
        assert "line2" in lines
        assert len(lines) == 2

    def test_each_entry_ends_with_newline(self, tmp_path):
        append_seed_log(tmp_path, "entry")
        raw = (tmp_path / "seeds.log").read_text(encoding="utf-8")
        assert raw.endswith("\n")


class TestNewCampaignSeedLog:
    def test_new_campaign_command_writes_seeds_log(self, tmp_path):
        """Simulate cmd_new_campaign: create a campaign folder and log seed."""
        campaign = new_campaign_object("SeedTest", seed=777)
        campaign_dir = tmp_path / "SeedTest"
        campaign_dir.mkdir()
        world_path = campaign_dir / "world.yaml"
        save_campaign(campaign, world_path)
        append_seed_log(campaign_dir, f"campaign_created seed={campaign.seed} name={campaign.name}")

        log = campaign_dir / "seeds.log"
        assert log.exists()
        text = log.read_text(encoding="utf-8")
        assert "seed=777" in text
        assert "name=SeedTest" in text

    def test_turn_writes_turn_seed_to_log(self, tmp_path):
        """Each turn appends a line with both campaign_seed and turn_seed."""
        campaign = new_campaign_object("TurnSeedTest", seed=100)
        campaign_dir = tmp_path / "TurnSeedTest"
        campaign_dir.mkdir()
        world_path = campaign_dir / "world.yaml"
        save_campaign(campaign, world_path)

        # Simulate first turn
        campaign.advance_turn()
        turn_seed = get_turn_seed(campaign.seed, campaign.turn_number)
        append_seed_log(
            campaign_dir,
            f"turn={campaign.turn_number} campaign_seed={campaign.seed} turn_seed={turn_seed} campaign={campaign.name}",
        )

        text = (campaign_dir / "seeds.log").read_text(encoding="utf-8")
        assert "turn=1" in text
        assert f"campaign_seed={campaign.seed}" in text
        assert f"turn_seed={turn_seed}" in text

    def test_multiple_turns_produce_multiple_log_lines(self, tmp_path):
        campaign = new_campaign_object("MultiTurn", seed=55)
        campaign_dir = tmp_path / "MultiTurn"
        campaign_dir.mkdir()
        world_path = campaign_dir / "world.yaml"
        save_campaign(campaign, world_path)

        for _ in range(3):
            campaign.advance_turn()
            turn_seed = get_turn_seed(campaign.seed, campaign.turn_number)
            append_seed_log(
                campaign_dir,
                f"turn={campaign.turn_number} campaign_seed={campaign.seed} turn_seed={turn_seed} campaign={campaign.name}",
            )

        lines = [
            ln for ln in (campaign_dir / "seeds.log").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        assert len(lines) == 3
        assert "turn=1" in lines[0]
        assert "turn=2" in lines[1]
        assert "turn=3" in lines[2]


class TestCreateCampaignSeedLog:
    def test_create_campaign_writes_seeds_log(self, tmp_path, monkeypatch):
        """create_campaign() must write seeds.log inside the campaign folder."""
        from src.backend.core import campaign_manager

        monkeypatch.setattr(campaign_manager, "campaigns_root", lambda: tmp_path)
        meta = create_campaign("WebTest", created_by="user1", seed=321)

        campaign_dir = tmp_path / meta.id
        log = campaign_dir / "seeds.log"
        assert log.exists(), "seeds.log must be created by create_campaign"
        text = log.read_text(encoding="utf-8")
        assert f"seed={meta.seed}" in text
        assert "WebTest" in text
