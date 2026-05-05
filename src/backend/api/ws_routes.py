"""WebSocket endpoint for real-time campaign chat and game events."""

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.backend.core.auth import get_session
from src.backend.core.campaign_manager import (
    append_chat,
    create_snapshot,
    get_campaign_meta,
    get_players,
    load_campaign_world,
    save_campaign_meta,
    save_campaign_world,
)
from src.backend.models.user import ChatMessage
from src.backend.core.tools import WorldTools
from src.backend.core.ai_client import ai_client

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """
    Manages active WebSocket connections grouped by campaign_id.

    Each connection is stored as a (WebSocket, username, character_name) tuple.
    """

    def __init__(self):
        # campaign_id -> list of (WebSocket, username, character_name)
        self._connections: dict[str, list[tuple[WebSocket, str, str]]] = {}

    async def connect(
        self,
        ws: WebSocket,
        campaign_id: str,
        username: str,
        char_name: str,
    ) -> None:
        """Accept a new WebSocket connection and register it."""
        await ws.accept()
        if campaign_id not in self._connections:
            self._connections[campaign_id] = []
        self._connections[campaign_id].append((ws, username, char_name))

    def disconnect(self, ws: WebSocket, campaign_id: str) -> None:
        """Remove a WebSocket from the connection registry."""
        if campaign_id in self._connections:
            self._connections[campaign_id] = [
                t for t in self._connections[campaign_id] if t[0] is not ws
            ]

    async def broadcast(self, campaign_id: str, message: dict) -> None:
        """Send a JSON message to every connected client in the campaign."""
        if campaign_id not in self._connections:
            return
        dead: list[WebSocket] = []
        for ws, uname, cname in list(self._connections[campaign_id]):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for dead_ws in dead:
            self.disconnect(dead_ws, campaign_id)

    async def send_personal(self, ws: WebSocket, message: dict) -> None:
        """Send a JSON message to a single WebSocket."""
        try:
            await ws.send_json(message)
        except Exception:
            pass

    def get_users(self, campaign_id: str) -> list[dict]:
        """Return the list of connected users for a campaign."""
        return [
            {"username": u, "character_name": c}
            for _, u, c in self._connections.get(campaign_id, [])
        ]


manager = ConnectionManager()


async def _run_dm_response(
    campaign_id: str,
    player_text: str,
    username: str,
    char_name: str,
) -> None:
    """
    Run the DM AI response in a thread-pool executor so it does not block the event loop.

    Broadcasts the resulting narration and an updated player list to all campaign clients.
    """
    meta = get_campaign_meta(campaign_id)
    if not meta:
        return
    campaign = load_campaign_world(campaign_id)
    if not campaign:
        return

    tools = WorldTools(campaign.world)

    # Strip "DM:" prefix if present
    situation = player_text
    if situation.upper().startswith("DM:"):
        situation = situation[3:].strip()

    try:
        narration = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: ai_client.generate_dm_response(campaign, situation, tools),
        )
    except Exception as e:
        narration = f"[DM is unavailable: {str(e)[:80]}]"

    save_campaign_world(campaign_id, campaign)

    # Update meta turn info
    meta.turn_number = campaign.turn_number
    meta.updated_at = datetime.now().isoformat()
    save_campaign_meta(meta)

    dm_msg = ChatMessage(
        sender="DM",
        sender_type="DM",
        text=narration,
        turn_number=campaign.turn_number,
    )
    append_chat(campaign_id, dm_msg)

    await manager.broadcast(
        campaign_id,
        {
            "type": "dm_response",
            "message": dm_msg.model_dump(mode="json"),
        },
    )

    # Broadcast refreshed player list with updated HP values
    players = get_players(campaign_id)
    await manager.broadcast(
        campaign_id,
        {
            "type": "player_list",
            "players": [p.model_dump(mode="json") for p in players],
        },
    )


@router.websocket("/ws/{campaign_id}")
async def campaign_websocket(campaign_id: str, websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time campaign interaction.

    Authenticates via the session_token cookie.  Supported message types:
      - chat:     Send a player message; DM AI triggers if text begins with "DM:" or "DM,"
      - action:   Declare a character action; always triggers DM AI
      - snapshot: Create a campaign snapshot
      - ping:     Keepalive; server replies with pong
    """
    # Authenticate via cookie
    token = websocket.cookies.get("session_token")
    if not token:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    session = get_session(token)
    if not session:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    meta = get_campaign_meta(campaign_id)
    if not meta:
        await websocket.close(code=1008, reason="Campaign not found")
        return

    # Determine character name for this user
    players = get_players(campaign_id)
    my_player = next((p for p in players if p.user_id == session.user_id), None)
    char_name = (
        (my_player.character_name or session.username) if my_player else session.username
    )

    await manager.connect(websocket, campaign_id, session.username, char_name)

    # Broadcast updated player list to everyone
    await manager.broadcast(
        campaign_id,
        {
            "type": "player_list",
            "players": [p.model_dump(mode="json") for p in players],
        },
    )

    # Send join confirmation to the new client
    await manager.send_personal(
        websocket,
        {
            "type": "joined",
            "campaign": meta.model_dump(mode="json"),
            "you": {"username": session.username, "character_name": char_name},
            "online_users": manager.get_users(campaign_id),
        },
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "")

            if msg_type == "chat":
                text = str(data.get("text", "")).strip()
                if not text:
                    continue

                # Save and broadcast the player's message
                pc_msg = ChatMessage(
                    sender=char_name,
                    sender_type="PC",
                    text=text,
                    turn_number=meta.turn_number,
                )
                append_chat(campaign_id, pc_msg)
                await manager.broadcast(
                    campaign_id,
                    {
                        "type": "chat",
                        "message": pc_msg.model_dump(mode="json"),
                    },
                )

                # Trigger DM AI if addressed to the Dungeon Master
                if text.upper().startswith("DM:") or text.upper().startswith("DM,"):
                    await manager.broadcast(
                        campaign_id,
                        {
                            "type": "dm_thinking",
                            "message": "The Dungeon Master is considering...",
                        },
                    )
                    asyncio.create_task(
                        _run_dm_response(campaign_id, text, session.username, char_name)
                    )

            elif msg_type == "action":
                action = str(data.get("action", ""))
                target_id = data.get("target_id")
                action_text = f"{char_name} performs: {action}" + (
                    f" targeting object #{target_id}" if target_id else ""
                )

                pc_msg = ChatMessage(
                    sender=char_name,
                    sender_type="PC",
                    text=f"[Action] {action}",
                    turn_number=meta.turn_number,
                )
                append_chat(campaign_id, pc_msg)
                await manager.broadcast(
                    campaign_id,
                    {
                        "type": "chat",
                        "message": pc_msg.model_dump(mode="json"),
                    },
                )
                await manager.broadcast(
                    campaign_id,
                    {"type": "dm_thinking", "message": "Resolving action..."},
                )
                asyncio.create_task(
                    _run_dm_response(campaign_id, action_text, session.username, char_name)
                )

            elif msg_type == "snapshot":
                label = str(data.get("label", f"Snapshot by {char_name}"))
                snap = create_snapshot(campaign_id, label, session.username)
                await manager.broadcast(
                    campaign_id,
                    {
                        "type": "snapshot_created",
                        "snapshot": snap.model_dump(mode="json"),
                    },
                )

            elif msg_type == "ping":
                await manager.send_personal(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, campaign_id)
        await manager.broadcast(
            campaign_id,
            {
                "type": "chat",
                "message": ChatMessage(
                    sender="SYSTEM",
                    sender_type="SYSTEM",
                    text=f"{char_name} has left the game.",
                    turn_number=meta.turn_number,
                ).model_dump(mode="json"),
            },
        )
