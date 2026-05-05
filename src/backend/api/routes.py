"""Main API router - includes all sub-routers."""

from fastapi import APIRouter

from src.backend.api.auth_routes import router as auth_router
from src.backend.api.campaign_routes import router as campaign_router
from src.backend.api.ws_routes import router as ws_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth")
router.include_router(campaign_router)
router.include_router(ws_router)


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/public")
async def public():
    return {"message": "Welcome to the D&D 5e AI Game Engine API"}
