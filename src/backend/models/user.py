"""User, session, campaign, and chat data models."""

import secrets
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class User(BaseModel):
    id: str = Field(default_factory=lambda: secrets.token_hex(8))
    username: str
    password_hash: str
    salt: str
    created_at: datetime = Field(default_factory=datetime.now)


class UserPublic(BaseModel):
    id: str
    username: str
    created_at: datetime


class Session(BaseModel):
    token: str
    user_id: str
    username: str
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.now)


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class CharacterCreate(BaseModel):
    name: str
    race: str
    class_type: str
    region: str
    background: Optional[str] = None  # None = AI generates it
    abilities: Optional[dict[str, int]] = None  # None = server generates random


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: secrets.token_hex(6))
    sender: str          # character name or "DM" or "SYSTEM"
    sender_type: str     # "PC", "NPC", "DM", "SYSTEM"
    text: str
    turn_number: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


class CampaignPlayer(BaseModel):
    user_id: str
    username: str
    character_object_id: Optional[int] = None
    character_name: Optional[str] = None
    race: Optional[str] = None
    class_type: Optional[str] = None
    hp_current: int = 0
    hp_max: int = 0
    encumbrance_current: float = 0.0
    encumbrance_max: float = 150.0  # default STR 10 * 15
    joined_at: str
    last_seen: Optional[str] = None

    @computed_field
    @property
    def health_status(self) -> str:
        if self.hp_max == 0:
            return "unknown"
        if self.hp_current <= 0:
            return "unconscious"
        pct = self.hp_current / self.hp_max
        if pct > 0.5:
            return "healthy"
        if pct > 0.25:
            return "bloodied"
        return "critical"

    @computed_field
    @property
    def hp_percent(self) -> float:
        if self.hp_max == 0:
            return 0.0
        return max(0.0, min(100.0, (self.hp_current / self.hp_max) * 100))


class CampaignMeta(BaseModel):
    id: str  # slug (folder name)
    name: str
    seed: int = 0
    turn_number: int = 0
    game_mode: str = "Exploration"  # Exploration, Social, Travel, Combat
    created_by: str = ""
    created_at: str
    updated_at: str
    parent_snapshot: Optional[str] = None
    snapshot_label: Optional[str] = None
    active_player_turn: Optional[int] = None  # object_id during combat
    player_count: int = 0


class Snapshot(BaseModel):
    id: str
    label: str
    campaign_id: str
    created_by: str
    created_at: str
    path: str  # relative path from data/campaigns root
