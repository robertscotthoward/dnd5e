"""Combat engine: initiative rolling, turn order, attack/damage resolution, saving throws."""

import random
import re
from typing import Optional

from ..models.user import CampaignMeta
from ..models.world import World


def _ability_modifier(score: int) -> int:
    return (score - 10) // 2


def roll_dice(notation: str, rng: Optional[random.Random] = None) -> dict:
    """Parse and roll a dice notation string like '2d6+3', 'd20', or '4d6-2'."""
    if rng is None:
        rng = random.Random()

    notation = notation.strip().lower()
    match = re.match(r"^(\d*)d(\d+)([+-]\d+)?$", notation)
    if not match:
        raise ValueError(f"Invalid dice notation: '{notation}'")

    count_str, sides_str, modifier_str = match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    modifier = int(modifier_str) if modifier_str else 0

    if count < 1 or sides < 2:
        raise ValueError(f"Invalid dice notation: count={count} sides={sides}")

    rolls = [rng.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier

    return {
        "notation": notation,
        "rolls": rolls,
        "modifier": modifier,
        "total": total,
        "critical_hit": (sides == 20 and count == 1 and rolls[0] == 20),
        "critical_miss": (sides == 20 and count == 1 and rolls[0] == 1),
    }


class CombatEngine:
    """
    Manages D&D 5e combat state: initiative order, turn advancement,
    attack rolls, and saving throws.

    Mutates CampaignMeta in place — callers must persist meta after use.
    """

    def __init__(self, world: World, meta: CampaignMeta, seed: Optional[int] = None):
        self.world = world
        self.meta = meta
        self.rng = random.Random(seed)

    def start_combat(self, combatant_ids: list[int]) -> dict:
        """
        Roll d20+DEX initiative for each combatant and establish turn order.

        Sets meta.game_mode = 'Combat', meta.combat_queue, and meta.active_player_turn.
        Returns the ordered initiative list.
        """
        initiatives = []
        for obj_id in combatant_ids:
            obj = self.world.get_object(obj_id)
            if not obj:
                continue
            dex = obj.properties.get("abilities", {}).get("dex", 10)
            dex_mod = _ability_modifier(dex)
            roll_result = roll_dice("d20", self.rng)
            initiative = roll_result["rolls"][0] + dex_mod
            initiatives.append(
                {
                    "id": obj_id,
                    "name": obj.name or f"combatant_{obj_id}",
                    "initiative": initiative,
                    "d20_roll": roll_result["rolls"][0],
                    "dex_mod": dex_mod,
                }
            )

        initiatives.sort(key=lambda x: x["initiative"], reverse=True)

        self.meta.game_mode = "Combat"
        self.meta.combat_queue = [e["id"] for e in initiatives]
        self.meta.active_player_turn = self.meta.combat_queue[0] if self.meta.combat_queue else None

        return {
            "initiative_order": initiatives,
            "active_turn": self.meta.active_player_turn,
            "queue": self.meta.combat_queue,
        }

    def next_turn(self) -> dict:
        """
        Advance to the next combatant's turn by rotating the queue.

        Updates meta.active_player_turn.
        """
        if not self.meta.combat_queue:
            return {"error": "No active combat queue", "active_turn": None}

        # Rotate: move current head to back
        current = self.meta.combat_queue[0]
        self.meta.combat_queue = self.meta.combat_queue[1:] + [current]
        self.meta.active_player_turn = self.meta.combat_queue[0]

        obj = self.world.get_object(self.meta.active_player_turn)
        name = obj.name if obj else f"combatant_{self.meta.active_player_turn}"

        return {
            "active_turn": self.meta.active_player_turn,
            "active_name": name,
            "queue": list(self.meta.combat_queue),
        }

    def end_combat(self) -> dict:
        """End combat and return to Exploration mode."""
        self.meta.game_mode = "Exploration"
        self.meta.combat_queue = []
        self.meta.active_player_turn = None
        return {"mode": "Exploration", "message": "Combat has ended."}

    def roll_attack(
        self,
        attacker_id: int,
        target_id: int,
        attack_bonus: int = 0,
    ) -> dict:
        """
        Roll d20 + attack_bonus vs target's AC.

        A natural 20 always hits; a natural 1 always misses.
        """
        attacker = self.world.get_object(attacker_id)
        target = self.world.get_object(target_id)

        if not attacker:
            return {"error": f"Attacker {attacker_id} not found"}
        if not target:
            return {"error": f"Target {target_id} not found"}

        target_ac = target.properties.get("ac", 10)
        roll_result = roll_dice("d20", self.rng)
        total = roll_result["rolls"][0] + attack_bonus

        if roll_result["critical_hit"]:
            hit = True
        elif roll_result["critical_miss"]:
            hit = False
        else:
            hit = total >= target_ac

        return {
            "attacker": attacker.name or f"object_{attacker_id}",
            "target": target.name or f"object_{target_id}",
            "d20_roll": roll_result["rolls"][0],
            "attack_bonus": attack_bonus,
            "total": total,
            "target_ac": target_ac,
            "hit": hit,
            "critical_hit": roll_result["critical_hit"],
            "critical_miss": roll_result["critical_miss"],
        }

    def roll_saving_throw(self, target_id: int, ability: str, dc: int) -> dict:
        """
        Roll d20 + ability modifier vs DC.

        A natural 20 always succeeds; a natural 1 always fails.
        """
        target = self.world.get_object(target_id)
        if not target:
            return {"error": f"Target {target_id} not found"}

        ability = ability.lower()
        score = target.properties.get("abilities", {}).get(ability, 10)
        modifier = _ability_modifier(score)

        roll_result = roll_dice("d20", self.rng)
        total = roll_result["rolls"][0] + modifier

        if roll_result["critical_hit"]:
            success = True
        elif roll_result["critical_miss"]:
            success = False
        else:
            success = total >= dc

        return {
            "target": target.name or f"object_{target_id}",
            "ability": ability,
            "score": score,
            "d20_roll": roll_result["rolls"][0],
            "modifier": modifier,
            "total": total,
            "dc": dc,
            "success": success,
            "critical_hit": roll_result["critical_hit"],
            "critical_miss": roll_result["critical_miss"],
        }
