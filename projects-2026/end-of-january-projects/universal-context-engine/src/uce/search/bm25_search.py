"""
BM25 full-text search using PostgreSQL tsvector.
"""

from uuid import UUID

import asyncpg


class BM25Search:
    """
    Full-text search using PostgreSQL tsvector and ts_rank_cd.
    """

    def __init__(self, pg_pool: asyncpg.Pool) -> None:
        """
        Initialize BM25 search.

        Args:
            pg_pool: PostgreSQL connection pool
        """
        self.pg = pg_pool

    async def search(
        self,
        query: str,
        limit: int = 50,
        source_filter: list[str] | None = None,
        type_filter: list[str] | None = None,
        namespace: str | None = None,
    ) -> list[dict]:
        """
        Full-text search using PostgreSQL.

        Args:
            query: Search query text
            limit: Maximum results
            source_filter: Filter by sources
            type_filter: Filter by content types
            namespace: Filter by namespace

        Returns:
            List of dicts with id and score
        """
        # Build WHERE clause
        conditions = [
            "fts_vector @@ plainto_tsquery('english', $1)",
            "t_expired IS NULL",
            "(expires_at IS NULL OR expires_at > NOW())",
        ]
        params: list = [query, limit]
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

        sql = f"""
            SELECT
                id,
                ts_rank_cd(fts_vector, plainto_tsquery('english', $1)) AS score
            FROM context_items
            WHERE {where_clause}
            ORDER BY score DESC
            LIMIT $2
        """

        async with self.pg.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        return [
            {"id": row["id"], "score": float(row["score"]), "match_type": "bm25"}
            for row in rows
        ]

    async def search_phrase(
        self,
        phrase: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        Search for exact phrase match.

        Args:
            phrase: Exact phrase to search for
            limit: Maximum results

        Returns:
            List of matching items
        """
        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    ts_rank_cd(fts_vector, phraseto_tsquery('english', $1)) AS score
                FROM context_items
                WHERE fts_vector @@ phraseto_tsquery('english', $1)
                  AND t_expired IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY score DESC
                LIMIT $2
                """,
                phrase,
                limit,
            )

        return [
            {"id": row["id"], "score": float(row["score"]), "match_type": "phrase"}
            for row in rows
        ]

    async def search_prefix(
        self,
        prefix: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        Search with prefix matching (autocomplete).

        Args:
            prefix: Prefix to match
            limit: Maximum results

        Returns:
            List of matching items
        """
        # Use prefix matching with :*
        tsquery = f"{prefix}:*"

        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    ts_rank_cd(fts_vector, to_tsquery('english', $1)) AS score
                FROM context_items
                WHERE fts_vector @@ to_tsquery('english', $1)
                  AND t_expired IS NULL
                ORDER BY score DESC
                LIMIT $2
                """,
                tsquery,
                limit,
            )

        return [
            {"id": row["id"], "score": float(row["score"]), "match_type": "prefix"}
            for row in rows
        ]

    async def get_headlines(
        self,
        item_id: UUID,
        query: str,
        max_words: int = 35,
    ) -> str | None:
        """
        Get highlighted snippet for a search result.

        Args:
            item_id: Item ID
            query: Original search query
            max_words: Maximum words in headline

        Returns:
            Highlighted snippet or None
        """
        async with self.pg.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ts_headline(
                    'english',
                    content,
                    plainto_tsquery('english', $2),
                    'MaxWords=$3, MinWords=15, ShortWord=3'
                ) AS headline
                FROM context_items
                WHERE id = $1
                """,
                item_id,
                query,
                max_words,
            )

            if row:
                return row["headline"]
        return None


__all__ = ["BM25Search"]
