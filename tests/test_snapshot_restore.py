"""Tests for snapshot restore — backend function and HTTP endpoint."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.backend.main import create_app
from src.backend.models.user import CampaignMeta, Snapshot

CAMPAIGN_ID = "test-restore-campaign"
SNAPSHOT_ID = "abcd1234"

FAKE_META = CampaignMeta(
    id=CAMPAIGN_ID,
    name="Restore Campaign",
    seed=42,
    turn_number=5,
    created_by="tester",
    created_at="2026-01-01T00:00:00",
    updated_at="2026-01-01T00:00:00",
)

FAKE_SESSION = MagicMock()
FAKE_SESSION.user_id = "u1"
FAKE_SESSION.username = "tester"


# ---------------------------------------------------------------------------
# Unit tests for campaign_manager.restore_snapshot
# ---------------------------------------------------------------------------


def _build_campaign_dir(base: Path) -> tuple[Path, Path]:
    """Create a minimal campaign folder structure under base and return (campaign_dir, snap_dir)."""
    campaign_dir = base / CAMPAIGN_ID
    snap_dir = campaign_dir / "campaigns" / SNAPSHOT_ID
    snap_dir.mkdir(parents=True)

    # Snapshot files
    (snap_dir / "world.yaml").write_text("world: snapshot", encoding="utf-8")
    (snap_dir / "players.json").write_text(json.dumps({"players": []}), encoding="utf-8")
    (snap_dir / "chat.json").write_text(json.dumps({"messages": []}), encoding="utf-8")
    (snap_dir / "meta.json").write_text(
        json.dumps({
            "id": SNAPSHOT_ID,
            "snapshot_label": "Before the Dragon",
            "parent_snapshot": CAMPAIGN_ID,
            "created_by": "tester",
            "created_at": "2026-01-01T10:00:00",
        }),
        encoding="utf-8",
    )

    # Live campaign files (will be overwritten on restore)
    (campaign_dir / "world.yaml").write_text("world: live", encoding="utf-8")
    (campaign_dir / "players.json").write_text(json.dumps({"players": [{"user_id": "u99"}]}), encoding="utf-8")
    (campaign_dir / "chat.json").write_text(json.dumps({"messages": [{"text": "live msg"}]}), encoding="utf-8")
    (campaign_dir / "meta.json").write_text(
        json.dumps({
            "id": CAMPAIGN_ID,
            "name": "Restore Campaign",
            "seed": 42,
            "turn_number": 5,
            "created_by": "tester",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T09:00:00",
        }),
        encoding="utf-8",
    )

    return campaign_dir, snap_dir


def test_restore_snapshot_copies_files(tmp_path):
    """restore_snapshot copies world.yaml, players.json, and chat.json from snap to campaign root."""
    from src.backend.core import campaign_manager

    campaign_dir, _ = _build_campaign_dir(tmp_path)

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        campaign_manager.restore_snapshot(CAMPAIGN_ID, SNAPSHOT_ID)

    assert (campaign_dir / "world.yaml").read_text() == "world: snapshot"
    assert json.loads((campaign_dir / "players.json").read_text())["players"] == []
    assert json.loads((campaign_dir / "chat.json").read_text())["messages"] == []


def test_restore_snapshot_preserves_meta(tmp_path):
    """restore_snapshot does NOT overwrite meta.json (campaign identity is preserved)."""
    from src.backend.core import campaign_manager

    campaign_dir, _ = _build_campaign_dir(tmp_path)

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        campaign_manager.restore_snapshot(CAMPAIGN_ID, SNAPSHOT_ID)

    live_meta = json.loads((campaign_dir / "meta.json").read_text())
    assert live_meta["turn_number"] == 5  # original live meta unchanged
    assert live_meta["id"] == CAMPAIGN_ID


def test_restore_snapshot_returns_snapshot_object(tmp_path):
    """restore_snapshot returns a Snapshot with the correct id and label."""
    from src.backend.core import campaign_manager

    _build_campaign_dir(tmp_path)

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        snap = campaign_manager.restore_snapshot(CAMPAIGN_ID, SNAPSHOT_ID)

    assert snap.id == SNAPSHOT_ID
    assert snap.label == "Before the Dragon"
    assert snap.campaign_id == CAMPAIGN_ID
    assert snap.created_by == "tester"


def test_restore_snapshot_raises_if_campaign_missing(tmp_path):
    """restore_snapshot raises FileNotFoundError when the campaign folder does not exist."""
    from src.backend.core import campaign_manager

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        with pytest.raises(FileNotFoundError, match="not found"):
            campaign_manager.restore_snapshot("nonexistent", SNAPSHOT_ID)


def test_restore_snapshot_raises_if_snapshot_missing(tmp_path):
    """restore_snapshot raises FileNotFoundError when the snapshot subfolder does not exist."""
    from src.backend.core import campaign_manager

    _build_campaign_dir(tmp_path)

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        with pytest.raises(FileNotFoundError, match="not found"):
            campaign_manager.restore_snapshot(CAMPAIGN_ID, "deadbeef")


def test_restore_snapshot_partial_files(tmp_path):
    """restore_snapshot copies only files that exist in the snapshot (no error if chat.json absent)."""
    from src.backend.core import campaign_manager

    campaign_dir = tmp_path / CAMPAIGN_ID
    snap_dir = campaign_dir / "campaigns" / SNAPSHOT_ID
    snap_dir.mkdir(parents=True)

    # Only world.yaml and meta in snapshot
    (snap_dir / "world.yaml").write_text("world: partial", encoding="utf-8")
    (snap_dir / "meta.json").write_text(
        json.dumps({
            "id": SNAPSHOT_ID,
            "snapshot_label": "Partial Snap",
            "created_by": "tester",
            "created_at": "2026-01-01T10:00:00",
        }),
        encoding="utf-8",
    )

    (campaign_dir / "world.yaml").write_text("world: live", encoding="utf-8")
    (campaign_dir / "meta.json").write_text(json.dumps({"id": CAMPAIGN_ID}), encoding="utf-8")

    with patch.object(campaign_manager, "campaigns_root", return_value=tmp_path):
        snap = campaign_manager.restore_snapshot(CAMPAIGN_ID, SNAPSHOT_ID)

    assert (campaign_dir / "world.yaml").read_text() == "world: partial"
    assert snap.label == "Partial Snap"


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    app = create_app()
    with patch("src.backend.api.campaign_routes.get_current_user", return_value=FAKE_SESSION):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


def test_restore_endpoint_success(client):
    """POST .../snapshots/{id}/restore returns 200 with restored=True and snapshot data."""
    fake_snap = Snapshot(
        id=SNAPSHOT_ID,
        label="Before the Dragon",
        campaign_id=CAMPAIGN_ID,
        created_by="tester",
        created_at="2026-01-01T10:00:00",
        path=f"{CAMPAIGN_ID}/campaigns/{SNAPSHOT_ID}",
    )

    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch("src.backend.api.campaign_routes.restore_snapshot", return_value=fake_snap) as mock_restore:
        res = client.post(f"/api/campaigns/{CAMPAIGN_ID}/snapshots/{SNAPSHOT_ID}/restore")

    assert res.status_code == 200
    data = res.json()
    assert data["restored"] is True
    assert data["snapshot"]["id"] == SNAPSHOT_ID
    assert data["snapshot"]["label"] == "Before the Dragon"
    mock_restore.assert_called_once_with(CAMPAIGN_ID, SNAPSHOT_ID)


def test_restore_endpoint_campaign_not_found(client):
    """POST .../restore returns 404 when campaign does not exist."""
    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=None):
        res = client.post(f"/api/campaigns/missing/snapshots/{SNAPSHOT_ID}/restore")

    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_restore_endpoint_snapshot_not_found(client):
    """POST .../restore returns 404 when snapshot does not exist."""
    with patch("src.backend.api.campaign_routes.get_campaign_meta", return_value=FAKE_META), \
         patch(
             "src.backend.api.campaign_routes.restore_snapshot",
             side_effect=FileNotFoundError("Snapshot 'bad' not found in campaign 'x'"),
         ):
        res = client.post(f"/api/campaigns/{CAMPAIGN_ID}/snapshots/bad/restore")

    assert res.status_code == 404


def test_restore_endpoint_requires_auth():
    """POST .../restore returns non-200 when the user is not authenticated."""
    from fastapi import HTTPException

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        with patch(
            "src.backend.api.campaign_routes.get_current_user",
            side_effect=HTTPException(status_code=401, detail="Not authenticated"),
        ):
            res = c.post(f"/api/campaigns/{CAMPAIGN_ID}/snapshots/{SNAPSHOT_ID}/restore")
    assert res.status_code == 401
