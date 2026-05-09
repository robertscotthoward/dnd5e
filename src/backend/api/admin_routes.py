"""Admin API endpoints — accessible only to users with is_admin=True."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.backend.core.auth import get_current_admin
from src.backend.core.campaign_manager import (
    delete_campaign,
    get_players,
    list_campaigns,
    load_campaign_world,
    remove_player,
    save_campaign_world,
)
from src.backend.models.world import Object


VIRTUAL_TYPES = {
    "system", "planet", "continent", "kingdom", "region",
    "town", "city", "village", "keep", "inn", "tavern", "shop",
    "temple", "guild", "dungeon", "district", "market", "palace",
    "wilderness", "forest", "mountain", "ruin", "room", "corridor",
    "courtyard", "tower", "party", "encounter", "sea", "ocean",
}

FIXED_TYPES = VIRTUAL_TYPES  # places don't move


class CreateWorldObjectRequest(BaseModel):
    parent: Optional[int] = None
    type: str
    name: str
    description: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)

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
            "properties": obj.properties,
        }
        for obj in campaign.world.objects.values()
    ]
    return {"campaign_id": campaign_id, "objects": objects}


@router.post("/world/{campaign_id}/objects")
def admin_create_world_object(
    campaign_id: str, body: CreateWorldObjectRequest, request: Request
):
    """Create a new world object inside a campaign."""
    get_current_admin(request)
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign world not found")
    if body.parent is not None and body.parent not in campaign.world.objects:
        raise HTTPException(status_code=400, detail="Parent object not found")

    obj = Object(
        id=campaign.world.next_id(),
        parent=body.parent,
        type=body.type,
        name=body.name,
        description=body.description,
        is_virtual=body.type in VIRTUAL_TYPES,
        is_moveable=body.type not in FIXED_TYPES,
        properties=body.properties,
    )
    campaign.world.add_object(obj)
    save_campaign_world(campaign_id, campaign)

    return {
        "id": obj.id,
        "parent": obj.parent,
        "type": obj.type,
        "name": obj.name,
        "description": obj.description,
        "properties": obj.properties,
    }


@router.delete("/world/{campaign_id}/objects/{object_id}")
def admin_delete_world_object(campaign_id: str, object_id: int, request: Request):
    """Delete a world object and all its descendants (cascade)."""
    get_current_admin(request)
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign world not found")
    if object_id not in campaign.world.objects:
        raise HTTPException(status_code=404, detail="Object not found")
    descendants = [d.id for d in campaign.world.get_descendants(object_id)]
    campaign.world.delete_object(object_id, cascade=True)
    save_campaign_world(campaign_id, campaign)
    return {"deleted_id": object_id, "deleted_descendants": descendants}
