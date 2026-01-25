"""
Knowledge Activation System adapter.

Directly queries KAS PostgreSQL database for chunks with embeddings.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import asyncpg

from .base import BaseAdapter, SyncCursor
from ..models.context_item import ContextItem, BiTemporalMetadata, RelevanceSignals


class KASAdapter(BaseAdapter):
    """
    Adapter for Knowledge Activation System.

    Connects to the KAS PostgreSQL database and fetches document chunks
    with their embeddings for indexing in UCE.
    """

    name = "Knowledge Activation System"
    source_type = "kas"

    def __init__(self, db_url: str):
        """
        Initialize KAS adapter.

        Args:
            db_url: PostgreSQL connection URL for KAS database
        """
        self.db_url = db_url
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=5,
            )
        return self._pool

    async def fetch_incremental(
        self, cursor: SyncCursor | None = None
    ) -> tuple[list[ContextItem], SyncCursor]:
        """Fetch chunks updated since cursor."""
        pool = await self._get_pool()

        since = cursor.last_sync_at if cursor else datetime.utcnow() - timedelta(days=7)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    ch.id, ch.content_id, ch.chunk_index, ch.chunk_text,
                    ch.embedding, ch.source_ref,
                    c.title, c.type, c.url, c.tags, c.auto_tags, c.metadata,
                    c.updated_at, c.captured_at
                FROM chunks ch
                JOIN content c ON ch.content_id = c.id
                WHERE c.updated_at > $1 AND c.deleted_at IS NULL
                ORDER BY c.updated_at ASC
                LIMIT 1000
                """,
                since,
            )

        items = [self._row_to_item(row) for row in rows]

        new_cursor = SyncCursor(
            source=self.source_type,
            cursor_value=rows[-1]["updated_at"].isoformat() if rows else (
                cursor.cursor_value if cursor else None
            ),
            last_sync_at=datetime.utcnow(),
            items_synced=(cursor.items_synced if cursor else 0) + len(items),
        )

        return items, new_cursor

    async def fetch_recent(self, hours: int = 24) -> list[ContextItem]:
        """Fetch recently updated chunks."""
        pool = await self._get_pool()
        since = datetime.utcnow() - timedelta(hours=hours)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    ch.id, ch.content_id, ch.chunk_index, ch.chunk_text,
                    ch.embedding, ch.source_ref,
                    c.title, c.type, c.url, c.tags, c.auto_tags, c.metadata,
                    c.updated_at, c.captured_at
                FROM chunks ch
                JOIN content c ON ch.content_id = c.id
                WHERE c.updated_at > $1 AND c.deleted_at IS NULL
                ORDER BY c.updated_at DESC
                LIMIT 500
                """,
                since,
            )

        return [self._row_to_item(row) for row in rows]

    async def search(self, query: str, limit: int = 10) -> list[ContextItem]:
        """
        Search KAS for matching content.

        Note: UCE will have its own search, so this is mainly for
        adapter-level testing. Returns items matching by title/content.
        """
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    ch.id, ch.content_id, ch.chunk_index, ch.chunk_text,
                    ch.embedding, ch.source_ref,
                    c.title, c.type, c.url, c.tags, c.auto_tags, c.metadata,
                    c.updated_at, c.captured_at
                FROM chunks ch
                JOIN content c ON ch.content_id = c.id
                WHERE c.deleted_at IS NULL
                  AND (c.title ILIKE $1 OR ch.chunk_text ILIKE $1)
                ORDER BY c.updated_at DESC
                LIMIT $2
                """,
                f"%{query}%",
                limit,
            )

        return [self._row_to_item(row) for row in rows]

    def _row_to_item(self, row: asyncpg.Record) -> ContextItem:
        """Transform database row to ContextItem."""
        # Combine tags and auto_tags
        all_tags = list(set((row["tags"] or []) + (row["auto_tags"] or [])))

        # Parse embedding if present
        embedding = None
        if row["embedding"]:
            # asyncpg returns bytea for vector type, need to parse
            if isinstance(row["embedding"], (list, tuple)):
                embedding = list(row["embedding"])
            elif isinstance(row["embedding"], bytes):
                # pgvector binary format - skip for now, we'll regenerate
                embedding = None
            elif isinstance(row["embedding"], str):
                # Could be array string format
                try:
                    import json
                    embedding = json.loads(row["embedding"])
                except Exception:
                    embedding = None

        return ContextItem(
            id=uuid4(),
            source="kas",
            source_id=f"{row['content_id']}_{row['chunk_index']}",
            source_url=row["url"],
            content_type="document_chunk",
            title=f"{row['title']} (chunk {row['chunk_index']})",
            content=row["chunk_text"],
            embedding=embedding,
            temporal=BiTemporalMetadata(
                t_valid=row["captured_at"] or row["updated_at"],
            ),
            tags=all_tags,
            relevance=RelevanceSignals(source_quality=0.9),
            metadata={
                "kas_content_id": str(row["content_id"]),
                "chunk_index": row["chunk_index"],
                "source_ref": row["source_ref"],
                "content_type": row["type"],
                **(dict(row["metadata"]) if row["metadata"] else {}),
            },
        )

    def get_sync_interval(self) -> timedelta:
        """KAS is relatively stable, sync every 30 minutes."""
        return timedelta(minutes=30)

    def get_source_quality(self) -> float:
        """KAS has curated, high-quality content."""
        return 0.9

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None


__all__ = ["KASAdapter"]
