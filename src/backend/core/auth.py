"""Authentication utilities: password hashing, sessions, and FastAPI dependency."""

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request

from src.backend.models.user import Session

_CACHE = Path(__file__).parent.parent.parent.parent / "cache"
_USERS_FILE    = _CACHE / "users.json"
_SESSIONS_FILE = _CACHE / "sessions.json"

_SESSION_TTL = timedelta(days=7)


def _load_sessions_from_disk() -> dict[str, Session]:
    """Load persisted sessions, discarding any that have expired."""
    if not _SESSIONS_FILE.exists():
        return {}
    try:
        with open(_SESSIONS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        cutoff = datetime.now() - _SESSION_TTL
        result = {}
        for token, data in raw.items():
            session = Session(**data)
            if session.created_at >= cutoff:
                result[token] = session
        return result
    except Exception:
        return {}


def _save_sessions_to_disk() -> None:
    """Write the current session store to disk."""
    _CACHE.mkdir(parents=True, exist_ok=True)
    data = {token: s.model_dump(mode="json") for token, s in _sessions.items()}
    with open(_SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


# Session store: populated from disk at import time
_sessions: dict[str, Session] = _load_sessions_from_disk()


def hash_password(password: str, salt: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=260000,
    )
    return dk.hex()


def generate_salt() -> str:
    """Generate a random salt."""
    return secrets.token_hex(16)


def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash and salt."""
    return hash_password(password, salt) == stored_hash


def load_users() -> list[dict]:
    """Load users from cache/users.json. Creates the file if it does not exist."""
    if not _USERS_FILE.exists():
        _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": []}, f, indent=2)
        return []
    with open(_USERS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("users", [])


def save_users(users: list[dict]) -> None:
    """Persist the users list to cache/users.json."""
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_USERS_FILE, "w", encoding="utf-8") as f:
        json.dump({"users": users}, f, indent=2, default=str)


def find_user(username: str) -> Optional[dict]:
    """Find a user dict by username (case-insensitive)."""
    users = load_users()
    username_lower = username.lower()
    return next((u for u in users if u["username"].lower() == username_lower), None)


def register_user(username: str, password: str) -> tuple[bool, str, Optional[dict]]:
    """
    Register a new user.

    Returns:
        (success, message, user_dict)
    """
    if not username or len(username.strip()) < 3:
        return False, "Username must be at least 3 characters.", None
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters.", None

    username = username.strip()

    existing = find_user(username)
    if existing:
        return False, "Username already taken.", None

    salt = generate_salt()
    password_hash = hash_password(password, salt)

    user_id = secrets.token_hex(8)
    user = {
        "id": user_id,
        "username": username,
        "password_hash": password_hash,
        "salt": salt,
        "is_admin": False,
        "created_at": datetime.now().isoformat(),
    }

    users = load_users()
    users.append(user)
    save_users(users)

    return True, "User registered successfully.", user


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Authenticate a user by username and password.

    Returns the user dict on success, None on failure.
    """
    user = find_user(username)
    if not user:
        return None
    if not verify_password(password, user["salt"], user["password_hash"]):
        return None
    return user


def create_session(user_dict: dict) -> str:
    """
    Create a session for the given user and persist it to disk.

    Returns the session token string.
    """
    token = secrets.token_hex(32)
    session = Session(
        token=token,
        user_id=user_dict["id"],
        username=user_dict["username"],
        is_admin=user_dict.get("is_admin", user_dict.get("admin", False)),
    )
    _sessions[token] = session
    _save_sessions_to_disk()
    return token


def get_session(token: str) -> Optional[Session]:
    """Look up a session by token, returning None if missing or expired."""
    session = _sessions.get(token)
    if session is None:
        return None
    if datetime.now() - session.created_at > _SESSION_TTL:
        delete_session(token)
        return None
    return session


def delete_session(token: str) -> None:
    """Remove a session and persist the change to disk."""
    _sessions.pop(token, None)
    _save_sessions_to_disk()


def get_current_user(request: Request) -> Session:
    """
    FastAPI dependency that reads the session_token cookie and returns the Session.

    Raises HTTPException 401 if the cookie is missing or the session is invalid.
    """
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


def get_current_admin(request: Request) -> Session:
    """
    FastAPI dependency like get_current_user but also enforces is_admin.

    Raises HTTPException 403 if the user is not an admin.
    """
    session = get_current_user(request)
    if not session.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return session
