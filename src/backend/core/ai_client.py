"""AI client using Ollama via LlamaIndex for agent interactions."""

from typing import Optional
from llama_index.core.tools import FunctionTool
from llama_index.llms.ollama import Ollama
from rich.console import Console

from .config import settings
from .tools import WorldTools
from .vector_store import vector_store
from ..models.game import Campaign

console = Console()


class AIClient:
    """
    AI client for interacting with Ollama LLM.

    Provides tool-calling capabilities for game agents.
    """

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
        tools = []

        tools.append(FunctionTool.from_defaults(
            fn=world_tools.create_object,
            name="create_object",
            description="Create a new object in the world",
        ))

        tools.append(FunctionTool.from_defaults(
            fn=world_tools.move_object,
            name="move_object",
            description="Move an object to a new parent location",
        ))

        tools.append(FunctionTool.from_defaults(
            fn=world_tools.set_object_property,
            name="set_object_property",
            description="Set a property on an object",
        ))

        tools.append(FunctionTool.from_defaults(
            fn=world_tools.add_hp,
            name="add_hp",
            description="Modify a player's HP (negative for damage, positive for healing)",
        ))

        tools.append(FunctionTool.from_defaults(
            fn=world_tools.delete_object,
            name="delete_object",
            description="Delete an object from the world",
        ))

        tools.append(FunctionTool.from_defaults(
            fn=world_tools.get_object,
            name="get_object",
            description="Get an object by ID",
        ))

        tools.append(FunctionTool.from_defaults(
            fn=world_tools.get_sub_world,
            name="get_sub_world",
            description="Get the visible world from an observer's perspective",
        ))

        return tools

    def query_rules(self, query: str, n_results: int = 3) -> str:
        """
        Query the D&D rules corpus and return relevant context.

        Args:
            query: The rules question
            n_results: Number of relevant chunks to retrieve
        """
        results = vector_store.search(query, n_results=n_results)
        if not results:
            return "No relevant rules found."

        context_parts = []
        for result in results:
            source = result["metadata"].get("source", "Unknown")
            section = result["metadata"].get("section", "")
            text = result["text"][:500]  # Truncate for context window
            context_parts.append(f"[{source}: {section}]\n{text}")

        return "\n\n---\n\n".join(context_parts)

    def generate_dm_response(
        self,
        campaign: Campaign,
        situation: str,
        world_tools: WorldTools,
    ) -> str:
        """
        Generate a DM response for the current situation.

        The DM narrates events, determines outcomes, and calls tools to modify the world.
        """
        # Get rules context
        rules_context = self.query_rules(situation)

        # Get PCs from world
        pcs = campaign.world.get_pcs()

        # Get visible world for context
        if pcs:
            visible_world = campaign.world.get_visible_world(pcs[0].id)
            world_context = str(visible_world.model_dump_yaml())
        else:
            world_context = "No players found"

        # Build PC summary
        pc_summaries = []
        for pc in pcs:
            hp = pc.properties.get("hp", {})
            classes = pc.properties.get("classes", [])
            class_str = "/".join(c.get("type", "?") for c in classes) if classes else "Unknown"
            race = pc.properties.get("race", "Unknown")
            pc_summaries.append(
                f"- {pc.name} ({race} {class_str}): HP {hp.get('current', '?')}/{hp.get('max', '?')}"
            )

        # Build prompt
        prompt = f"""You are the Dungeon Master for a D&D 5e campaign called "{campaign.name}".

CURRENT SITUATION:
{situation}

VISIBLE WORLD STATE:
{world_context}

RELEVANT D&D RULES:
{rules_context}

PLAYERS:
{chr(10).join(pc_summaries) if pc_summaries else "No players"}

As the DM, narrate what happens next. If any game mechanics are involved (combat, skill checks, etc.),
describe the dice rolls and their outcomes. Use the tools available to modify the game state.

Respond with your narration."""

        # Generate response
        try:
            response = self.llm.complete(prompt)
            return response.text
        except Exception as e:
            console.print(f"[red]Error generating DM response: {e}[/red]")
            return f"[DM is thinking...] (Error: {e})"

    def generate_player_action(
        self,
        campaign: Campaign,
        player_id: int,
        situation: str,
    ) -> str:
        """
        Generate a player character's action based on their personality.

        Args:
            campaign: The current campaign
            player_id: Object ID of the player
            situation: Current situation description
        """
        pc = campaign.world.get_object(player_id)
        if not pc:
            return "Player not found"

        # Get visible world
        visible_world = campaign.world.get_visible_world(player_id)

        # Extract PC properties
        hp = pc.properties.get("hp", {})
        abilities = pc.properties.get("abilities", {})
        classes = pc.properties.get("classes", [])
        class_str = "/".join(c.get("type", "?") for c in classes) if classes else "Unknown"
        race = pc.properties.get("race", "Unknown")
        personality = pc.properties.get("personality", "Not defined")
        goals = pc.properties.get("goals", [])

        prompt = f"""You are playing {pc.name}, a {race} {class_str}.

CHARACTER DETAILS:
- HP: {hp.get('current', '?')}/{hp.get('max', '?')}
- Abilities: STR {abilities.get('str', 10)}, INT {abilities.get('int', 10)}, WIS {abilities.get('wis', 10)}, DEX {abilities.get('dex', 10)}, CON {abilities.get('con', 10)}, CHR {abilities.get('chr', 10)}
- Personality: {personality}
- Goals: {', '.join(goals) if goals else 'None specified'}

CURRENT SITUATION:
{situation}

WHAT YOU CAN SEE:
{visible_world.model_dump_yaml()}

What does {pc.name} do? Respond in first person as the character, describing your action."""

        try:
            response = self.llm.complete(prompt)
            return response.text
        except Exception as e:
            console.print(f"[red]Error generating player action: {e}[/red]")
            return f"[{pc.name} hesitates...] (Error: {e})"

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
