"""Database operations using asyncpg (P12: Connection Pool Management)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

import asyncpg
from pgvector.asyncpg import register_vector

from knowledge.config import Settings, get_settings
from knowledge.exceptions import (
    ConnectionError,
    ConnectionPoolExhaustedError,
    DatabaseError,
    QueryError,
    TransactionError,
)
from knowledge.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


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


@dataclass
class PoolStats:
    """Connection pool statistics."""

    size: int
    free_size: int
    used_size: int
    min_size: int
    max_size: int

    def to_dict(self) -> dict[str, int]:
        return {
            "size": self.size,
            "free_size": self.free_size,
            "used_size": self.used_size,
            "min_size": self.min_size,
            "max_size": self.max_size,
        }


def _build_namespace_filter(
    namespace: str | None, param_num: int
) -> tuple[str, list[Any]]:
    """
    Build namespace filter clause for SQL queries.

    Args:
        namespace: Namespace filter (supports trailing * for prefix match)
        param_num: Starting parameter number for the clause

    Returns:
        Tuple of (SQL clause fragment, list of parameter values)
        Returns ("", []) if namespace is None
    """
    if namespace is None:
        return "", []

    if namespace.endswith("*"):
        # Prefix match: "projects/*" matches "projects/voice-ai", "projects/kas"
        ns_pattern = namespace[:-1] + "%"
        return f"AND COALESCE(c.metadata->>'namespace', 'default') LIKE ${param_num}", [ns_pattern]
    else:
        # Exact match
        return f"AND COALESCE(c.metadata->>'namespace', 'default') = ${param_num}", [namespace]


class Database:
    """Async database connection pool manager with retry logic and health monitoring."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._pool: asyncpg.Pool | None = None
        self._connection_attempts: int = 0
        self._last_health_check: datetime | None = None

    async def connect(self) -> None:
        """Create connection pool with configured settings."""
        if self._pool is not None:
            return

        try:
            self._pool = await asyncpg.create_pool(
                self.settings.database_url,
                min_size=self.settings.db_pool_min,
                max_size=self.settings.db_pool_max,
                max_inactive_connection_lifetime=self.settings.db_pool_max_inactive_time,
                command_timeout=self.settings.db_command_timeout,
                init=self._init_connection,
            )
            self._connection_attempts = 0
            logger.info(
                "database_connected",
                pool_min=self.settings.db_pool_min,
                pool_max=self.settings.db_pool_max,
            )
        except Exception as e:
            self._connection_attempts += 1
            logger.error(
                "database_connection_failed",
                error=str(e),
                attempts=self._connection_attempts,
            )
            raise ConnectionError(
                f"Failed to create connection pool: {e}",
                details={"attempts": self._connection_attempts},
                cause=e,
            ) from e

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize each connection with pgvector and JSON support."""
        await register_vector(conn)
        # Set up JSON codec for JSONB columns
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    async def disconnect(self) -> None:
        """Close connection pool gracefully."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("database_disconnected")

    async def close(self) -> None:
        """Alias for disconnect() for common API convention."""
        await self.disconnect()

    def get_pool_stats(self) -> PoolStats | None:
        """Get current connection pool statistics."""
        if self._pool is None:
            return None
        return PoolStats(
            size=self._pool.get_size(),
            free_size=self._pool.get_idle_size(),
            used_size=self._pool.get_size() - self._pool.get_idle_size(),
            min_size=self._pool.get_min_size(),
            max_size=self._pool.get_max_size(),
        )

    async def _execute_with_retry(
        self,
        operation: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute an operation with exponential backoff retry logic."""
        last_error: Exception | None = None

        for attempt in range(self.settings.db_retry_attempts):
            try:
                return await operation(*args, **kwargs)  # type: ignore[misc]
            except asyncpg.PostgresConnectionError as e:
                last_error = e
                if attempt < self.settings.db_retry_attempts - 1:
                    delay = self.settings.db_retry_delay * (2**attempt)
                    logger.warning(
                        "database_retry",
                        attempt=attempt + 1,
                        max_attempts=self.settings.db_retry_attempts,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
            except asyncpg.TooManyConnectionsError as e:
                raise ConnectionPoolExhaustedError(
                    "Connection pool exhausted",
                    details={"pool_stats": self.get_pool_stats()},
                    cause=e,
                ) from e
            except asyncpg.PostgresError as e:
                raise QueryError(str(e), cause=e) from e

        raise ConnectionError(
            f"Failed after {self.settings.db_retry_attempts} attempts",
            details={"last_error": str(last_error)},
            cause=last_error,
        )

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire a connection from the pool with retry logic."""
        if self._pool is None:
            raise DatabaseError("Database not connected. Call connect() first.")

        try:
            async with self._pool.acquire(timeout=self.settings.db_pool_timeout) as conn:
                yield conn
        except TimeoutError as e:
            stats = self.get_pool_stats()
            raise ConnectionPoolExhaustedError(
                "Timeout waiting for connection",
                details={"pool_stats": stats.to_dict() if stats else None},
                cause=e,
            ) from e
        except asyncpg.PostgresConnectionError as e:
            raise ConnectionError(
                f"Connection error: {e}",
                cause=e,
            ) from e

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire a connection with an active transaction."""
        if self._pool is None:
            raise DatabaseError("Database not connected. Call connect() first.")

        try:
            async with self._pool.acquire(timeout=self.settings.db_pool_timeout) as conn:
                async with conn.transaction():
                    yield conn
        except TimeoutError as e:
            raise ConnectionPoolExhaustedError(
                "Timeout waiting for connection",
                cause=e,
            ) from e
        except asyncpg.PostgresError as e:
            raise TransactionError(
                f"Transaction failed: {e}",
                cause=e,
            ) from e

    async def check_health(self) -> dict[str, Any]:
        """Check database health and return comprehensive status."""
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

                # Get pool stats
                pool_stats = self.get_pool_stats()

                self._last_health_check = datetime.now()

                return {
                    "status": "healthy",
                    "extensions": ext_names,
                    "content_count": content_count,
                    "chunk_count": chunk_count,
                    "pool": pool_stats.to_dict() if pool_stats else None,
                    "last_check": self._last_health_check.isoformat(),
                }
        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            return {"status": "unhealthy", "error": str(e)}

    async def check_connection_health(self, conn: asyncpg.Connection) -> bool:
        """Check if a specific connection is healthy."""
        try:
            result = await conn.fetchval("SELECT 1")
            return result == 1
        except Exception:
            return False

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
        """Insert a new content record and optionally add to review queue."""
        content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
        metadata_dict = metadata or {}  # Pass dict directly, codec handles JSON encoding

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
                        "duplicate_content_detected",
                        filepath=filepath,
                        existing_filepath=existing["filepath"],
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
                metadata_dict,
                captured_at,
            )
            content_id = row["id"]

            # Auto-enroll in review queue
            if add_to_review:
                from fsrs import Card  # type: ignore[import-untyped]

                card = Card()
                # Pass dict directly to asyncpg, it handles JSONB conversion
                fsrs_state = card.to_dict()
                await conn.execute(
                    """
                    INSERT INTO review_queue (content_id, fsrs_state, next_review, status)
                    VALUES ($1, $2, NOW(), 'active')
                    ON CONFLICT (content_id) DO NOTHING
                    """,
                    content_id,
                    fsrs_state,
                )

            logger.info(
                "content_inserted",
                content_id=str(content_id),
                content_type=content_type,
                title=title,
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
            deleted = result == "UPDATE 1"
            if deleted:
                logger.info("content_deleted", content_id=str(content_id))
            return deleted

    async def update_content_tags(self, content_id: UUID, tags: list[str]) -> bool:
        """Update tags for content.

        Args:
            content_id: Content UUID
            tags: List of tags to set

        Returns:
            True if update succeeded
        """
        async with self.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE content
                SET tags = $2, updated_at = NOW()
                WHERE id = $1 AND deleted_at IS NULL
                """,
                content_id,
                tags,
            )
            updated = result == "UPDATE 1"
            if updated:
                logger.info(
                    "content_tags_updated",
                    content_id=str(content_id),
                    tag_count=len(tags),
                )
            return updated

    async def get_content(self, content_id: UUID) -> dict[str, Any] | None:
        """Get content as dictionary (for CLI compatibility).

        Args:
            content_id: Content UUID

        Returns:
            Content as dict or None if not found
        """
        record = await self.get_content_by_id(content_id)
        if record is None:
            return None
        return {
            "id": record.id,
            "filepath": record.filepath,
            "title": record.title,
            "type": record.type,
            "url": record.url,
            "summary": record.summary,
            "tags": record.tags or [],
            "auto_tags": record.auto_tags or [],
            "metadata": record.metadata,
            "created_at": record.created_at,
        }

    async def get_chunks(self, content_id: UUID) -> list[dict[str, Any]]:
        """Get chunks for content as list of dicts (for CLI compatibility).

        Args:
            content_id: Content UUID

        Returns:
            List of chunk dicts
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, chunk_index, chunk_text, source_ref, start_char, end_char
                FROM chunks
                WHERE content_id = $1
                ORDER BY chunk_index
                """,
                content_id,
            )
            return [dict(row) for row in rows]

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

            await conn.executemany(
                """
                INSERT INTO chunks (content_id, chunk_index, chunk_text, embedding,
                                   embedding_model, embedding_version, source_ref, start_char, end_char)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                records,
            )

            rows = await conn.fetch(
                "SELECT id FROM chunks WHERE content_id = $1 ORDER BY chunk_index",
                content_id,
            )
            chunk_ids = [row["id"] for row in rows]
            logger.debug(
                "chunks_inserted",
                content_id=str(content_id),
                count=len(chunk_ids),
            )
            return chunk_ids

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
        namespace: str | None = None,
    ) -> list[tuple[UUID, str, str, str | None, str | None, float]]:
        """BM25 full-text search on content with chunk text."""
        ns_clause, ns_params = _build_namespace_filter(namespace, 3)

        async with self.acquire() as conn:
            rows = await conn.fetch(
                f"""
                WITH ranked_content AS (
                    SELECT c.id, c.title, c.type,
                           c.metadata->>'namespace' as namespace,
                           ts_rank_cd(c.fts_vector, query) AS rank
                    FROM content c, plainto_tsquery('english', $1) query
                    WHERE c.fts_vector @@ query
                      AND c.deleted_at IS NULL
                      {ns_clause}
                    ORDER BY rank DESC
                    LIMIT $2
                )
                SELECT rc.id, rc.title, rc.type, rc.namespace,
                       (SELECT ch.chunk_text FROM chunks ch
                        WHERE ch.content_id = rc.id
                        ORDER BY ch.chunk_index LIMIT 1) as chunk_text,
                       rc.rank
                FROM ranked_content rc
                ORDER BY rc.rank DESC
                """,
                query,
                limit,
                *ns_params,
            )
            return [(row["id"], row["title"], row["type"], row["namespace"], row["chunk_text"], row["rank"]) for row in rows]

    async def vector_search(
        self,
        query_embedding: list[float],
        limit: int = 50,
        namespace: str | None = None,
    ) -> list[tuple[UUID, str, str, str | None, str | None, float]]:
        """Vector similarity search on chunks."""
        ns_clause, ns_params = _build_namespace_filter(namespace, 3)

        async with self.acquire() as conn:
            rows = await conn.fetch(
                f"""
                WITH ranked_chunks AS (
                    SELECT
                        c.id,
                        c.title,
                        c.type,
                        c.metadata->>'namespace' as namespace,
                        ch.chunk_text,
                        1 - (ch.embedding <=> $1::vector) AS similarity,
                        ROW_NUMBER() OVER (PARTITION BY c.id ORDER BY ch.embedding <=> $1::vector) AS rn
                    FROM chunks ch
                    JOIN content c ON ch.content_id = c.id
                    WHERE c.deleted_at IS NULL
                      {ns_clause}
                )
                SELECT id, title, type, namespace, chunk_text, similarity
                FROM ranked_chunks
                WHERE rn = 1
                ORDER BY similarity DESC
                LIMIT $2
                """,
                query_embedding,
                limit,
                *ns_params,
            )
            return [
                (row["id"], row["title"], row["type"], row["namespace"], row["chunk_text"], row["similarity"])
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

            pool_stats = self.get_pool_stats()

            return {
                "content_by_type": {row["type"]: row["count"] for row in content_by_type},
                "total_content": total_content,
                "total_chunks": total_chunks,
                "review_active": review_active,
                "review_due": review_due,
                "pool": pool_stats.to_dict() if pool_stats else None,
            }

    async def log_search_query(
        self,
        query: str,
        result_count: int,
        top_score: float | None = None,
        avg_score: float | None = None,
        namespace: str | None = None,
        reranked: bool = False,
        source: str = "api",
    ) -> None:
        """Log a search query for analytics."""
        query_hash = hashlib.sha256(query.lower().strip().encode()).hexdigest()[:32]

        async with self.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO search_queries (
                    query_text, query_hash, namespace, result_count,
                    top_score, avg_score, reranked, source
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                query,
                query_hash,
                namespace,
                result_count,
                top_score,
                avg_score,
                reranked,
                source,
            )

    async def get_search_gaps(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get queries with poor results for gap analysis."""
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM search_gaps
                LIMIT $1
                """,
                limit,
            )
            return [dict(row) for row in rows]

    async def get_search_analytics(self) -> dict[str, Any]:
        """Get search analytics summary."""
        async with self.acquire() as conn:
            total_queries = await conn.fetchval(
                "SELECT COUNT(*) FROM search_queries"
            )
            today_queries = await conn.fetchval(
                "SELECT COUNT(*) FROM search_queries WHERE created_at > NOW() - INTERVAL '1 day'"
            )
            zero_results = await conn.fetchval(
                "SELECT COUNT(*) FROM search_queries WHERE result_count = 0"
            )
            low_score = await conn.fetchval(
                "SELECT COUNT(*) FROM search_queries WHERE top_score < 0.3 AND result_count > 0"
            )
            avg_top_score = await conn.fetchval(
                "SELECT AVG(top_score) FROM search_queries WHERE top_score IS NOT NULL"
            )

            return {
                "total_queries": total_queries or 0,
                "queries_today": today_queries or 0,
                "zero_results_count": zero_results or 0,
                "low_score_count": low_score or 0,
                "avg_top_score": float(avg_top_score) if avg_top_score else None,
                "gap_rate": (zero_results + low_score) / total_queries if total_queries else 0,
            }

    async def get_quality_scores(
        self,
        content_ids: list[UUID],
    ) -> dict[UUID, float]:
        """Get quality scores for multiple content IDs."""
        if not content_ids:
            return {}

        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, COALESCE(quality_score, 0.5) as quality_score
                FROM content
                WHERE id = ANY($1)
                """,
                content_ids,
            )
            return {row["id"]: row["quality_score"] for row in rows}

    # =========================================================================
    # Entity Operations (Knowledge Graph)
    # =========================================================================

    async def insert_entity(
        self,
        content_id: UUID,
        name: str,
        entity_type: str,
        confidence: float = 1.0,
    ) -> UUID:
        """Insert a new entity.

        Args:
            content_id: Content this entity was extracted from
            name: Entity name
            entity_type: Type (technology, concept, tool, framework, organization, person)
            confidence: Extraction confidence score

        Returns:
            Entity UUID
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO entities (content_id, name, entity_type, confidence)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                content_id,
                name,
                entity_type,
                confidence,
            )
            return row["id"]

    async def insert_entities_batch(
        self,
        content_id: UUID,
        entities: list[dict[str, Any]],
    ) -> list[UUID]:
        """Insert multiple entities in a batch.

        Args:
            content_id: Content this entity was extracted from
            entities: List of dicts with name, entity_type, confidence

        Returns:
            List of entity UUIDs
        """
        if not entities:
            return []

        async with self.acquire() as conn:
            records = [
                (
                    content_id,
                    e["name"],
                    e["entity_type"],
                    e.get("confidence", 1.0),
                )
                for e in entities
            ]

            await conn.executemany(
                """
                INSERT INTO entities (content_id, name, entity_type, confidence)
                VALUES ($1, $2, $3, $4)
                """,
                records,
            )

            # Get the inserted IDs
            rows = await conn.fetch(
                """
                SELECT id FROM entities
                WHERE content_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                content_id,
                len(entities),
            )
            return [row["id"] for row in rows]

    async def insert_relationship(
        self,
        from_entity_id: UUID,
        to_entity_id: UUID,
        relation_type: str,
        confidence: float = 1.0,
    ) -> UUID | None:
        """Insert a new relationship between entities.

        Args:
            from_entity_id: Source entity UUID
            to_entity_id: Target entity UUID
            relation_type: Relationship type (uses, depends_on, implements, related_to, mentions)
            confidence: Confidence score

        Returns:
            Relationship UUID or None if duplicate
        """
        async with self.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO relationships (from_entity_id, to_entity_id, relation_type, confidence)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (from_entity_id, to_entity_id, relation_type) DO NOTHING
                    RETURNING id
                    """,
                    from_entity_id,
                    to_entity_id,
                    relation_type,
                    confidence,
                )
                return row["id"] if row else None
            except Exception as e:
                logger.warning(
                    "insert_relationship_failed",
                    from_entity_id=str(from_entity_id),
                    to_entity_id=str(to_entity_id),
                    error=str(e),
                )
                return None

    async def get_entities_by_content(
        self, content_id: UUID
    ) -> list[dict[str, Any]]:
        """Get all entities for a content item.

        Args:
            content_id: Content UUID

        Returns:
            List of entity dicts
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, entity_type, confidence, created_at
                FROM entities
                WHERE content_id = $1
                ORDER BY confidence DESC, name
                """,
                content_id,
            )
            return [dict(row) for row in rows]

    async def get_entity_by_name(
        self, name: str, entity_type: str | None = None
    ) -> dict[str, Any] | None:
        """Get entity by name (case-insensitive).

        Args:
            name: Entity name
            entity_type: Optional type filter

        Returns:
            Entity dict or None
        """
        async with self.acquire() as conn:
            if entity_type:
                row = await conn.fetchrow(
                    """
                    SELECT id, content_id, name, entity_type, confidence, created_at
                    FROM entities
                    WHERE LOWER(name) = LOWER($1) AND entity_type = $2
                    LIMIT 1
                    """,
                    name,
                    entity_type,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT id, content_id, name, entity_type, confidence, created_at
                    FROM entities
                    WHERE LOWER(name) = LOWER($1)
                    LIMIT 1
                    """,
                    name,
                )
            return dict(row) if row else None

    async def get_relationships_by_entity(
        self, entity_id: UUID
    ) -> list[dict[str, Any]]:
        """Get all relationships for an entity (both directions).

        Args:
            entity_id: Entity UUID

        Returns:
            List of relationship dicts with entity names
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.id, r.relation_type, r.confidence,
                       e_from.name as from_name, e_from.entity_type as from_type,
                       e_to.name as to_name, e_to.entity_type as to_type
                FROM relationships r
                JOIN entities e_from ON r.from_entity_id = e_from.id
                JOIN entities e_to ON r.to_entity_id = e_to.id
                WHERE r.from_entity_id = $1 OR r.to_entity_id = $1
                ORDER BY r.confidence DESC
                """,
                entity_id,
            )
            return [dict(row) for row in rows]

    async def get_entity_stats(self) -> list[dict[str, Any]]:
        """Get entity statistics by type.

        Returns:
            List of dicts with entity_type, count, unique_names
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT entity_type, COUNT(*) as count,
                       COUNT(DISTINCT name) as unique_names
                FROM entities
                GROUP BY entity_type
                ORDER BY count DESC
                """
            )
            return [dict(row) for row in rows]

    async def get_connected_entities(
        self, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get most connected entities.

        Args:
            limit: Maximum number of entities to return

        Returns:
            List of dicts with name, entity_type, connection_count
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT name, entity_type, connection_count
                FROM connected_entities
                LIMIT $1
                """,
                limit,
            )
            return [dict(row) for row in rows]

    async def delete_entities_by_content(self, content_id: UUID) -> int:
        """Delete all entities (and their relationships) for a content item.

        Args:
            content_id: Content UUID

        Returns:
            Number of entities deleted
        """
        async with self.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM entities WHERE content_id = $1",
                content_id,
            )
            # Parse "DELETE N" to get count
            count = int(result.split()[-1])
            if count > 0:
                logger.info(
                    "entities_deleted",
                    content_id=str(content_id),
                    count=count,
                )
            return count


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
