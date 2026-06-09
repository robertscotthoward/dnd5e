"""AI client using Ollama via LlamaIndex for agent interactions."""

import asyncio
import inspect
import json
import re
from typing import Any, Callable, Optional
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama import Ollama
from rich.console import Console

from .config import settings
from .tools import WorldTools, CombatTools
from .vector_store import vector_store
from ..models.game import Campaign
from ..models.user import CampaignMeta

console = Console()

_REACT_TOOL_PROMPT = (
    "\n\nYou have access to the following tools:\n{tool_descriptions}\n\n"
    "Use this exact format for EVERY tool call:\n"
    "Thought: <your reasoning>\n"
    "Action: <tool_name>\n"
    "Action Input: <json object with tool arguments>\n"
    "Observation: <tool result will be inserted here>\n\n"
    "When you have enough information and all necessary tool calls are done, respond with:\n"
    "Thought: I now have all the information I need.\n"
    "Final Answer: <your narrative response to the player — no tool syntax>\n\n"
    "IMPORTANT: The Final Answer must be plain prose only. "
    "Never include Thought/Action/Action Input in the Final Answer.\n"
)

_MAX_REACT_ITERATIONS = 10

_DM_SYSTEM_PROMPT = (
    "You are the Dungeon Master for a D&D 5e campaign. You orchestrate events, enforce "
    "the rules, narrate outcomes, and call tools to mutate the game world. Think step by "
    "step: reason about the situation, decide what game-world changes are needed, call "
    "the appropriate tools, then produce your final narration. Never invent object IDs — "
    "use get_object or get_sub_world to discover them first.\n\n"
    "MOVEMENT RULE (mandatory): Whenever a player or NPC moves from one location to another "
    "— entering a room, leaving a building, stepping outside — you MUST call move_object to "
    "update their parent to the destination object BEFORE writing the Final Answer. "
    "Never narrate movement without calling move_object first. If you do not know the "
    "destination object's ID, call get_sub_world or get_object to find it first."
)

_PC_SYSTEM_PROMPT_TEMPLATE = (
    "You are playing {name}, a {race} {class_str} in a D&D 5e campaign.\n\n"
    "PERSONALITY: {personality}\n"
    "GOALS: {goals}\n\n"
    "Act in character at all times. Use your personality and goals to guide every decision. "
    "You may call tools to inspect the world (get_object, get_sub_world) and to move yourself "
    "or pick up items (move_object). You cannot deal damage directly — only the DM resolves "
    "combat outcomes. Think step by step: assess the situation, check relevant world details "
    "with tools if needed, then declare your action in first person as {name}. "
    "Never invent object IDs — use get_object or get_sub_world to discover them first."
)

_NPC_SYSTEM_PROMPT_TEMPLATE = (
    "You are {name}, a {creature_type} in a D&D 5e campaign.\n\n"
    "ROLE: {role}\n"
    "BEHAVIOR: {behavior}\n\n"
    "You act under the direction of the Dungeon Master. Execute DM directives faithfully "
    "and in character. You may call tools to inspect the world (get_object, get_sub_world), "
    "move yourself (move_object), update your own state (set_object_property), and apply "
    "damage or healing (add_hp) when instructed to attack or heal. Think step by step: "
    "assess the directive, check relevant world details with tools if needed, then carry out "
    "the action and describe what {name} does in third person. "
    "Never invent object IDs — use get_object or get_sub_world to discover them first."
)

_WORLD_SYSTEM_PROMPT = (
    "You are the World Agent for a D&D 5e campaign. You run autonomously before the "
    "Dungeon Master each turn to advance the living world: shift weather conditions, "
    "move NPCs along their daily routines, trigger opportunistic theft or item movement, "
    "and introduce minor environmental events. Keep changes subtle and believable — the "
    "world must feel alive without overshadowing the players' story.\n\n"
    "Guidelines:\n"
    "- Use set_object_property to update weather or environmental state on region objects.\n"
    "- Use move_object to relocate wandering NPCs or stolen items.\n"
    "- Use create_object sparingly — only for ephemeral world objects like weather effects.\n"
    "- Use get_sub_world or get_object to discover valid IDs before acting on them.\n"
    "- Never kill a PC or damage a PC directly — that is the DM's job.\n"
    "- After making world changes, produce a brief narrator summary of what shifted.\n"
    "Never invent object IDs — always discover them with tools first."
)


class AIClient:
    """AI client for interacting with Ollama LLM."""

    def __init__(self):
        self._llm: Optional[Ollama] = None

    @property
    def llm(self) -> Ollama:
        """Lazy-load the Ollama LLM."""
        if self._llm is None:
            self._llm = Ollama(
                model=settings.ollama.model,
                base_url=settings.ollama.base_url,
                temperature=settings.ollama.temperature,
                request_timeout=settings.ollama.request_timeout,
            )
        return self._llm

    def test_connection(self) -> bool:
        """Test the connection to Ollama."""
        try:
            response = self.llm.complete("Say 'hello' in one word.")
            return bool(response.text)
        except Exception as e:
            console.print(f"[red]Failed to connect to Ollama: {e}[/red]")
            return False

    def create_tools(self, world_tools: WorldTools) -> list[FunctionTool]:
        """Create LlamaIndex function tools from WorldTools."""
        return [
            FunctionTool.from_defaults(
                fn=world_tools.create_object,
                name="create_object",
                description="Create a new object in the world",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.move_object,
                name="move_object",
                description="Move an object to a new parent location",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.set_object_property,
                name="set_object_property",
                description="Set a property on an object",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.add_hp,
                name="add_hp",
                description="Modify a player's HP (negative for damage, positive for healing)",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.delete_object,
                name="delete_object",
                description="Delete an object from the world",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.get_object,
                name="get_object",
                description="Get an object by ID",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.get_sub_world,
                name="get_sub_world",
                description="Get the visible world from an observer's perspective",
            ),
        ]

    def create_pc_tools(self, world_tools: WorldTools) -> list[FunctionTool]:
        """Create a restricted tool set for PC agents (read + movement, no destructive ops)."""
        return [
            FunctionTool.from_defaults(
                fn=world_tools.get_object,
                name="get_object",
                description="Get an object by ID to inspect its properties",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.get_sub_world,
                name="get_sub_world",
                description="Get the visible world from an observer's perspective",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.move_object,
                name="move_object",
                description="Move yourself or a held item to a new location",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.set_object_property,
                name="set_object_property",
                description="Update a property on yourself (e.g. equipped item, stance)",
            ),
        ]

    def create_world_tools(self, world_tools: WorldTools) -> list[FunctionTool]:
        """Create the World Agent tool set: read, movement, state update, and create."""
        return [
            FunctionTool.from_defaults(
                fn=world_tools.get_object,
                name="get_object",
                description="Get an object by ID to inspect its properties",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.get_sub_world,
                name="get_sub_world",
                description="Get the visible world from an observer's perspective",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.move_object,
                name="move_object",
                description="Move an NPC or item to a new location in the world",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.set_object_property,
                name="set_object_property",
                description="Update a property on a world object (e.g. weather, NPC state)",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.create_object,
                name="create_object",
                description="Create a new ephemeral world object (e.g. weather effect, dropped item)",
            ),
        ]

    def create_combat_tools(
        self, world_tools: WorldTools, combat_tools: CombatTools
    ) -> list[FunctionTool]:
        """Create the full DM tool set including combat mechanics."""
        base_tools = self.create_tools(world_tools)
        return base_tools + [
            FunctionTool.from_defaults(
                fn=combat_tools.start_combat,
                name="start_combat",
                description="Begin combat by rolling d20+DEX initiative for all combatants",
            ),
            FunctionTool.from_defaults(
                fn=combat_tools.next_turn,
                name="next_turn",
                description="Advance combat to the next combatant in initiative order",
            ),
            FunctionTool.from_defaults(
                fn=combat_tools.end_combat,
                name="end_combat",
                description="End combat and return to Exploration mode",
            ),
            FunctionTool.from_defaults(
                fn=combat_tools.roll_attack,
                name="roll_attack",
                description="Roll d20+bonus vs target AC; returns hit/miss and critical status",
            ),
            FunctionTool.from_defaults(
                fn=combat_tools.roll_saving_throw,
                name="roll_saving_throw",
                description="Roll a saving throw (d20+ability modifier) vs a difficulty class",
            ),
            FunctionTool.from_defaults(
                fn=combat_tools.roll_damage,
                name="roll_damage",
                description="Roll damage dice (e.g. '1d8+3') for a successful attack",
            ),
        ]

    def create_npc_tools(self, world_tools: WorldTools) -> list[FunctionTool]:
        """Create the NPC tool set: read, movement, state update, and combat damage."""
        return [
            FunctionTool.from_defaults(
                fn=world_tools.get_object,
                name="get_object",
                description="Get an object by ID to inspect its properties",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.get_sub_world,
                name="get_sub_world",
                description="Get the visible world from an observer's perspective",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.move_object,
                name="move_object",
                description="Move yourself or a carried item to a new location",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.set_object_property,
                name="set_object_property",
                description="Update a property on yourself (e.g. stance, condition)",
            ),
            FunctionTool.from_defaults(
                fn=world_tools.add_hp,
                name="add_hp",
                description="Apply damage (negative) or healing (positive) to a target by DM directive",
            ),
        ]

    def query_rules(self, query: str, n_results: int = 3) -> str:
        """Query the D&D rules corpus and return relevant context."""
        try:
            results = vector_store.search(query, n_results=n_results)
        except Exception:
            return ""
        if not results:
            return ""

        context_parts = []
        for result in results:
            source = result["metadata"].get("source", "Unknown")
            section = result["metadata"].get("section", "")
            text = result["text"][:500]
            context_parts.append(f"[{source}: {section}]\n{text}")

        return "\n\n---\n\n".join(context_parts)

    def _build_tool_map(self, tools: list[FunctionTool]) -> dict[str, Callable]:
        """Return name→callable for every tool in the list."""
        return {t.metadata.name: t.fn for t in tools}

    def _build_tool_descriptions(self, tools: list[FunctionTool]) -> str:
        lines = []
        for t in tools:
            sig = inspect.signature(t.fn)
            params = ", ".join(
                f"{n}: {p.annotation.__name__ if p.annotation != inspect.Parameter.empty else 'any'}"
                for n, p in sig.parameters.items()
                if n != "self"
            )
            lines.append(f"- {t.metadata.name}({params}): {t.metadata.description}")
        return "\n".join(lines)

    def _parse_action(self, text: str) -> tuple[str, dict] | None:
        """Extract (action_name, args_dict) from ReAct output, or None."""
        action_match = re.search(r"Action\s*:\s*(\w+)", text)
        input_match = re.search(r"Action\s+Input\s*:\s*(\{.*?\})", text, re.DOTALL)
        if not action_match:
            return None
        action_name = action_match.group(1).strip()
        args: dict[str, Any] = {}
        if input_match:
            try:
                args = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                pass
        return action_name, args

    def _extract_final_answer(self, text: str) -> str | None:
        """Return the Final Answer prose if present, else None."""
        match = re.search(r"Final\s+Answer\s*:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _clean_narration(self, text: str) -> str:
        """Strip any ReAct boilerplate that leaked into the final text."""
        lines = []
        skip_prefixes = ("thought:", "action:", "action input:", "observation:", "final answer:")
        for line in text.splitlines():
            if line.strip().lower().startswith(skip_prefixes):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    async def _run_react_loop(
        self,
        system_prompt: str,
        user_message: str,
        tools: list[FunctionTool],
        max_iterations: int = _MAX_REACT_ITERATIONS,
    ) -> str:
        """
        Manual ReAct loop:
        1. Prompt the LLM with accumulated history.
        2. Parse Action/Action Input from response.
        3. Execute the tool and append Observation.
        4. Repeat until Final Answer or max_iterations.
        Returns only the final narrative text.
        """
        tool_map = self._build_tool_map(tools)
        tool_descriptions = self._build_tool_descriptions(tools)

        tool_section = _REACT_TOOL_PROMPT.format(tool_descriptions=tool_descriptions)
        full_system = system_prompt + tool_section

        history = f"User: {user_message}\n"
        last_narration = ""

        loop = asyncio.get_running_loop()

        for _ in range(max_iterations):
            prompt = full_system + "\n\n" + history + "Assistant:"
            response_obj = await loop.run_in_executor(
                None, lambda p=prompt: self.llm.complete(p)
            )
            response_text = response_obj.text.strip()

            # Check for final answer first
            final = self._extract_final_answer(response_text)
            if final:
                return self._clean_narration(final)

            # Try to parse and execute a tool call
            parsed = self._parse_action(response_text)
            if parsed:
                action_name, args = parsed
                fn = tool_map.get(action_name)
                if fn:
                    try:
                        result = fn(**args)
                        observation = str(result)
                    except Exception as exc:
                        observation = f"Error calling {action_name}: {exc}"
                else:
                    observation = f"Unknown tool: {action_name}"

                # Append this exchange to history
                history += f"Assistant: {response_text}\nObservation: {observation}\n"
                last_narration = self._clean_narration(response_text)
                continue

            # No action and no Final Answer — treat the whole response as the answer
            cleaned = self._clean_narration(response_text)
            if cleaned:
                return cleaned
            break

        return last_narration or "[The DM considers the situation...]"

    async def _run_dm_agent(self, user_message: str, tools: list[FunctionTool]) -> str:
        """Run the DM ReAct loop and return only the final narrative."""
        return await self._run_react_loop(_DM_SYSTEM_PROMPT, user_message, tools, max_iterations=10)

    async def _run_pc_agent(
        self, user_message: str, system_prompt: str, tools: list[FunctionTool]
    ) -> str:
        """Run a PC ReAct loop and return only the action declaration."""
        return await self._run_react_loop(system_prompt, user_message, tools, max_iterations=6)

    def generate_dm_response(
        self,
        campaign: Campaign,
        situation: str,
        world_tools: WorldTools,
        meta: Optional[CampaignMeta] = None,
    ) -> str:
        """
        Run a full ReAct tool-calling loop as the DM agent.

        When meta is provided and game_mode is 'Combat', the full combat tool set
        (initiative, attack, saving throws) is included in the agent's tool list.
        """
        rules_context = self.query_rules(situation)

        pcs = campaign.world.get_pcs()

        if pcs:
            visible_world = campaign.world.get_visible_world(pcs[0].id)
            world_context = str(visible_world.model_dump_yaml())
        else:
            world_context = "No players found"

        pc_summaries = []
        for pc in pcs:
            hp = pc.properties.get("hp", {})
            classes = pc.properties.get("classes", [])
            class_str = "/".join(c.get("type", "?") for c in classes) if classes else "Unknown"
            race = pc.properties.get("race", "Unknown")
            pc_summaries.append(
                f"- {pc.name} ({race} {class_str}): HP {hp.get('current', '?')}/{hp.get('max', '?')}"
            )

        in_combat = meta is not None and meta.game_mode == "Combat"

        if in_combat and meta:
            active_obj = campaign.world.get_object(meta.active_player_turn) if meta.active_player_turn else None
            active_name = active_obj.name if active_obj else "unknown"
            queue_names = []
            for oid in meta.combat_queue:
                o = campaign.world.get_object(oid)
                queue_names.append(o.name if o else str(oid))
            combat_context = (
                f"\nCOMBAT STATUS:\n"
                f"- Mode: Combat\n"
                f"- Active turn: {active_name} (ID {meta.active_player_turn})\n"
                f"- Initiative queue: {', '.join(queue_names)}\n"
            )
            combat_instruction = (
                "You are running a combat encounter. Use roll_attack, roll_damage, "
                "roll_saving_throw, and add_hp to resolve combat actions. Call next_turn "
                "after each combatant's action is resolved. Call end_combat when all enemies "
                "are defeated or the encounter otherwise ends.\n"
            )
        else:
            combat_context = ""
            combat_instruction = ""

        user_message = (
            f'Campaign: "{campaign.name}"\n\n'
            f"CURRENT SITUATION:\n{situation}\n\n"
            f"VISIBLE WORLD STATE:\n{world_context}\n\n"
            f"RELEVANT D&D RULES:\n{rules_context}\n\n"
            f"PLAYERS:\n{chr(10).join(pc_summaries) if pc_summaries else 'No players'}\n"
            f"{combat_context}\n"
            f"{combat_instruction}"
            "As the DM, narrate what happens next. Call world tools as needed to update "
            "game state (e.g. apply damage with add_hp, move objects with move_object). "
            "IMPORTANT: If the player or any character changes location, you MUST call "
            "move_object(id, new_parent_id) to update their position in the world BEFORE "
            "writing the Final Answer. Use get_sub_world or get_object first if you need "
            "to discover the destination's object ID."
        )

        if in_combat and meta:
            combat_tools = CombatTools(campaign.world, meta)
            tools = self.create_combat_tools(world_tools, combat_tools)
        else:
            tools = self.create_tools(world_tools)

        try:
            return asyncio.run(self._run_dm_agent(user_message, tools))
        except Exception as e:
            console.print(f"[red]Error in DM ReAct agent: {e}[/red]")
            return f"[DM is thinking...] (Error: {e})"

    def generate_player_action(
        self,
        campaign: Campaign,
        player_id: int,
        situation: str,
        world_tools: Optional[WorldTools] = None,
    ) -> str:
        """
        Run a ReAct agent as the PC to decide and declare an action.

        The agent receives the character's personality and visible world, may call
        read/movement tools, and produces a first-person action declaration.

        Args:
            campaign: The current campaign
            player_id: Object ID of the player
            situation: Current situation description
            world_tools: WorldTools instance; created from campaign.world if omitted
        """
        pc = campaign.world.get_object(player_id)
        if not pc:
            return "Player not found"

        if world_tools is None:
            world_tools = WorldTools(campaign.world)

        hp = pc.properties.get("hp", {})
        abilities = pc.properties.get("abilities", {})
        classes = pc.properties.get("classes", [])
        class_str = "/".join(c.get("type", "?") for c in classes) if classes else "Unknown"
        race = pc.properties.get("race", "Unknown")
        personality = pc.properties.get("personality", "Not defined")
        goals = pc.properties.get("goals", [])
        goals_str = ", ".join(goals) if goals else "None specified"

        system_prompt = _PC_SYSTEM_PROMPT_TEMPLATE.format(
            name=pc.name or "the character",
            race=race,
            class_str=class_str,
            personality=personality,
            goals=goals_str,
        )

        visible_world = campaign.world.get_visible_world(player_id)

        user_message = (
            f"Campaign: \"{campaign.name}\"\n\n"
            f"CHARACTER DETAILS:\n"
            f"- HP: {hp.get('current', '?')}/{hp.get('max', '?')}\n"
            f"- Abilities: STR {abilities.get('str', 10)}, DEX {abilities.get('dex', 10)}, "
            f"CON {abilities.get('con', 10)}, INT {abilities.get('int', 10)}, "
            f"WIS {abilities.get('wis', 10)}, CHR {abilities.get('chr', 10)}\n\n"
            f"CURRENT SITUATION:\n{situation}\n\n"
            f"WHAT YOU CAN SEE:\n{visible_world.model_dump_yaml()}\n\n"
            f"What does {pc.name or 'you'} do? Respond in first person as the character."
        )

        tools = self.create_pc_tools(world_tools)

        try:
            return asyncio.run(self._run_pc_agent(user_message, system_prompt, tools))
        except Exception as e:
            console.print(f"[red]Error in PC ReAct agent: {e}[/red]")
            return f"[{pc.name or 'character'} hesitates...] (Error: {e})"

    def generate_npc_action(
        self,
        campaign: Campaign,
        npc_id: int,
        dm_directive: str,
        world_tools: Optional[WorldTools] = None,
    ) -> str:
        """
        Run a ReAct agent as an NPC to execute a DM directive.

        The NPC agent receives the DM's instruction, may call world tools to inspect
        or mutate state, and produces a third-person action description.

        Args:
            campaign: The current campaign
            npc_id: Object ID of the NPC (monster or townfolk)
            dm_directive: The DM's instruction for what the NPC should do
            world_tools: WorldTools instance; created from campaign.world if omitted
        """
        npc = campaign.world.get_object(npc_id)
        if not npc:
            return "NPC not found"

        if world_tools is None:
            world_tools = WorldTools(campaign.world)

        hp = npc.properties.get("hp", {})
        abilities = npc.properties.get("abilities", {})
        creature_type = npc.properties.get("creature_type", npc.type)
        role = npc.properties.get("role", npc.description or "a creature in the world")
        behavior = npc.properties.get("behavior", "Acts according to its nature")

        system_prompt = _NPC_SYSTEM_PROMPT_TEMPLATE.format(
            name=npc.name or "the creature",
            creature_type=creature_type,
            role=role,
            behavior=behavior,
        )

        visible_world = campaign.world.get_visible_world(npc_id)

        user_message = (
            f'Campaign: "{campaign.name}"\n\n'
            f"NPC DETAILS:\n"
            f"- Name: {npc.name or 'Unknown'}\n"
            f"- Type: {creature_type}\n"
            f"- HP: {hp.get('current', '?')}/{hp.get('max', '?')}\n"
            f"- Abilities: STR {abilities.get('str', 10)}, DEX {abilities.get('dex', 10)}, "
            f"CON {abilities.get('con', 10)}, INT {abilities.get('int', 10)}, "
            f"WIS {abilities.get('wis', 10)}, CHR {abilities.get('chr', 10)}\n\n"
            f"DM DIRECTIVE:\n{dm_directive}\n\n"
            f"WHAT YOU CAN SEE:\n{visible_world.model_dump_yaml()}\n\n"
            f"Carry out the directive as {npc.name or 'the NPC'}. "
            "Describe your actions in third person."
        )

        tools = self.create_npc_tools(world_tools)

        try:
            return asyncio.run(self._run_pc_agent(user_message, system_prompt, tools))
        except Exception as e:
            console.print(f"[red]Error in NPC ReAct agent: {e}[/red]")
            return f"[{npc.name or 'NPC'} hesitates...] (Error: {e})"

    async def _run_world_agent(self, user_message: str, tools: list[FunctionTool]) -> str:
        """Run the World ReAct loop and return only the narrator summary."""
        return await self._run_react_loop(_WORLD_SYSTEM_PROMPT, user_message, tools, max_iterations=8)

    def generate_journal_entry(
        self,
        campaign_name: str,
        turn_number: int,
        narration: str,
        player_names: list[str],
    ) -> str:
        """
        Generate a one-paragraph journal entry summarising the turn's events.

        Called after each DM response so the journal accumulates a narrative log.
        Falls back to the raw narration on LLM error.
        """
        names_str = ", ".join(player_names) if player_names else "the party"
        prompt = (
            f"You are chronicling a D&D 5e campaign called \"{campaign_name}\".\n\n"
            f"TURN {turn_number} EVENTS:\n{narration}\n\n"
            f"PARTY MEMBERS: {names_str}\n\n"
            "Write a single evocative paragraph (3-5 sentences) summarising what happened "
            "this turn as a campaign journal entry. Write in past tense, third person. "
            "Be specific about events, characters, and locations. Do not add headers or "
            "bullet points — only a flowing prose paragraph."
        )
        try:
            return self.llm.complete(prompt).text.strip()
        except Exception as e:
            console.print(f"[red]Error generating journal entry: {e}[/red]")
            return narration[:500] if narration else f"Turn {turn_number} passed uneventfully."

    def generate_dm_recap(
        self,
        character_name: str,
        race: str,
        class_str: str,
        location_name: str,
        turn_number: int,
        recent_messages: list[dict],
        hp_current: int = 0,
        hp_max: int = 0,
        conditions: list[str] | None = None,
        visible_objects: list[str] | None = None,
        nearby_party: list[str] | None = None,
        is_new_character: bool = False,
    ) -> str:
        """
        Generate a DM situational summary when a player joins or rejoins.

        For a new character: describes the opening scene, where they are, and who
        they can see. For a returning player: recaps recent events and restates
        current status. Falls back to a plain string on LLM error.
        """
        hp_line = f"{hp_current}/{hp_max} HP" if hp_max else "unknown HP"
        cond_line = ", ".join(conditions) if conditions else "none"
        objects_block = "\n".join(f"- {o}" for o in visible_objects) if visible_objects else "(nothing notable nearby)"
        party_block = ", ".join(nearby_party) if nearby_party else "none present"

        if is_new_character:
            prompt = (
                f"You are the Dungeon Master opening the first scene for a brand-new player character.\n\n"
                f"CHARACTER: {character_name}, a {race} {class_str}\n"
                f"STARTING LOCATION: {location_name}\n"
                f"STATUS: {hp_line} | Conditions: {cond_line}\n"
                f"NEARBY PARTY MEMBERS: {party_block}\n"
                f"VISIBLE SURROUNDINGS:\n{objects_block}\n\n"
                f"Write 2-3 sentences in second person describing what {character_name} sees and senses "
                f"as they arrive in {location_name}. Name specific visible objects or people. "
                f"End with a question or observation that invites the player to act."
            )
            fallback = (
                f"You are {character_name}, a {race} {class_str}. "
                f"You find yourself in {location_name}. "
                f"{'Your companions ' + party_block + ' are nearby. ' if nearby_party else ''}"
                f"What do you do?"
            )
        else:
            if recent_messages:
                history_lines = [
                    f"{m.get('sender', '?')}: {m.get('text', '')}"
                    for m in recent_messages[-20:]
                ]
                history_block = "\n".join(history_lines)
            else:
                history_block = "(No prior chat history available.)"

            prompt = (
                f"You are the Dungeon Master recapping the last session for a returning player.\n\n"
                f"CHARACTER: {character_name}, a {race} {class_str}\n"
                f"CURRENT LOCATION: {location_name}\n"
                f"CAMPAIGN TURN: {turn_number}\n"
                f"CURRENT STATUS: {hp_line} | Conditions: {cond_line}\n"
                f"NEARBY PARTY MEMBERS: {party_block}\n"
                f"VISIBLE SURROUNDINGS:\n{objects_block}\n\n"
                f"RECENT SESSION LOG:\n{history_block}\n\n"
                f"Write 3-4 sentences in second person. First, recap what {character_name} last experienced "
                f"(reference specific log events if available). Then describe what they currently see around them "
                f"and their present condition. End with a hook that draws them back into the action."
            )
            fallback = (
                f"Welcome back, {character_name}! "
                f"You find yourself in {location_name} on turn {turn_number} ({hp_line}). "
                f"{'Nearby: ' + party_block + '.' if nearby_party else ''}"
            )

        try:
            return self.llm.complete(prompt).text.strip()
        except Exception as e:
            console.print(f"[red]Error generating DM recap: {e}[/red]")
            return fallback

    def generate_world_update(
        self,
        campaign: Campaign,
        world_tools: Optional[WorldTools] = None,
        time_passed: str = "a few moments",
    ) -> str:
        """
        Run a full ReAct tool-calling loop as the World Agent.

        The agent runs before the DM each turn, autonomously advancing weather,
        NPC movement, item theft, and minor environmental events.

        Args:
            campaign: The current campaign
            world_tools: WorldTools instance; created from campaign.world if omitted
            time_passed: Narrative description of elapsed time
        """
        if world_tools is None:
            world_tools = WorldTools(campaign.world)

        # Build a root-level world snapshot for context
        root_objects = list(campaign.world.objects.values())
        object_summary_lines = []
        for obj in root_objects[:30]:  # cap to avoid token overflow
            object_summary_lines.append(
                f"  [{obj.id}] {obj.type} '{obj.name or 'unnamed'}' (parent={obj.parent})"
            )
        object_summary = "\n".join(object_summary_lines)

        user_message = (
            f'Campaign: "{campaign.name}" | Turn: {campaign.turn_number}\n\n'
            f"TIME PASSED: {time_passed}\n\n"
            f"WORLD OBJECTS (first 30):\n{object_summary}\n\n"
            "Advance the living world. Consider:\n"
            "- Shift weather or light conditions on region/area objects.\n"
            "- Move wandering NPCs to new locations.\n"
            "- Trigger opportunistic theft: move a small item from an unattended location.\n"
            "- Introduce a minor environmental event (sound, smell, distant activity).\n\n"
            "Use tools to inspect objects before acting on them. After making your changes, "
            "provide a brief narrator summary (1–3 sentences) of what shifted in the world."
        )

        tools = self.create_world_tools(world_tools)

        try:
            return asyncio.run(self._run_world_agent(user_message, tools))
        except Exception as e:
            console.print(f"[red]Error in World ReAct agent: {e}[/red]")
            return f"[World Agent silent] (Error: {e})"


# Global AI client instance
ai_client = AIClient()
