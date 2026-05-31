"""Tests for snapshot tree — parent_snapshot tracking in create/list/restore."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.backend.core import campaign_manager
from src.backend.models.user import CampaignMeta

CAMPAIGN_ID = "tree-test-campaign"


def _make_meta(base: Path, campaign_id: str = CAMPAIGN_ID, current_snapshot_id: str = None) -> Path:
    """Write a minimal valid meta.json for a campaign."""
    camp_dir = base / campaign_id
    camp_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": campaign_id,
        "name": "Tree Campaign",
        "seed": 1,
        "turn_number": 1,
        "created_by": "tester",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    if current_snapshot_id:
        meta["current_snapshot_id"] = current_snapshot_id
    (camp_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return camp_dir


def _make_snap_meta(base: Path, snap_id: str, label: str, parent_snap_id: str = None) -> None:
    """Write a snapshot meta.json inside the campaign campaigns/ folder."""
    snap_dir = base / CAMPAIGN_ID / "campaigns" / snap_id
    snap_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": snap_id,
        "snapshot_label": label,
        "parent_snapshot": CAMPAIGN_ID,
        "parent_snapshot_id": parent_snap_id,
        "created_by": "tester",
        "created_at": "2026-01-01T10:00:00",
    }
    (snap_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_list_snapshots_exposes_parent_snapshot(tmp_path):
    """list_snapshots includes parent_snapshot field from meta."""
    _make_meta(tmp_path)
    _make_snap_meta(tmp_path, "aaa", "Root Snap", parent_snap_id=None)
    _make_snap_meta(tmp_path, "bbb", "Child Snap", parent_snap_id="aaa")

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        snaps = campaign_manager.list_snapshots(CAMPAIGN_ID)

    by_id = {s.id: s for s in snaps}
    assert by_id["aaa"].parent_snapshot is None
    assert by_id["bbb"].parent_snapshot == "aaa"


def test_create_snapshot_uses_current_snapshot_id_as_parent(tmp_path):
    """create_snapshot uses the live meta's current_snapshot_id as parent_snapshot_id."""
    camp_dir = _make_meta(tmp_path, current_snapshot_id="prev-snap")
    (camp_dir / "world.yaml").write_text("world: {}", encoding="utf-8")

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        snap = campaign_manager.create_snapshot(CAMPAIGN_ID, "New Snap", "tester")

    assert snap.parent_snapshot == "prev-snap"

    # Check that the stored meta.json reflects the parent
    snap_meta_path = camp_dir / "campaigns" / snap.id / "meta.json"
    stored = json.loads(snap_meta_path.read_text())
    assert stored["parent_snapshot_id"] == "prev-snap"


def test_create_snapshot_no_parent_when_no_current_snapshot(tmp_path):
    """create_snapshot produces parent_snapshot=None when no current_snapshot_id is set."""
    camp_dir = _make_meta(tmp_path)
    (camp_dir / "world.yaml").write_text("world: {}", encoding="utf-8")

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        snap = campaign_manager.create_snapshot(CAMPAIGN_ID, "Root Snap", "tester")

    assert snap.parent_snapshot is None


def test_restore_snapshot_sets_current_snapshot_id(tmp_path):
    """restore_snapshot updates live meta.current_snapshot_id to the restored snapshot ID."""
    camp_dir = _make_meta(tmp_path)
    snap_dir = camp_dir / "campaigns" / "snap1"
    snap_dir.mkdir(parents=True)
    (snap_dir / "world.yaml").write_text("world: snap", encoding="utf-8")
    snap_meta = {
        "id": "snap1",
        "snapshot_label": "Snap One",
        "created_by": "tester",
        "created_at": "2026-01-01T10:00:00",
        "parent_snapshot_id": None,
    }
    (snap_dir / "meta.json").write_text(json.dumps(snap_meta), encoding="utf-8")
    (camp_dir / "world.yaml").write_text("world: live", encoding="utf-8")

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        campaign_manager.restore_snapshot(CAMPAIGN_ID, "snap1")
        meta = campaign_manager.get_campaign_meta(CAMPAIGN_ID)

    assert meta.current_snapshot_id == "snap1"
