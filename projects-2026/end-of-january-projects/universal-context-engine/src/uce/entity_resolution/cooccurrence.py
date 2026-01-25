"""
Entity co-occurrence tracking.

Tracks how often entities appear together to discover implicit relationships.
"""

from collections import defaultdict
from datetime import datetime
from uuid import UUID

import asyncpg


class CooccurrenceTracker:
    """
    Tracks entity co-occurrence for relationship discovery.

    When entities frequently appear together, they likely have
    an implicit relationship worth surfacing.
    """

    def __init__(self, pg_pool: asyncpg.Pool) -> None:
        """
        Initialize co-occurrence tracker.

        Args:
            pg_pool: PostgreSQL connection pool
        """
        self.pg = pg_pool
        self._local_cache: dict[tuple[UUID, UUID], int] = defaultdict(int)
        self._flush_threshold = 100

    async def record(self, entity_ids: list[UUID]) -> None:
        """
        Record co-occurrence of entities.

        Args:
            entity_ids: List of entity IDs that appeared together
        """
        if len(entity_ids) < 2:
            return

        # Record all pairs
        for i, id_a in enumerate(entity_ids):
            for id_b in entity_ids[i + 1:]:
                # Ensure consistent ordering (a < b)
                if str(id_a) > str(id_b):
                    id_a, id_b = id_b, id_a

                self._local_cache[(id_a, id_b)] += 1

        # Flush to database if threshold reached
        if len(self._local_cache) >= self._flush_threshold:
            await self.flush()

    async def record_batch(self, entity_id_lists: list[list[UUID]]) -> None:
        """
        Record co-occurrences for multiple items.

        Args:
            entity_id_lists: List of entity ID lists
        """
        for entity_ids in entity_id_lists:
            await self.record(entity_ids)

    async def flush(self) -> None:
        """Flush cached co-occurrences to database."""
        if not self._local_cache:
            return

        async with self.pg.acquire() as conn:
            # Batch upsert
            for (id_a, id_b), count in self._local_cache.items():
                await conn.execute(
                    """
                    INSERT INTO entity_cooccurrence (entity_a_id, entity_b_id, cooccurrence_count, last_seen_at)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (entity_a_id, entity_b_id)
                    DO UPDATE SET
                        cooccurrence_count = entity_cooccurrence.cooccurrence_count + $3,
                        last_seen_at = NOW()
                    """,
                    id_a,
                    id_b,
                    count,
                )

        self._local_cache.clear()

    async def get_related(
        self,
        entity_id: UUID,
        min_count: int = 2,
        limit: int = 20,
    ) -> list[tuple[UUID, int]]:
        """
        Get entities that frequently co-occur with the given entity.

        Args:
            entity_id: Entity to find related entities for
            min_count: Minimum co-occurrence count
            limit: Maximum results

        Returns:
            List of (entity_id, count) tuples
        """
        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    CASE
                        WHEN entity_a_id = $1 THEN entity_b_id
                        ELSE entity_a_id
                    END as related_id,
                    cooccurrence_count
                FROM entity_cooccurrence
                WHERE (entity_a_id = $1 OR entity_b_id = $1)
                  AND cooccurrence_count >= $2
                ORDER BY cooccurrence_count DESC
                LIMIT $3
                """,
                entity_id,
                min_count,
                limit,
            )

        return [(row["related_id"], row["cooccurrence_count"]) for row in rows]

    async def get_strongest_pairs(
        self,
        min_count: int = 5,
        limit: int = 50,
    ) -> list[tuple[UUID, UUID, int]]:
        """
        Get the strongest co-occurring entity pairs.

        Args:
            min_count: Minimum co-occurrence count
            limit: Maximum results

        Returns:
            List of (entity_a_id, entity_b_id, count) tuples
        """
        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entity_a_id, entity_b_id, cooccurrence_count
                FROM entity_cooccurrence
                WHERE cooccurrence_count >= $1
                ORDER BY cooccurrence_count DESC
                LIMIT $2
                """,
                min_count,
                limit,
            )

        return [
            (row["entity_a_id"], row["entity_b_id"], row["cooccurrence_count"])
            for row in rows
        ]

    async def suggest_relationships(
        self,
        min_count: int = 5,
        confidence_threshold: float = 0.7,
    ) -> list[dict]:
        """
        Suggest relationships based on strong co-occurrence.

        Args:
            min_count: Minimum co-occurrence count
            confidence_threshold: Minimum confidence for suggestion

        Returns:
            List of relationship suggestions with confidence scores
        """
        pairs = await self.get_strongest_pairs(min_count=min_count, limit=100)

        suggestions = []
        for id_a, id_b, count in pairs:
            # Calculate confidence based on count
            # Higher count = higher confidence
            confidence = min(1.0, count / 20)  # Cap at 20 co-occurrences

            if confidence >= confidence_threshold:
                suggestions.append({
                    "from_entity_id": id_a,
                    "to_entity_id": id_b,
                    "relationship_type": "related_to",
                    "confidence": confidence,
                    "cooccurrence_count": count,
                })

        return suggestions


__all__ = ["CooccurrenceTracker"]
