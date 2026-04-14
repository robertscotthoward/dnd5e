"""Game state models for the D&D 5e game engine."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .world import World


class EventLog(BaseModel):
    """A single event in the game log."""

    turn: int
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str  # e.g. "combat", "dialogue", "movement", "world"
    description: str
    actor_id: Optional[int] = None  # Object ID of the actor
    target_id: Optional[int] = None  # Object ID of the target
    dice_rolls: list[dict] = Field(default_factory=list)  # {die: "d20", result: 15, ...}
    seed: Optional[int] = None  # Random seed for this event


class Campaign(BaseModel):
    """
    A persistent game campaign.

    Contains the world state and event history.
    Everything (players, parties, items, locations) is stored in world.objects.
    """

    name: str
    seed: int  # Fixed seed for reproducibility
    world: World
    turn_number: int = 0
    event_log: list[EventLog] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_event(
        self,
        event_type: str,
        description: str,
        actor_id: Optional[int] = None,
        target_id: Optional[int] = None,
        dice_rolls: Optional[list[dict]] = None,
        seed: Optional[int] = None,
    ) -> EventLog:
        """Add an event to the log."""
        event = EventLog(
            turn=self.turn_number,
            event_type=event_type,
            description=description,
            actor_id=actor_id,
            target_id=target_id,
            dice_rolls=dice_rolls or [],
            seed=seed,
        )
        self.event_log.append(event)
        return event

    def advance_turn(self) -> int:
        """Advance to the next turn."""
        self.turn_number += 1
        self.updated_at = datetime.now()
        return self.turn_number


class GameState(BaseModel):
    """
    Current game state for the CLI session.

    Tracks the active campaign and provides session management.
    """

    campaign: Optional[Campaign] = None
    campaign_file: Optional[str] = None  # Path to the campaign YAML file

    def load_campaign(self, campaign: Campaign, file_path: str) -> None:
        """Load a campaign into the game state."""
        self.campaign = campaign
        self.campaign_file = file_path

    def unload_campaign(self) -> None:
        """Unload the current campaign."""
        self.campaign = None
        self.campaign_file = None

    @property
    def has_campaign(self) -> bool:
        return self.campaign is not None
