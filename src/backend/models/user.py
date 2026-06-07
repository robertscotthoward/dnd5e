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


class DeathSaves(BaseModel):
    successes: int = 0  # 0-3
    failures: int = 0   # 0-3


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
    conditions: list[str] = Field(default_factory=list)  # active D&D 5e conditions
    death_saves: DeathSaves = Field(default_factory=DeathSaves)
    location_ancestry: list[dict] = Field(default_factory=list)  # [{name, type}, ...] nearest first
    joined_at: str
    last_seen: Optional[str] = None

    @computed_field
    @property
    def health_status(self) -> str:
        if self.hp_max == 0:
            return "unknown"
        if self.hp_current <= 0:
            if self.death_saves.failures >= 2:
                return "dead"
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
    combat_queue: list[int] = Field(default_factory=list)  # ordered combatant IDs
    player_count: int = 0
    current_snapshot_id: Optional[str] = None  # snapshot we last restored to; parent for next snapshot
    # Day/night cycle
    day_number: int = 1
    hour_of_day: int = 9  # 0-23; campaign starts at 9 AM
    is_night: bool = False  # True when hour < 6 or hour >= 20


class Snapshot(BaseModel):
    id: str
    label: str
    campaign_id: str
    created_by: str
    created_at: str
    path: str  # relative path from data/campaigns root
    parent_snapshot: Optional[str] = None  # snapshot ID of the parent, or None for root
