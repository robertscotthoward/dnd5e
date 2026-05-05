"""Authentication utilities: password hashing, sessions, and FastAPI dependency."""

import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request

from src.backend.models.user import Session

# In-memory session store: token -> Session
_sessions: dict[str, Session] = {}

# Path to the users JSON file: 4 levels up from src/backend/core/ is the project root
_USERS_FILE = Path(__file__).parent.parent.parent.parent / "cache" / "users.json"


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
    from datetime import datetime
    user = {
        "id": user_id,
        "username": username,
        "password_hash": password_hash,
        "salt": salt,
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
    Create an in-memory session for the given user.

    Returns the session token string.
    """
    token = secrets.token_hex(32)
    session = Session(
        token=token,
        user_id=user_dict["id"],
        username=user_dict["username"],
    )
    _sessions[token] = session
    return token


def get_session(token: str) -> Optional[Session]:
    """Look up a session by token. Returns None if not found."""
    return _sessions.get(token)


def delete_session(token: str) -> None:
    """Remove a session from memory."""
    _sessions.pop(token, None)


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
