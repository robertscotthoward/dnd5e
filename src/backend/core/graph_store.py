"""Memgraph graph store for world object relationships."""

from typing import Optional
from neo4j import GraphDatabase
from rich.console import Console

from .config import settings
from ..models.world import World, Object

console = Console()


class GraphStore:
    """
    Memgraph graph store for object relationships.

    Stores the parent/child hierarchy and enables efficient traversal queries.
    Uses the neo4j driver which is compatible with Memgraph.
    """

    def __init__(self):
        self._driver = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Memgraph."""
        if self._connected:
            return True

        try:
            self._driver = GraphDatabase.driver(
                settings.memgraph.uri,
                auth=(settings.memgraph.user, settings.memgraph.password) if settings.memgraph.user else None,
            )
            # Test connection
            with self._driver.session() as session:
                session.run("RETURN 1")
            self._connected = True
            return True
        except Exception as e:
            console.print(f"[yellow]Could not connect to Memgraph: {e}[/yellow]")
            console.print("[yellow]Graph features will be disabled.[/yellow]")
            self._connected = False
            return False

    def close(self) -> None:
        """Close the connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def sync_world(self, world: World) -> int:
        """
        Sync world objects to the graph database.

        Creates/updates nodes and relationships.

        Returns:
            Number of nodes synced
        """
        if not self.connect():
            return 0

        count = 0
        with self._driver.session() as session:
            # Clear existing data for this world
            session.run("MATCH (n:Object) DETACH DELETE n")

            # Create nodes
            for obj in world.objects.values():
                session.run(
                    """
                    CREATE (o:Object {
                        id: $id,
                        type: $type,
                        name: $name,
                        parent: $parent
                    })
                    """,
                    id=obj.id,
                    type=obj.type,
                    name=obj.name or "",
                    parent=obj.parent,
                )
                count += 1

            # Create relationships
            for obj in world.objects.values():
                if obj.parent is not None:
                    session.run(
                        """
                        MATCH (child:Object {id: $child_id})
                        MATCH (parent:Object {id: $parent_id})
                        CREATE (child)-[:CHILD_OF]->(parent)
                        """,
                        child_id=obj.id,
                        parent_id=obj.parent,
                    )

        return count

    def get_ancestors(self, obj_id: int) -> list[dict]:
        """Get all ancestors of an object."""
        if not self.connect():
            return []

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (start:Object {id: $id})
                MATCH path = (start)-[:CHILD_OF*]->(ancestor)
                RETURN ancestor.id AS id, ancestor.type AS type, ancestor.name AS name
                ORDER BY length(path)
                """,
                id=obj_id,
            )
            return [dict(record) for record in result]

    def get_descendants(self, obj_id: int) -> list[dict]:
        """Get all descendants of an object."""
        if not self.connect():
            return []

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (start:Object {id: $id})
                MATCH path = (descendant)-[:CHILD_OF*]->(start)
                RETURN descendant.id AS id, descendant.type AS type, descendant.name AS name
                ORDER BY length(path)
                """,
                id=obj_id,
            )
            return [dict(record) for record in result]

    def get_siblings(self, obj_id: int) -> list[dict]:
        """Get all siblings of an object (same parent)."""
        if not self.connect():
            return []

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (obj:Object {id: $id})-[:CHILD_OF]->(parent)
                MATCH (sibling)-[:CHILD_OF]->(parent)
                WHERE sibling.id <> $id
                RETURN sibling.id AS id, sibling.type AS type, sibling.name AS name
                """,
                id=obj_id,
            )
            return [dict(record) for record in result]

    def find_path(self, from_id: int, to_id: int) -> Optional[list[dict]]:
        """Find the shortest path between two objects."""
        if not self.connect():
            return None

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (start:Object {id: $from_id}), (end:Object {id: $to_id})
                MATCH path = shortestPath((start)-[:CHILD_OF*]-(end))
                RETURN [node IN nodes(path) | {id: node.id, type: node.type, name: node.name}] AS path
                """,
                from_id=from_id,
                to_id=to_id,
            )
            record = result.single()
            return record["path"] if record else None

    def get_objects_by_type(self, obj_type: str) -> list[dict]:
        """Get all objects of a specific type."""
        if not self.connect():
            return []

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (o:Object {type: $type})
                RETURN o.id AS id, o.type AS type, o.name AS name, o.parent AS parent
                """,
                type=obj_type,
            )
            return [dict(record) for record in result]

    def get_visible_objects(self, observer_id: int, max_depth: int = 3) -> list[dict]:
        """
        Get objects visible from the observer's location.

        Visibility includes:
        - All ancestors up to root
        - Siblings at the same level
        - Children up to max_depth
        """
        if not self.connect():
            return []

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (observer:Object {id: $id})

                // Get ancestors
                OPTIONAL MATCH ancestor_path = (observer)-[:CHILD_OF*]->(ancestor)

                // Get siblings
                OPTIONAL MATCH (observer)-[:CHILD_OF]->(parent)
                OPTIONAL MATCH (sibling)-[:CHILD_OF]->(parent)

                // Get children
                OPTIONAL MATCH (child)-[:CHILD_OF*1..3]->(observer)

                WITH collect(DISTINCT ancestor) + collect(DISTINCT sibling) + collect(DISTINCT child) + [observer] AS visible
                UNWIND visible AS obj
                WHERE obj IS NOT NULL
                RETURN DISTINCT obj.id AS id, obj.type AS type, obj.name AS name, obj.parent AS parent
                """,
                id=observer_id,
            )
            return [dict(record) for record in result]


# Global graph store instance
graph_store = GraphStore()
