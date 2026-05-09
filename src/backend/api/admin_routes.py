"""Admin API endpoints — accessible only to users with is_admin=True."""

from fastapi import APIRouter, HTTPException, Request

from src.backend.core.auth import get_current_admin
from src.backend.core.campaign_manager import (
    delete_campaign,
    get_players,
    list_campaigns,
    load_campaign_world,
    remove_player,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/campaigns")
def admin_list_campaigns(request: Request):
    """Return all campaigns with their current player lists."""
    get_current_admin(request)
    campaigns = list_campaigns()
    result = []
    for meta in campaigns:
        players = get_players(meta.id)
        result.append({"meta": meta, "players": players})
    return result


@router.delete("/campaigns/{campaign_id}")
def admin_delete_campaign(campaign_id: str, request: Request):
    """Zip the campaign folder then permanently delete it."""
    get_current_admin(request)
    try:
        zip_name = delete_campaign(campaign_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"deleted": campaign_id, "archived_as": zip_name}


@router.delete("/campaigns/{campaign_id}/players/{user_id}")
def admin_remove_player(campaign_id: str, user_id: str, request: Request):
    """Remove a player (and their PC) from a campaign."""
    get_current_admin(request)
    found = remove_player(campaign_id, user_id)
    if not found:
        raise HTTPException(status_code=404, detail="Player not found in campaign")
    return {"removed": user_id, "campaign": campaign_id}


@router.get("/world/{campaign_id}")
def admin_get_world(campaign_id: str, request: Request):
    """Return all world objects for a campaign as a flat list."""
    get_current_admin(request)
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign world not found")
    objects = [
        {
            "id": obj.id,
            "parent": obj.parent,
            "type": obj.type,
            "name": obj.name,
            "description": obj.description,
        }
        for obj in campaign.world.objects.values()
    ]
    return {"campaign_id": campaign_id, "objects": objects}
