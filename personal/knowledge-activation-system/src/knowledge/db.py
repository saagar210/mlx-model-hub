"""Database operations using asyncpg."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
from pgvector.asyncpg import register_vector

from knowledge.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class ContentRecord:
    """Content table record."""

    id: UUID
    filepath: str
    content_hash: str
    type: str
    url: str | None
    title: str
    summary: str | None
    auto_tags: list[str]
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    captured_at: datetime | None
    deleted_at: datetime | None


@dataclass
class ChunkRecord:
    """Chunk table record."""

    id: UUID
    content_id: UUID
    chunk_index: int
    chunk_text: str
    embedding: list[float] | None
    embedding_model: str
    embedding_version: str
    source_ref: str | None
    start_char: int | None
    end_char: int | None


class Database:
    """Async database connection pool manager."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Create connection pool."""
        if self._pool is not None:
            return

        self._pool = await asyncpg.create_pool(
            self.settings.database_url,
            min_size=self.settings.db_pool_min,
            max_size=self.settings.db_pool_max,
            command_timeout=self.settings.db_command_timeout,
            init=self._init_connection,
        )

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize each connection with pgvector support."""
        await register_vector(conn)

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire a connection from the pool."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        async with self._pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Acquire a connection with an active transaction.

        Use this for multi-step operations that need atomicity.
        The transaction will be committed on success or rolled back on error.
        """
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def check_health(self) -> dict[str, Any]:
        """Check database health and return status."""
        try:
            async with self.acquire() as conn:
                # Check basic connectivity
                result = await conn.fetchval("SELECT 1")
                if result != 1:
                    return {"status": "unhealthy", "error": "Query returned unexpected result"}

                # Check extensions
                extensions = await conn.fetch(
                    "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'vectorscale')"
                )
                ext_names = [r["extname"] for r in extensions]

                # Get table counts
                content_count = await conn.fetchval("SELECT COUNT(*) FROM content")
                chunk_count = await conn.fetchval("SELECT COUNT(*) FROM chunks")

                return {
                    "status": "healthy",
                    "extensions": ext_names,
                    "content_count": content_count,
                    "chunk_count": chunk_count,
                }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    # =========================================================================
    # Content Operations
    # =========================================================================

    async def insert_content(
        self,
        filepath: str,
        content_type: str,
        title: str,
        content_for_hash: str,
        url: str | None = None,
        summary: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        captured_at: datetime | None = None,
        add_to_review: bool = True,
        deduplicate: bool = True,
    ) -> UUID:
        """
        Insert a new content record and optionally add to review queue.

        Args:
            filepath: Path to Obsidian note
            content_type: Type of content (youtube, bookmark, file, note)
            title: Content title
            content_for_hash: Content to hash for deduplication
            url: Optional URL source
            summary: Optional summary
            tags: Optional list of tags
            metadata: Optional metadata dict
            captured_at: Optional capture timestamp
            add_to_review: Add to review queue (default True)
            deduplicate: Check for duplicate content by hash (default True)

        Returns:
            UUID of inserted/existing content
        """
        content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
        # Serialize metadata to JSON string for JSONB column
        metadata_json = json.dumps(metadata or {})

        # Check for duplicate content by hash
        if deduplicate:
            async with self.acquire() as conn:
                existing = await conn.fetchrow(
                    """
                    SELECT id, filepath FROM content
                    WHERE content_hash = $1 AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    content_hash,
                )
                if existing:
                    logger.info(
                        f"Duplicate content detected: {filepath} matches existing {existing['filepath']}"
                    )
                    content_id: UUID = existing["id"]
                    return content_id

        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO content (filepath, content_hash, type, url, title, summary, tags, metadata, captured_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
                RETURNING id
                """,
                filepath,
                content_hash,
                content_type,
                url,
                title,
                summary,
                tags or [],
                metadata_json,
                captured_at,
            )
            content_id = row["id"]

            # Auto-enroll in review queue
            if add_to_review:
                # Create default FSRS card state using Card().to_dict()
                from fsrs import Card

                card = Card()
                fsrs_state = json.dumps(card.to_dict())
                await conn.execute(
                    """
                    INSERT INTO review_queue (content_id, fsrs_state, next_review, status)
                    VALUES ($1, $2::jsonb, NOW(), 'active')
                    ON CONFLICT (content_id) DO NOTHING
                    """,
                    content_id,
                    fsrs_state,
                )

            return content_id

    async def get_content_by_id(self, content_id: UUID) -> ContentRecord | None:
        """Get content by ID."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, filepath, content_hash, type, url, title, summary,
                       auto_tags, tags, metadata, created_at, updated_at, captured_at, deleted_at
                FROM content
                WHERE id = $1 AND deleted_at IS NULL
                """,
                content_id,
            )
            if row is None:
                return None
            return ContentRecord(**dict(row))

    async def get_content_by_filepath(self, filepath: str) -> ContentRecord | None:
        """Get content by filepath."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, filepath, content_hash, type, url, title, summary,
                       auto_tags, tags, metadata, created_at, updated_at, captured_at, deleted_at
                FROM content
                WHERE filepath = $1 AND deleted_at IS NULL
                """,
                filepath,
            )
            if row is None:
                return None
            return ContentRecord(**dict(row))

    async def content_exists(self, filepath: str) -> bool:
        """Check if content exists by filepath."""
        async with self.acquire() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM content WHERE filepath = $1 AND deleted_at IS NULL)",
                filepath,
            )
            return result

    async def soft_delete_content(self, content_id: UUID) -> bool:
        """Soft delete content by ID."""
        async with self.acquire() as conn:
            result = await conn.execute(
                "UPDATE content SET deleted_at = NOW() WHERE id = $1 AND deleted_at IS NULL",
                content_id,
            )
            return result == "UPDATE 1"

    # =========================================================================
    # Chunk Operations
    # =========================================================================

    async def insert_chunks(
        self,
        content_id: UUID,
        chunks: list[dict[str, Any]],
    ) -> list[UUID]:
        """Insert multiple chunks for a content record."""
        async with self.acquire() as conn:
            # Prepare data for batch insert
            records = [
                (
                    content_id,
                    chunk["chunk_index"],
                    chunk["chunk_text"],
                    chunk.get("embedding"),
                    chunk.get("embedding_model", "nomic-embed-text"),
                    chunk.get("embedding_version", "v1.5"),
                    chunk.get("source_ref"),
                    chunk.get("start_char"),
                    chunk.get("end_char"),
                )
                for chunk in chunks
            ]

            # Use COPY for efficient batch insert
            await conn.executemany(
                """
                INSERT INTO chunks (content_id, chunk_index, chunk_text, embedding,
                                   embedding_model, embedding_version, source_ref, start_char, end_char)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                records,
            )

            # Fetch the IDs
            rows = await conn.fetch(
                "SELECT id FROM chunks WHERE content_id = $1 ORDER BY chunk_index",
                content_id,
            )
            return [row["id"] for row in rows]

    async def get_chunks_by_content_id(self, content_id: UUID) -> list[ChunkRecord]:
        """Get all chunks for a content record."""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, content_id, chunk_index, chunk_text, embedding,
                       embedding_model, embedding_version, source_ref, start_char, end_char
                FROM chunks
                WHERE content_id = $1
                ORDER BY chunk_index
                """,
                content_id,
            )
            return [ChunkRecord(**dict(row)) for row in rows]

    # =========================================================================
    # Search Operations
    # =========================================================================

    async def bm25_search(
        self,
        query: str,
        limit: int = 50,
    ) -> list[tuple[UUID, str, str, float]]:
        """
        BM25 full-text search on content.

        Returns: List of (content_id, title, type, rank)
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT c.id, c.title, c.type,
                       ts_rank_cd(c.fts_vector, query) AS rank
                FROM content c, plainto_tsquery('english', $1) query
                WHERE c.fts_vector @@ query AND c.deleted_at IS NULL
                ORDER BY rank DESC
                LIMIT $2
                """,
                query,
                limit,
            )
            return [(row["id"], row["title"], row["type"], row["rank"]) for row in rows]

    async def vector_search(
        self,
        query_embedding: list[float],
        limit: int = 50,
    ) -> list[tuple[UUID, str, str, str | None, float]]:
        """
        Vector similarity search on chunks.

        Uses a subquery to find the best matching chunk per content,
        then sorts globally by similarity.

        Returns: List of (content_id, title, type, chunk_text, similarity)
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH ranked_chunks AS (
                    SELECT
                        c.id,
                        c.title,
                        c.type,
                        ch.chunk_text,
                        1 - (ch.embedding <=> $1::vector) AS similarity,
                        ROW_NUMBER() OVER (PARTITION BY c.id ORDER BY ch.embedding <=> $1::vector) AS rn
                    FROM chunks ch
                    JOIN content c ON ch.content_id = c.id
                    WHERE c.deleted_at IS NULL
                )
                SELECT id, title, type, chunk_text, similarity
                FROM ranked_chunks
                WHERE rn = 1
                ORDER BY similarity DESC
                LIMIT $2
                """,
                query_embedding,
                limit,
            )
            return [
                (row["id"], row["title"], row["type"], row["chunk_text"], row["similarity"])
                for row in rows
            ]

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        async with self.acquire() as conn:
            content_by_type = await conn.fetch(
                """
                SELECT type, COUNT(*) as count
                FROM content
                WHERE deleted_at IS NULL
                GROUP BY type
                """
            )

            total_content = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE deleted_at IS NULL"
            )
            total_chunks = await conn.fetchval("SELECT COUNT(*) FROM chunks")
            review_active = await conn.fetchval(
                "SELECT COUNT(*) FROM review_queue WHERE status = 'active'"
            )
            review_due = await conn.fetchval(
                """
                SELECT COUNT(*) FROM review_queue
                WHERE status = 'active' AND next_review <= NOW()
                """
            )

            return {
                "content_by_type": {row["type"]: row["count"] for row in content_by_type},
                "total_content": total_content,
                "total_chunks": total_chunks,
                "review_active": review_active,
                "review_due": review_due,
            }


# Global database instance
_db: Database | None = None


async def get_db() -> Database:
    """Get or create global database instance."""
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
    return _db


async def close_db() -> None:
    """Close global database instance."""
    global _db
    if _db is not None:
        await _db.disconnect()
        _db = None
