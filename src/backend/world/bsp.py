"""
Binary Space Partitioning for procedural child-object placement.

Given a parent object P (with known size) and a player position with radius R,
BspPartitioner divides the available floor area into rectangular cells and
returns placement rectangles for child objects — without exceeding P's
boundary or going beyond R from the player.

Units are in world feet (5-foot grid).  All returned rects are snapped to
the 5-foot grid.

Usage::

    from src.backend.world.bsp import BspPartitioner, Rect

    partitioner = BspPartitioner(rng=random.Random(42))
    rects = partitioner.partition(
        area=Rect(0, 0, 200, 200),      # parent floor area in local coords
        player_pos=(0.0, 0.0),           # player position relative to parent
        radius=50.0,                     # max distance from player
        min_cell=(10, 10),              # minimum rect size (feet)
        max_depth=4,                     # max BSP recursion depth
    )
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


GRID = 5.0  # world resolution in feet


@dataclass
class Rect:
    """Axis-aligned rectangle in local parent coordinates (feet)."""
    x: float
    y: float
    width: float
    height: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.height / 2.0

    def area(self) -> float:
        return self.width * self.height

    def snap(self) -> "Rect":
        """Snap all edges to the 5-foot grid."""
        sx = round(self.x / GRID) * GRID
        sy = round(self.y / GRID) * GRID
        sx2 = round(self.x2 / GRID) * GRID
        sy2 = round(self.y2 / GRID) * GRID
        return Rect(sx, sy, max(GRID, sx2 - sx), max(GRID, sy2 - sy))

    def intersects_radius(self, px: float, py: float, r: float) -> bool:
        """True when any part of this rect falls within radius r of (px, py)."""
        # Closest point on rect to player
        closest_x = max(self.x, min(px, self.x2))
        closest_y = max(self.y, min(py, self.y2))
        dx = closest_x - px
        dy = closest_y - py
        return (dx * dx + dy * dy) <= r * r

    def clip_to(self, outer: "Rect") -> Optional["Rect"]:
        """Return the intersection with outer, or None if no overlap."""
        ix = max(self.x, outer.x)
        iy = max(self.y, outer.y)
        ix2 = min(self.x2, outer.x2)
        iy2 = min(self.y2, outer.y2)
        if ix2 <= ix or iy2 <= iy:
            return None
        return Rect(ix, iy, ix2 - ix, iy2 - iy)


@dataclass
class _BspNode:
    rect: Rect
    left: Optional["_BspNode"] = field(default=None, repr=False)
    right: Optional["_BspNode"] = field(default=None, repr=False)
    leaf: bool = True


class BspPartitioner:
    """
    Splits a floor area into non-overlapping rectangles using binary space
    partitioning.  Leaves of the BSP tree become placement candidates.

    The split axis alternates horizontal / vertical at each depth level to
    produce a varied grid.  A random jitter (±20 %) is applied to the split
    position so rooms are unequal in size — avoiding a rigid chessboard look.

    Args:
        rng: A seeded `random.Random` instance for reproducibility.
    """

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def partition(
        self,
        area: Rect,
        player_pos: tuple[float, float],
        radius: float,
        min_cell: tuple[float, float] = (10.0, 10.0),
        max_depth: int = 4,
    ) -> list[Rect]:
        """
        Partition *area* and return leaf rects that lie (at least partially)
        within *radius* feet of *player_pos*.

        Args:
            area:       The bounding rectangle of the parent object's floor
                        space, in the parent's local coordinate system.
            player_pos: Player's [x, y] in the same coordinate space.
            radius:     Maximum distance from the player; only rects within
                        this radius are returned.
            min_cell:   Minimum (width, height) in feet for any leaf rect.
                        Rects smaller than this are not split further.
            max_depth:  Maximum BSP recursion depth (controls granularity).

        Returns:
            List of :class:`Rect` instances, each snapped to the 5-foot grid,
            that represent candidate placement areas for child objects.
        """
        root = _BspNode(rect=area.snap())
        self._split(root, depth=0, max_depth=max_depth, min_w=min_cell[0], min_h=min_cell[1])

        leaves: list[Rect] = []
        self._collect_leaves(root, leaves)

        px, py = player_pos
        within_radius = [
            r for r in leaves
            if r.intersects_radius(px, py, radius)
        ]

        return within_radius

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _split(
        self,
        node: _BspNode,
        depth: int,
        max_depth: int,
        min_w: float,
        min_h: float,
    ) -> None:
        r = node.rect
        if depth >= max_depth:
            return
        # Decide split axis: alternate H/V with a random 30 % chance of flip
        split_horizontal = (depth % 2 == 0)
        if self.rng.random() < 0.3:
            split_horizontal = not split_horizontal

        if split_horizontal:
            # Split along Y (producing top/bottom children)
            if r.height < min_h * 2:
                return
            # Jitter: split at 40–60 % of height
            ratio = 0.4 + self.rng.random() * 0.2
            split_y = r.y + round((r.height * ratio) / GRID) * GRID
            left_rect = Rect(r.x, r.y, r.width, split_y - r.y)
            right_rect = Rect(r.x, split_y, r.width, r.y2 - split_y)
        else:
            # Split along X (producing left/right children)
            if r.width < min_w * 2:
                return
            ratio = 0.4 + self.rng.random() * 0.2
            split_x = r.x + round((r.width * ratio) / GRID) * GRID
            left_rect = Rect(r.x, r.y, split_x - r.x, r.height)
            right_rect = Rect(split_x, r.y, r.x2 - split_x, r.height)

        # Validate minimum size
        if left_rect.width < min_w or left_rect.height < min_h:
            return
        if right_rect.width < min_w or right_rect.height < min_h:
            return

        node.left = _BspNode(rect=left_rect.snap())
        node.right = _BspNode(rect=right_rect.snap())
        node.leaf = False

        self._split(node.left, depth + 1, max_depth, min_w, min_h)
        self._split(node.right, depth + 1, max_depth, min_w, min_h)

    def _collect_leaves(self, node: _BspNode, out: list[Rect]) -> None:
        if node.leaf:
            out.append(node.rect)
            return
        if node.left:
            self._collect_leaves(node.left, out)
        if node.right:
            self._collect_leaves(node.right, out)
