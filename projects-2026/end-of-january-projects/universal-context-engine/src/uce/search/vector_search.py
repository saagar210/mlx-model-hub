"""
Vector similarity search using pgvector.
"""

from uuid import UUID

import asyncpg


class VectorSearch:
    """
    Vector similarity search using PostgreSQL pgvector extension.
    """

    def __init__(self, pg_pool: asyncpg.Pool) -> None:
        """
        Initialize vector search.

        Args:
            pg_pool: PostgreSQL connection pool
        """
        self.pg = pg_pool

    async def search(
        self,
        embedding: list[float],
        limit: int = 50,
        source_filter: list[str] | None = None,
        type_filter: list[str] | None = None,
        namespace: str | None = None,
    ) -> list[dict]:
        """
        Search for similar items by embedding.

        Args:
            embedding: Query embedding vector
            limit: Maximum results
            source_filter: Filter by sources
            type_filter: Filter by content types
            namespace: Filter by namespace

        Returns:
            List of dicts with id and score
        """
        # Build WHERE clause
        conditions = [
            "embedding IS NOT NULL",
            "t_expired IS NULL",
            "(expires_at IS NULL OR expires_at > NOW())",
        ]
        params: list = [embedding, limit]
        param_idx = 3

        if source_filter:
            conditions.append(f"source = ANY(${param_idx})")
            params.append(source_filter)
            param_idx += 1

        if type_filter:
            conditions.append(f"content_type = ANY(${param_idx})")
            params.append(type_filter)
            param_idx += 1

        if namespace:
            conditions.append(f"namespace = ${param_idx}")
            params.append(namespace)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                id,
                1 - (embedding <=> $1::vector) AS score
            FROM context_items
            WHERE {where_clause}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
        """

        async with self.pg.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [
            {"id": row["id"], "score": float(row["score"]), "match_type": "vector"}
            for row in rows
        ]

    async def find_similar(
        self,
        item_id: UUID,
        limit: int = 10,
    ) -> list[dict]:
        """
        Find items similar to a given item.

        Args:
            item_id: ID of the item to find similar items for
            limit: Maximum results

        Returns:
            List of similar items with scores
        """
        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    b.id,
                    1 - (a.embedding <=> b.embedding) AS score
                FROM context_items a, context_items b
                WHERE a.id = $1
                  AND b.id != $1
                  AND b.embedding IS NOT NULL
                  AND b.t_expired IS NULL
                ORDER BY a.embedding <=> b.embedding
                LIMIT $2
                """,
                item_id,
                limit,
            )

        return [
            {"id": row["id"], "score": float(row["score"]), "match_type": "similar"}
            for row in rows
        ]


__all__ = ["VectorSearch"]
