"""WebSocket endpoint for real-time campaign chat and game events."""

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.backend.core.auth import get_session
from src.backend.core.campaign_manager import (
    append_chat,
    append_journal,
    create_snapshot,
    get_campaign_meta,
    get_players,
    load_campaign_world,
    save_campaign_meta,
    save_campaign_world,
)
from src.backend.models.user import ChatMessage
from src.backend.core.tools import WorldTools
from src.backend.core.loot import generate_loot
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

    # Generate and append a journal entry for this turn
    try:
        player_names = [p.character_name or p.username for p in get_players(campaign_id) if p.character_name or p.username]
        journal_entry = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: ai_client.generate_journal_entry(
                campaign_name=meta.name,
                turn_number=meta.turn_number,
                narration=narration,
                player_names=player_names,
            ),
        )
        append_journal(campaign_id, meta.turn_number, journal_entry)
        await manager.broadcast(
            campaign_id,
            {
                "type": "journal_updated",
                "turn_number": meta.turn_number,
                "entry": journal_entry,
            },
        )
    except Exception:
        pass

    # Broadcast updated NPC relationship list after each DM turn
    try:
        npc_world = load_campaign_world(campaign_id)
        if npc_world:
            from src.backend.core.tools import WorldTools as _WorldTools
            _npc_tools = _WorldTools(npc_world.world)
            _npc_result = _npc_tools.get_npc_relationships()
            for _npc in _npc_result.data["npcs"]:
                await manager.broadcast(
                    campaign_id,
                    {"type": "npc_updated", "npc": _npc},
                )
    except Exception:
        pass

    # Detect all-enemies-dead: if in Combat mode, check whether every NPC in
    # the combat queue has HP <= 0.  If so, generate loot and broadcast.
    if meta.game_mode == "Combat" and meta.combat_queue:
        world_for_loot = load_campaign_world(campaign_id)
        if world_for_loot:
            pcs = {obj.id for obj in world_for_loot.world.get_pcs()}
            enemies_in_queue = [
                world_for_loot.world.get_object(oid)
                for oid in meta.combat_queue
                if oid not in pcs
            ]
            enemies_in_queue = [e for e in enemies_in_queue if e is not None]
            all_enemies_dead = (
                bool(enemies_in_queue)
                and all(e.is_dead for e in enemies_in_queue)
            )
            if all_enemies_dead:
                # Find a suitable loot container: the party object or world root
                parties = world_for_loot.world.get_parties()
                loot_parent_id = parties[0].id if parties else 1
                loot_summary = generate_loot(
                    enemies=enemies_in_queue,
                    world=world_for_loot.world,
                    loot_container_parent_id=loot_parent_id,
                )
                save_campaign_world(campaign_id, world_for_loot)
                loot_msg = ChatMessage(
                    sender="SYSTEM",
                    sender_type="SYSTEM",
                    text=(
                        f"Victory! All enemies defeated. "
                        f"Loot recovered: {len(loot_summary['items'])} item(s)."
                    ),
                    turn_number=meta.turn_number,
                )
                append_chat(campaign_id, loot_msg)
                await manager.broadcast(
                    campaign_id,
                    {
                        "type": "loot_summary",
                        "loot": loot_summary,
                        "message": loot_msg.model_dump(mode="json"),
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

            elif msg_type == "take_loot":
                item_id = data.get("item_id")
                character_id = data.get("character_id")
                if not isinstance(item_id, int) or not isinstance(character_id, int):
                    await manager.send_personal(
                        websocket,
                        {"type": "error", "message": "take_loot requires integer item_id and character_id"},
                    )
                else:
                    loot_campaign = load_campaign_world(campaign_id)
                    if loot_campaign:
                        loot_tools = WorldTools(loot_campaign.world)
                        move_result = loot_tools.move_object(item_id, character_id)
                        if move_result.success:
                            save_campaign_world(campaign_id, loot_campaign)
                            char_obj = loot_campaign.world.get_object(character_id)
                            char_name_loot = char_obj.name if char_obj else f"Character #{character_id}"
                            item_obj = loot_campaign.world.get_object(item_id)
                            item_name_loot = item_obj.name if item_obj else f"Item #{item_id}"
                            take_msg = ChatMessage(
                                sender="SYSTEM",
                                sender_type="SYSTEM",
                                text=f"{char_name_loot} takes {item_name_loot}.",
                                turn_number=meta.turn_number,
                            )
                            append_chat(campaign_id, take_msg)
                            await manager.broadcast(
                                campaign_id,
                                {
                                    "type": "loot_taken",
                                    "item_id": item_id,
                                    "character_id": character_id,
                                    "character_name": char_name_loot,
                                    "message": take_msg.model_dump(mode="json"),
                                },
                            )
                            # Refresh player list (encumbrance update)
                            updated_players = get_players(campaign_id)
                            await manager.broadcast(
                                campaign_id,
                                {
                                    "type": "player_list",
                                    "players": [p.model_dump(mode="json") for p in updated_players],
                                },
                            )
                        else:
                            await manager.send_personal(
                                websocket,
                                {"type": "error", "message": move_result.message},
                            )

            elif msg_type == "complete_milestone":
                quest_id = data.get("quest_id")
                milestone_idx = data.get("milestone_idx")
                if not isinstance(quest_id, int) or not isinstance(milestone_idx, int):
                    await manager.send_personal(
                        websocket,
                        {"type": "error", "message": "complete_milestone requires integer quest_id and milestone_idx"},
                    )
                else:
                    q_campaign = load_campaign_world(campaign_id)
                    if q_campaign:
                        q_tools = WorldTools(q_campaign.world)
                        q_result = q_tools.complete_milestone(quest_id, milestone_idx)
                        if q_result.success:
                            save_campaign_world(campaign_id, q_campaign)
                            await manager.broadcast(
                                campaign_id,
                                {
                                    "type": "quest_updated",
                                    "quest": q_result.data["quest"],
                                },
                            )
                        else:
                            await manager.send_personal(
                                websocket,
                                {"type": "error", "message": q_result.message},
                            )

            elif msg_type == "travel":
                # Travel segment: roll hidden d20 encounter check.
                # If triggered, switch to Combat mode and broadcast encounter details.
                location_type = str(data.get("location_type", "default"))
                meta = get_campaign_meta(campaign_id) or meta
                travel_campaign = load_campaign_world(campaign_id)
                if not travel_campaign:
                    await manager.send_personal(
                        websocket, {"type": "error", "message": "Campaign world not found"}
                    )
                else:
                    travel_tools = WorldTools(travel_campaign.world)
                    # Determine average party level from PC objects
                    pcs = travel_campaign.world.get_pcs()
                    party_level = 1
                    if pcs:
                        levels = []
                        for pc in pcs:
                            classes = pc.properties.get("classes", [])
                            if classes:
                                levels.append(classes[0].get("level", 1))
                        if levels:
                            party_level = max(1, sum(levels) // len(levels))

                    enc_result = travel_tools.trigger_travel_encounter(
                        location_type=location_type,
                        party_level=party_level,
                    )
                    roll_data = enc_result.data or {}

                    # Broadcast the (hidden) roll outcome to all connected clients
                    await manager.broadcast(
                        campaign_id,
                        {
                            "type": "travel_roll",
                            "d20_roll": roll_data.get("d20_roll"),
                            "encounter_dc": roll_data.get("encounter_dc"),
                            "triggered": roll_data.get("triggered", False),
                            "location_type": location_type,
                            "encounter": roll_data.get("encounter"),
                        },
                    )

                    if roll_data.get("triggered") and roll_data.get("encounter"):
                        enc = roll_data["encounter"]
                        enc_msg = ChatMessage(
                            sender="DM",
                            sender_type="DM",
                            text=(
                                f"As the party travels through the {location_type}, "
                                f"danger stirs! {enc['count']}x {enc['enemy_name']} "
                                f"(CR {enc['cr']}) emerge — roll for initiative!"
                            ),
                            turn_number=meta.turn_number,
                        )
                        append_chat(campaign_id, enc_msg)
                        await manager.broadcast(
                            campaign_id,
                            {
                                "type": "chat",
                                "message": enc_msg.model_dump(mode="json"),
                            },
                        )

                        # Switch game mode to Combat
                        meta.game_mode = "Combat"
                        save_campaign_meta(meta)
                        await manager.broadcast(
                            campaign_id,
                            {
                                "type": "encounter_started",
                                "encounter": enc,
                                "location_type": location_type,
                                "game_mode": "Combat",
                            },
                        )

                        # Ask DM agent to narrate and spawn enemies
                        spawn_prompt = (
                            f"Random encounter during travel through {location_type}! "
                            f"Spawn {enc['count']}x {enc['enemy_name']} (CR {enc['cr']}) "
                            f"as NPC objects in the current location, start combat with all "
                            f"party members and the spawned enemies, and narrate the ambush."
                        )
                        await manager.broadcast(
                            campaign_id,
                            {"type": "dm_thinking", "message": "The Dungeon Master prepares an encounter..."},
                        )
                        asyncio.create_task(
                            _run_dm_response(campaign_id, spawn_prompt, session.username, char_name)
                        )
                    else:
                        safe_msg = ChatMessage(
                            sender="DM",
                            sender_type="DM",
                            text=f"The party travels through the {location_type} without incident.",
                            turn_number=meta.turn_number,
                        )
                        append_chat(campaign_id, safe_msg)
                        await manager.broadcast(
                            campaign_id,
                            {
                                "type": "chat",
                                "message": safe_msg.model_dump(mode="json"),
                            },
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
