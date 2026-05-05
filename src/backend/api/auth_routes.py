"""Authentication API endpoints."""

from fastapi import APIRouter, HTTPException, Response, Request

from src.backend.models.user import RegisterRequest, LoginRequest, UserPublic
from src.backend.core.auth import (
    register_user,
    authenticate_user,
    create_session,
    delete_session,
    get_current_user,
)

router = APIRouter(tags=["auth"])

COOKIE_NAME = "session_token"
COOKIE_SETTINGS = dict(httponly=True, samesite="lax", secure=False, max_age=86400 * 7)


@router.post("/register")
def register(req: RegisterRequest, response: Response):
    """Register a new user and create a session cookie."""
    success, message, user = register_user(req.username, req.password)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    token = create_session(user)
    response.set_cookie(COOKIE_NAME, token, **COOKIE_SETTINGS)
    return {"user_id": user["id"], "username": user["username"]}


@router.post("/login")
def login(req: LoginRequest, response: Response):
    """Authenticate a user and create a session cookie."""
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session(user)
    response.set_cookie(COOKIE_NAME, token, **COOKIE_SETTINGS)
    return {"user_id": user["id"], "username": user["username"]}


@router.post("/logout")
def logout(request: Request, response: Response):
    """Destroy the session and clear the cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        delete_session(token)
    response.delete_cookie(COOKIE_NAME)
    return {"message": "Logged out"}


@router.get("/me")
def me(request: Request):
    """Return the currently authenticated user's info."""
    session = get_current_user(request)
    return {"user_id": session.user_id, "username": session.username}
