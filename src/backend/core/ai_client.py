"""AI client using Ollama via LlamaIndex for agent interactions."""

import asyncio
from typing import Optional
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama import Ollama
from rich.console import Console

from .config import settings
from .tools import WorldTools
from .vector_store import vector_store
from ..models.game import Campaign

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
    ) -> str:
        """
        Run a full ReAct tool-calling loop as the DM agent.

        The agent receives the filtered world, may call world tools to mutate state,
        and produces a final narrative string.
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

        user_message = (
            f'Campaign: "{campaign.name}"\n\n'
            f"CURRENT SITUATION:\n{situation}\n\n"
            f"VISIBLE WORLD STATE:\n{world_context}\n\n"
            f"RELEVANT D&D RULES:\n{rules_context}\n\n"
            f"PLAYERS:\n{chr(10).join(pc_summaries) if pc_summaries else 'No players'}\n\n"
            "As the DM, narrate what happens next. Call world tools as needed to update "
            "game state (e.g. apply damage with add_hp, move objects with move_object). "
            "End with your narration."
        )

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

    def generate_world_update(
        self,
        campaign: Campaign,
        time_passed: str = "a few moments",
    ) -> str:
        """
        Generate world updates (weather, NPC actions, events).

        Args:
            campaign: The current campaign
            time_passed: Description of time that has passed
        """
        prompt = f"""You are the World agent for a D&D 5e campaign. {time_passed} have passed.

Consider what might change in the world:
- Weather conditions
- NPC movements and actions
- Environmental changes
- Random events

Current turn: {campaign.turn_number}
World: {campaign.world.name}

Describe any world changes that should occur. Keep it brief and relevant to the story."""

        try:
            response = self.llm.complete(prompt)
            return response.text
        except Exception as e:
            console.print(f"[red]Error generating world update: {e}[/red]")
            return ""


# Global AI client instance
ai_client = AIClient()
