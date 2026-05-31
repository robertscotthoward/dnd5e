"""Memgraph graph database client for the D&D 5e world object graph.

Connects via Bolt protocol (bolt://localhost:7687).
Nodes represent world objects; edges represent parent relationships.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from neo4j import GraphDatabase, Driver

if TYPE_CHECKING:
    from src.backend.models.world import Object, World

logger = logging.getLogger(__name__)

_BOLT_URL = "bolt://localhost:7687"


def _get_driver(url: str = _BOLT_URL) -> Driver:
    """Return a new Bolt driver connected to Memgraph."""
    return GraphDatabase.driver(url, auth=None)


def _obj_to_props(obj: "Object") -> dict:
    """Convert a world Object into the flat property dict stored on a graph node."""
    return {
        "obj_id": obj.id,
        "type": obj.type,
        "name": obj.name or "",
        "description": obj.description or "",
        "weight": obj.weight,
        "cost": obj.cost,
        "is_moveable": obj.is_moveable,
        "is_virtual": obj.is_virtual,
        "loc_x": obj.location.x,
        "loc_y": obj.location.y,
        "loc_z": obj.location.z,
    }


def seed_world(world: "World", url: str = _BOLT_URL) -> int:
    """Mirror every object in *world* into Memgraph.

    Clears all existing nodes/edges, then creates:
      - One (:WorldObject) node per object with all scalar properties.
      - One [:CHILD_OF] edge from each object to its parent.

    Returns the number of nodes created.
    """
    driver = _get_driver(url)
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            count = 0
            for obj in world.objects.values():
                session.run(
                    "CREATE (n:WorldObject $props)",
                    props=_obj_to_props(obj),
                )
                count += 1

            for obj in world.objects.values():
                if obj.parent is not None and obj.parent in world.objects:
                    session.run(
                        """
                        MATCH (child:WorldObject {obj_id: $child_id})
                        MATCH (parent:WorldObject {obj_id: $parent_id})
                        CREATE (child)-[:CHILD_OF]->(parent)
                        """,
                        child_id=obj.id,
                        parent_id=obj.parent,
                    )
        return count
    finally:
        driver.close()


def upsert_object(obj_id: int, props: dict, parent_id: int | None, url: str = _BOLT_URL) -> None:
    """Create or update a single WorldObject node and its CHILD_OF edge."""
    driver = _get_driver(url)
    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (n:WorldObject {obj_id: $obj_id})
                SET n += $props
                """,
                obj_id=obj_id,
                props=props,
            )
            session.run(
                "MATCH (:WorldObject {obj_id: $id})-[r:CHILD_OF]->() DELETE r",
                id=obj_id,
            )
            if parent_id is not None:
                session.run(
                    """
                    MATCH (child:WorldObject {obj_id: $child_id})
                    MATCH (parent:WorldObject {obj_id: $parent_id})
                    MERGE (child)-[:CHILD_OF]->(parent)
                    """,
                    child_id=obj_id,
                    parent_id=parent_id,
                )
    finally:
        driver.close()


def delete_object(obj_id: int, url: str = _BOLT_URL) -> None:
    """Remove a WorldObject node and all its edges from the graph."""
    driver = _get_driver(url)
    try:
        with driver.session() as session:
            session.run(
                "MATCH (n:WorldObject {obj_id: $id}) DETACH DELETE n",
                id=obj_id,
            )
    finally:
        driver.close()


def get_path_between(id1: int, id2: int, url: str = _BOLT_URL) -> list[dict]:
    """Return the shortest path between two WorldObject nodes via CHILD_OF edges.

    Uses bidirectional BFS through the parent hierarchy (undirected CHILD_OF).
    Each hop is returned as a dict with ``obj_id``, ``type``, and ``name``.
    Returns an empty list when no path exists or either node is absent.
    """
    driver = _get_driver(url)
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH path = shortestPath(
                    (a:WorldObject {obj_id: $id1})-[:CHILD_OF*]-(b:WorldObject {obj_id: $id2})
                )
                RETURN [n IN nodes(path) | {obj_id: n.obj_id, type: n.type, name: n.name}] AS hops
                """,
                id1=id1,
                id2=id2,
            )
            record = result.single()
            if record is None:
                return []
            return list(record["hops"])
    finally:
        driver.close()


def get_nearby_objects(obj_id: int, radius: float, url: str = _BOLT_URL) -> list[dict]:
    """Return WorldObject nodes within *radius* feet of the given object.

    Distance is computed in the flat (x, y) plane using the ``loc_x`` / ``loc_y``
    properties stored on each node.  The source object itself is excluded.
    Each result is a dict with ``obj_id``, ``type``, ``name``, and ``distance``.
    Returns an empty list when the source object is not found.
    """
    driver = _get_driver(url)
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (src:WorldObject {obj_id: $obj_id})
                MATCH (other:WorldObject)
                WHERE other.obj_id <> $obj_id
                WITH other,
                     sqrt(
                         (other.loc_x - src.loc_x)^2 +
                         (other.loc_y - src.loc_y)^2
                     ) AS dist
                WHERE dist <= $radius
                RETURN other.obj_id AS obj_id,
                       other.type   AS type,
                       other.name   AS name,
                       dist         AS distance
                ORDER BY dist
                """,
                obj_id=obj_id,
                radius=radius,
            )
            return [
                {
                    "obj_id": r["obj_id"],
                    "type": r["type"],
                    "name": r["name"],
                    "distance": r["distance"],
                }
                for r in result
            ]
    finally:
        driver.close()
