"""Campaign folder manager - handles all campaign persistence on disk."""

import json
import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.backend.models.user import CampaignMeta, CampaignPlayer, ChatMessage, Snapshot
from src.backend.core.campaign_io import load_campaign_from_file, save_campaign, new_campaign_object


def campaigns_root() -> Path:
    """Return the root directory where all campaign folders live."""
    return Path(__file__).parent.parent.parent.parent / "data" / "campaigns"


def campaign_path(campaign_id: str) -> Path:
    """Return the path to a specific campaign folder."""
    return campaigns_root() / campaign_id


def slugify(name: str) -> str:
    """Convert a campaign name to a filesystem-safe slug."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-")


def list_campaigns() -> list[CampaignMeta]:
    """List all top-level campaigns (not snapshots) from their meta.json."""
    root = campaigns_root()
    if not root.exists():
        return []
    result = []
    for d in sorted(root.iterdir()):
        if d.is_dir():
            meta_file = d / "meta.json"
            if meta_file.exists():
                with open(meta_file, encoding="utf-8") as f:
                    data = json.load(f)
                result.append(CampaignMeta(**data))
    return result


def get_campaign_meta(campaign_id: str) -> Optional[CampaignMeta]:
    """Load and return the CampaignMeta for a campaign, or None if not found."""
    p = campaign_path(campaign_id) / "meta.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return CampaignMeta(**json.load(f))


def save_campaign_meta(meta: CampaignMeta) -> None:
    """Write the CampaignMeta to meta.json inside the campaign folder."""
    p = campaign_path(meta.id)
    p.mkdir(parents=True, exist_ok=True)
    with open(p / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta.model_dump(), f, indent=2, default=str)


def load_campaign_world(campaign_id: str):
    """Load the Campaign object from world.yaml inside the campaign folder."""
    world_path = campaign_path(campaign_id) / "world.yaml"
    if not world_path.exists():
        return None
    return load_campaign_from_file(world_path)


def save_campaign_world(campaign_id: str, campaign) -> None:
    """Save the Campaign object to world.yaml inside the campaign folder."""
    campaign_path(campaign_id).mkdir(parents=True, exist_ok=True)
    save_campaign(campaign, campaign_path(campaign_id) / "world.yaml")


def get_raw_players(campaign_id: str) -> list[dict]:
    """Return the raw list of player dicts from players.json."""
    p = campaign_path(campaign_id) / "players.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("players", [])


def save_raw_players(campaign_id: str, players: list[dict]) -> None:
    """Persist the raw player dicts to players.json."""
    p = campaign_path(campaign_id)
    p.mkdir(parents=True, exist_ok=True)
    with open(p / "players.json", "w", encoding="utf-8") as f:
        json.dump({"players": players}, f, indent=2, default=str)


def get_players(campaign_id: str) -> list[CampaignPlayer]:
    """
    Return a list of CampaignPlayer objects, enriched with live HP and encumbrance
    data read from the world.yaml.
    """
    raw_players = get_raw_players(campaign_id)
    campaign = load_campaign_world(campaign_id)
    result = []
    for rp in raw_players:
        cp = CampaignPlayer(**rp)
        if campaign and cp.character_object_id is not None:
            obj = campaign.world.get_object(cp.character_object_id)
            if obj:
                hp = obj.properties.get("hp", {})
                cp.hp_current = hp.get("current", 0)
                cp.hp_max = hp.get("max", 0)
                cp.character_name = obj.name or cp.character_name
                cp.race = obj.properties.get("race", cp.race)
                classes = obj.properties.get("classes", [])
                if classes:
                    cp.class_type = classes[0].get("type", cp.class_type)
                # Encumbrance: sum weight of all children (inventory)
                children = campaign.world.get_children(cp.character_object_id)
                total_weight = sum(c.weight for c in children)
                str_score = obj.properties.get("abilities", {}).get("str", 10)
                cp.encumbrance_current = total_weight
                cp.encumbrance_max = str_score * 15.0
        result.append(cp)
    return result


def add_player(campaign_id: str, user_id: str, username: str) -> dict:
    """
    Add a user to the campaign (or update last_seen if already joined).

    Returns the raw player dict.
    """
    players = get_raw_players(campaign_id)
    existing = next((p for p in players if p["user_id"] == user_id), None)
    if existing:
        existing["last_seen"] = datetime.now().isoformat()
        save_raw_players(campaign_id, players)
        return existing
    player = {
        "user_id": user_id,
        "username": username,
        "character_object_id": None,
        "character_name": None,
        "race": None,
        "class_type": None,
        "hp_current": 0,
        "hp_max": 0,
        "encumbrance_current": 0.0,
        "encumbrance_max": 150.0,
        "joined_at": datetime.now().isoformat(),
        "last_seen": datetime.now().isoformat(),
    }
    players.append(player)
    save_raw_players(campaign_id, players)
    # Update player count in meta
    meta = get_campaign_meta(campaign_id)
    if meta:
        meta.player_count = len(players)
        save_campaign_meta(meta)
    return player


def find_player(campaign_id: str, user_id: str) -> Optional[dict]:
    """Find a raw player dict by user_id, or None if not found."""
    players = get_raw_players(campaign_id)
    return next((p for p in players if p["user_id"] == user_id), None)


def update_player_character(
    campaign_id: str,
    user_id: str,
    character_object_id: int,
    character_name: str,
    race: str,
    class_type: str,
    hp_current: int,
    hp_max: int,
) -> None:
    """Update the character fields on a player record in players.json."""
    players = get_raw_players(campaign_id)
    for p in players:
        if p["user_id"] == user_id:
            p["character_object_id"] = character_object_id
            p["character_name"] = character_name
            p["race"] = race
            p["class_type"] = class_type
            p["hp_current"] = hp_current
            p["hp_max"] = hp_max
            break
    save_raw_players(campaign_id, players)


def get_chat(campaign_id: str, limit: int = 100) -> list[ChatMessage]:
    """Return up to `limit` recent chat messages for the campaign."""
    p = campaign_path(campaign_id) / "chat.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    messages = data.get("messages", [])[-limit:]
    return [ChatMessage(**m) for m in messages]


def append_chat(campaign_id: str, message: ChatMessage) -> None:
    """Append a single ChatMessage to chat.json."""
    p = campaign_path(campaign_id)
    p.mkdir(parents=True, exist_ok=True)
    chat_file = p / "chat.json"
    if chat_file.exists():
        with open(chat_file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"messages": []}
    data["messages"].append(message.model_dump(mode="json"))
    with open(chat_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def create_campaign(name: str, created_by: str, seed: Optional[int] = None) -> CampaignMeta:
    """
    Create a new campaign folder with world.yaml, meta.json, players.json, and chat.json.

    Returns the CampaignMeta for the newly-created campaign.
    """
    campaign_id = slugify(name)
    path = campaign_path(campaign_id)
    if path.exists():
        # Append a random suffix if the name is already taken
        campaign_id = f"{campaign_id}-{secrets.token_hex(3)}"
        path = campaign_path(campaign_id)
    path.mkdir(parents=True, exist_ok=True)

    # Create world
    campaign_obj = new_campaign_object(name, seed)
    save_campaign(campaign_obj, path / "world.yaml")

    # Create meta
    now = datetime.now().isoformat()
    meta = CampaignMeta(
        id=campaign_id,
        name=name,
        seed=campaign_obj.seed,
        turn_number=0,
        game_mode="Exploration",
        created_by=created_by,
        created_at=now,
        updated_at=now,
        player_count=0,
    )
    save_campaign_meta(meta)

    # Empty players list and chat log
    save_raw_players(campaign_id, [])
    with open(path / "chat.json", "w", encoding="utf-8") as f:
        json.dump({"messages": []}, f)

    return meta


def list_snapshots(campaign_id: str) -> list[Snapshot]:
    """List all snapshots stored under the campaign's campaigns/ subdirectory."""
    snapshots_dir = campaign_path(campaign_id) / "campaigns"
    if not snapshots_dir.exists():
        return []
    result = []
    for d in sorted(snapshots_dir.iterdir()):
        if d.is_dir():
            meta_file = d / "meta.json"
            if meta_file.exists():
                with open(meta_file, encoding="utf-8") as f:
                    meta = json.load(f)
                result.append(
                    Snapshot(
                        id=meta.get("id", d.name),
                        label=meta.get("snapshot_label", d.name),
                        campaign_id=campaign_id,
                        created_by=meta.get("created_by", ""),
                        created_at=meta.get("created_at", ""),
                        path=str(d.relative_to(campaigns_root())),
                    )
                )
    return result


def create_snapshot(campaign_id: str, label: str, created_by: str) -> Snapshot:
    """
    Copy the campaign's key files into a campaigns/<snap_id>/ subdirectory.

    Returns a Snapshot describing the newly-created snapshot.
    """
    snap_id = secrets.token_hex(4)
    src = campaign_path(campaign_id)
    dst = src / "campaigns" / snap_id
    dst.mkdir(parents=True, exist_ok=True)

    # Copy key files into the snapshot folder
    for fname in ["world.yaml", "players.json", "chat.json", "meta.json"]:
        if (src / fname).exists():
            shutil.copy2(src / fname, dst / fname)

    # Update the snapshot copy's meta
    now = datetime.now().isoformat()
    snap_meta_file = dst / "meta.json"
    if snap_meta_file.exists():
        with open(snap_meta_file, encoding="utf-8") as f:
            snap_meta = json.load(f)
    else:
        snap_meta = {}

    snap_meta["id"] = snap_id
    snap_meta["snapshot_label"] = label
    snap_meta["parent_snapshot"] = campaign_id
    snap_meta["created_by"] = created_by
    snap_meta["created_at"] = now

    with open(snap_meta_file, "w", encoding="utf-8") as f:
        json.dump(snap_meta, f, indent=2)

    return Snapshot(
        id=snap_id,
        label=label,
        campaign_id=campaign_id,
        created_by=created_by,
        created_at=now,
        path=str((src / "campaigns" / snap_id).relative_to(campaigns_root())),
    )
