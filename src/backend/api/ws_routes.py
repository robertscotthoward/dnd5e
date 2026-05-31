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
            lambda: ai_client.generate_dm_response(campaign, situation, tools, meta),
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

    # Broadcast updated combat state if still in Combat mode
    if meta.game_mode == "Combat":
        # Build initiative_order with names for the frontend tracker
        world_snap = load_campaign_world(campaign_id)
        initiative_order = []
        for obj_id in meta.combat_queue:
            obj = world_snap.world.get_object(obj_id) if world_snap else None
            initiative_order.append({
                "id": obj_id,
                "name": (obj.name if obj else f"Combatant #{obj_id}"),
                "initiative": obj.properties.get("initiative", 0) if obj else 0,
            })
        await manager.broadcast(
            campaign_id,
            {
                "type": "combat_state",
                "active_turn": meta.active_player_turn,
                "combat_queue": meta.combat_queue,
                "initiative_order": initiative_order,
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

                # Reload meta for current game mode
                meta = get_campaign_meta(campaign_id) or meta

                # Combat turn enforcement: only the active combatant may send
                # commands that trigger the DM during Combat mode.
                if meta.game_mode == "Combat":
                    active_id = meta.active_player_turn
                    campaign_for_check = load_campaign_world(campaign_id)
                    active_obj = (
                        campaign_for_check.world.get_object(active_id)
                        if (campaign_for_check and active_id is not None)
                        else None
                    )
                    active_char_name = active_obj.name if active_obj else None

                    if active_char_name and char_name != active_char_name:
                        await manager.send_personal(
                            websocket,
                            {
                                "type": "not_your_turn",
                                "message": f"It is {active_char_name}'s turn. Please wait.",
                                "active_character": active_char_name,
                            },
                        )
                        await manager.broadcast(
                            campaign_id,
                            {
                                "type": "waiting_for_turn",
                                "message": f"Waiting for {active_char_name} to act.",
                                "active_character": active_char_name,
                            },
                        )
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

                # Player message triggers the DM agent
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

                # Reload meta to get latest game_mode and active_player_turn
                meta = get_campaign_meta(campaign_id) or meta

                # Combat turn enforcement: only the active combatant may act
                if meta.game_mode == "Combat":
                    active_id = meta.active_player_turn
                    # Resolve the active combatant's character name from the world
                    campaign_for_check = load_campaign_world(campaign_id)
                    active_obj = (
                        campaign_for_check.world.get_object(active_id)
                        if (campaign_for_check and active_id is not None)
                        else None
                    )
                    active_char_name = active_obj.name if active_obj else None

                    if active_char_name and char_name != active_char_name:
                        # Not this player's turn — reject and notify sender; broadcast to others
                        await manager.send_personal(
                            websocket,
                            {
                                "type": "not_your_turn",
                                "message": f"It is {active_char_name}'s turn. Please wait.",
                                "active_character": active_char_name,
                            },
                        )
                        await manager.broadcast(
                            campaign_id,
                            {
                                "type": "waiting_for_turn",
                                "message": f"Waiting for {active_char_name} to act.",
                                "active_character": active_char_name,
                            },
                        )
                        continue

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

            elif msg_type == "award_xp":
                char_id = data.get("character_id")
                xp_amount = data.get("amount", 0)
                reason = data.get("reason", "")
                if not isinstance(char_id, int) or xp_amount <= 0:
                    await manager.send_personal(
                        websocket,
                        {"type": "error", "message": "award_xp requires integer character_id and positive amount"},
                    )
                else:
                    campaign_xp = load_campaign_world(campaign_id)
                    if campaign_xp:
                        from src.backend.core.tools import WorldTools
                        from src.backend.core.campaign_manager import append_chat as _append_chat
                        from src.backend.models.user import ChatMessage as _ChatMessage
                        tools_xp = WorldTools(campaign_xp.world)
                        xp_result = tools_xp.award_xp(char_id, xp_amount)
                        if xp_result.success:
                            save_campaign_world(campaign_id, campaign_xp)
                            reason_text = f" ({reason})" if reason else ""
                            sys_msg = _ChatMessage(
                                sender="SYSTEM",
                                sender_type="SYSTEM",
                                text=f"{xp_amount} XP awarded{reason_text}. "
                                     f"Total: {xp_result.data['new_xp']} XP "
                                     f"(Level {xp_result.data['new_level']}).",
                                turn_number=meta.turn_number,
                            )
                            _append_chat(campaign_id, sys_msg)
                            await manager.broadcast(
                                campaign_id,
                                {
                                    "type": "xp_awarded",
                                    "data": xp_result.data,
                                    "message": sys_msg.model_dump(mode="json"),
                                },
                            )
                            if xp_result.data.get("level_up"):
                                await manager.broadcast(
                                    campaign_id,
                                    {
                                        "type": "level_up",
                                        "level_up": xp_result.data["level_up"],
                                    },
                                )

            elif msg_type == "death_save":
                char_id = data.get("character_id")
                if not isinstance(char_id, int):
                    await manager.send_personal(
                        websocket,
                        {"type": "error", "message": "death_save requires integer character_id"},
                    )
                else:
                    ds_campaign = load_campaign_world(campaign_id)
                    if ds_campaign:
                        from src.backend.core.tools import WorldTools as _WorldTools
                        ds_tools = _WorldTools(ds_campaign.world)
                        ds_result = ds_tools.roll_death_save(char_id)
                        if ds_result.success:
                            save_campaign_world(campaign_id, ds_campaign)
                            ds_msg = ChatMessage(
                                sender="DM",
                                sender_type="DM",
                                text=ds_result.message,
                                turn_number=meta.turn_number,
                            )
                            append_chat(campaign_id, ds_msg)
                            await manager.broadcast(
                                campaign_id,
                                {
                                    "type": "death_save_result",
                                    "data": ds_result.data,
                                    "message": ds_msg.model_dump(mode="json"),
                                    "dice_roll": {
                                        "die": "d20",
                                        "result": ds_result.data.get("roll"),
                                    },
                                },
                            )
                            # Refresh player list so death_saves pips update
                            ds_players = get_players(campaign_id)
                            await manager.broadcast(
                                campaign_id,
                                {
                                    "type": "player_list",
                                    "players": [p.model_dump(mode="json") for p in ds_players],
                                },
                            )
                        else:
                            await manager.send_personal(
                                websocket,
                                {"type": "error", "message": ds_result.message},
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
