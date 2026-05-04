"""API route definitions."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/public")
async def public():
    """Public welcome endpoint."""
    return {"message": "Welcome to the D&D 5e AI Game Engine API"}
