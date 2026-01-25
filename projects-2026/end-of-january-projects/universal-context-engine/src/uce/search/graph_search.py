"""
Graph-based search for entity relationships.
"""

from uuid import UUID

import asyncpg


class GraphSearch:
    """
    Graph-based search traversing entity relationships.
    """

    def __init__(self, pg_pool: asyncpg.Pool) -> None:
        """
        Initialize graph search.

        Args:
            pg_pool: PostgreSQL connection pool
        """
        self.pg = pg_pool

    async def search_by_entity(
        self,
        entity_name: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        Find context items mentioning an entity.

        Args:
            entity_name: Entity name to search for
            limit: Maximum results

        Returns:
            List of matching items
        """
        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    0.8 AS score
                FROM context_items
                WHERE $1 = ANY(entities)
                  AND t_expired IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY t_valid DESC
                LIMIT $2
                """,
                entity_name,
                limit,
            )

        return [
            {"id": row["id"], "score": float(row["score"]), "match_type": "entity"}
            for row in rows
        ]

    async def search_by_entities(
        self,
        entity_names: list[str],
        require_all: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """
        Find context items mentioning multiple entities.

        Args:
            entity_names: List of entity names
            require_all: If True, item must mention all entities
            limit: Maximum results

        Returns:
            List of matching items
        """
        if not entity_names:
            return []

        if require_all:
            # All entities must be present
            operator = "@>"
        else:
            # Any entity matches
            operator = "&&"

        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT
                    id,
                    array_length(
                        ARRAY(SELECT unnest(entities) INTERSECT SELECT unnest($1::text[])),
                        1
                    )::float / $2 AS score
                FROM context_items
                WHERE entities {operator} $1
                  AND t_expired IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY score DESC, t_valid DESC
                LIMIT $3
                """,
                entity_names,
                len(entity_names),
                limit,
            )

        return [
            {"id": row["id"], "score": float(row["score"] or 0.5), "match_type": "entities"}
            for row in rows
        ]

    async def expand_via_relationships(
        self,
        entity_id: UUID,
        hops: int = 1,
        limit: int = 50,
    ) -> list[dict]:
        """
        Find context items via entity relationships.

        Traverses relationships to find related items.

        Args:
            entity_id: Starting entity ID
            hops: Number of relationship hops
            limit: Maximum results

        Returns:
            List of items related through relationships
        """
        if hops < 1:
            hops = 1
        elif hops > 3:
            hops = 3  # Limit to prevent explosion

        # Get related entity IDs
        related_ids = await self._get_related_entity_ids(entity_id, hops)

        if not related_ids:
            return []

        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    0.6 AS score
                FROM context_items
                WHERE entity_ids && $1
                  AND t_expired IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY t_valid DESC
                LIMIT $2
                """,
                [str(rid) for rid in related_ids],
                limit,
            )

        return [
            {"id": row["id"], "score": float(row["score"]), "match_type": "relationship"}
            for row in rows
        ]

    async def _get_related_entity_ids(
        self,
        entity_id: UUID,
        hops: int,
    ) -> list[UUID]:
        """Get entity IDs within N hops of the given entity."""
        visited: set[UUID] = {entity_id}
        frontier: set[UUID] = {entity_id}

        async with self.pg.acquire() as conn:
            for _ in range(hops):
                if not frontier:
                    break

                # Get entities connected to frontier
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT
                        CASE
                            WHEN from_entity_id = ANY($1) THEN to_entity_id
                            ELSE from_entity_id
                        END AS related_id
                    FROM entity_relationships
                    WHERE (from_entity_id = ANY($1) OR to_entity_id = ANY($1))
                      AND t_invalid IS NULL
                    """,
                    list(frontier),
                )

                new_ids = {row["related_id"] for row in rows} - visited
                visited.update(new_ids)
                frontier = new_ids

        # Remove the starting entity
        visited.discard(entity_id)
        return list(visited)

    async def find_paths(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        max_hops: int = 3,
    ) -> list[list[UUID]]:
        """
        Find paths between two entities.

        Args:
            from_entity_id: Starting entity
            to_entity_id: Target entity
            max_hops: Maximum path length

        Returns:
            List of paths (each path is a list of entity IDs)
        """
        # BFS to find paths
        paths: list[list[UUID]] = []
        queue: list[list[UUID]] = [[from_entity_id]]

        async with self.pg.acquire() as conn:
            while queue and len(paths) < 10:  # Limit paths
                path = queue.pop(0)

                if len(path) > max_hops + 1:
                    continue

                current = path[-1]

                if current == to_entity_id:
                    paths.append(path)
                    continue

                # Get neighbors
                rows = await conn.fetch(
                    """
                    SELECT
                        CASE
                            WHEN from_entity_id = $1 THEN to_entity_id
                            ELSE from_entity_id
                        END AS neighbor_id
                    FROM entity_relationships
                    WHERE (from_entity_id = $1 OR to_entity_id = $1)
                      AND t_invalid IS NULL
                    """,
                    current,
                )

                for row in rows:
                    neighbor = row["neighbor_id"]
                    if neighbor not in path:  # Avoid cycles
                        queue.append(path + [neighbor])

        return paths


__all__ = ["GraphSearch"]
