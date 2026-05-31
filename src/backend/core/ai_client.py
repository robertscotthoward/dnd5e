"""AI client using Ollama via LlamaIndex for agent interactions."""

import asyncio
from typing import Optional
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama import Ollama
from rich.console import Console

from .config import settings
from .tools import WorldTools, CombatTools
from .vector_store import vector_store
from ..models.game import Campaign
from ..models.user import CampaignMeta

console = Console()

_DM_SYSTEM_PROMPT = (
    "You are the Dungeon Master for a D&D 5e campaign. You orchestrate events, enforce "
    "the rules, narrate outcomes, and call tools to mutate the game world. Think step by "
    "step: reason about the situation, decide what game-world changes are needed, call "
    "the appropriate tools, then produce your final narration. Never invent object IDs — "
    "use get_object or get_sub_world to discover them first."
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
        results = vector_store.search(query, n_results=n_results)
        if not results:
            return "No relevant rules found."

        context_parts = []
        for result in results:
            source = result["metadata"].get("source", "Unknown")
            section = result["metadata"].get("section", "")
            text = result["text"][:500]
            context_parts.append(f"[{source}: {section}]\n{text}")

        return "\n\n---\n\n".join(context_parts)

    async def _run_dm_agent(self, user_message: str, tools: list[FunctionTool]) -> str:
        """Run the DM ReAct agent asynchronously and return the narrative text."""
        agent = ReActAgent(
            tools=tools,
            llm=self.llm,
            system_prompt=_DM_SYSTEM_PROMPT,
            verbose=True,
            streaming=False,
            max_iterations=10,
            early_stopping_method="generate",
        )
        handler = agent.run(user_msg=user_message)
        result = await handler
        # result is AgentOutput; result.response is a ChatMessage
        return result.response.content or ""

    async def _run_pc_agent(
        self, user_message: str, system_prompt: str, tools: list[FunctionTool]
    ) -> str:
        """Run a PC ReAct agent asynchronously and return the action text."""
        agent = ReActAgent(
            tools=tools,
            llm=self.llm,
            system_prompt=system_prompt,
            verbose=True,
            streaming=False,
            max_iterations=6,
            early_stopping_method="generate",
        )
        handler = agent.run(user_msg=user_message)
        result = await handler
        return result.response.content or ""

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
            "End with your narration."
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
        """Run the World ReAct agent asynchronously and return the narrator summary."""
        agent = ReActAgent(
            tools=tools,
            llm=self.llm,
            system_prompt=_WORLD_SYSTEM_PROMPT,
            verbose=True,
            streaming=False,
            max_iterations=8,
            early_stopping_method="generate",
        )
        handler = agent.run(user_msg=user_message)
        result = await handler
        return result.response.content or ""

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
