"""Database integration tests.

Tests database operations with a real PostgreSQL + pgvector instance.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from knowledge.db import Database


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations."""

    async def test_insert_and_retrieve_content(self, clean_db: Database):
        """Test full content lifecycle with real database."""
        # Insert content
        content_id = await clean_db.insert_content(
            title="Test Content",
            content_type="note",
            source_ref="test/content.md",
            namespace="default",
        )

        assert content_id is not None
        assert isinstance(content_id, UUID)

        # Retrieve content
        content = await clean_db.get_content(content_id)
        assert content is not None
        assert content["title"] == "Test Content"
        assert content["content_type"] == "note"

    async def test_insert_chunks(self, clean_db: Database):
        """Test chunk insertion and retrieval."""
        # Insert content first
        content_id = await clean_db.insert_content(
            title="Chunked Content",
            content_type="note",
            source_ref="test/chunked.md",
        )

        # Insert chunks
        chunks = [
            "First chunk of text about Python.",
            "Second chunk about machine learning.",
            "Third chunk about database optimization.",
        ]

        async with clean_db._pool.acquire() as conn:
            for i, text in enumerate(chunks):
                await conn.execute(
                    """
                    INSERT INTO chunks (content_id, chunk_index, chunk_text)
                    VALUES ($1, $2, $3)
                    """,
                    content_id,
                    i,
                    text,
                )

        # Verify chunks
        async with clean_db._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT chunk_text FROM chunks WHERE content_id = $1 ORDER BY chunk_index",
                content_id,
            )
            assert len(rows) == 3
            assert rows[0]["chunk_text"] == chunks[0]

    async def test_concurrent_inserts(self, clean_db: Database):
        """Test database handles concurrent inserts."""

        async def insert_content(n: int) -> UUID:
            return await clean_db.insert_content(
                title=f"Concurrent Content {n}",
                content_type="note",
                source_ref=f"test/concurrent_{n}.md",
            )

        # Run 20 concurrent inserts
        ids = await asyncio.gather(*[insert_content(i) for i in range(20)])

        assert len(ids) == 20
        assert len(set(ids)) == 20  # All unique

    async def test_pool_stats(self, clean_db: Database):
        """Test connection pool statistics."""
        stats = clean_db.get_pool_stats()

        assert "size" in stats
        assert "free_size" in stats
        assert "min_size" in stats
        assert "max_size" in stats
        assert stats["size"] >= stats["min_size"]

    async def test_health_check(self, clean_db: Database):
        """Test database health check."""
        health = await clean_db.check_health()

        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "latency_ms" in health
        assert health["latency_ms"] >= 0

    async def test_delete_content(self, clean_db: Database):
        """Test content deletion cascades to chunks."""
        # Insert content and chunk
        content_id = await clean_db.insert_content(
            title="To Delete",
            content_type="note",
        )

        async with clean_db._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chunks (content_id, chunk_index, chunk_text) VALUES ($1, 0, 'chunk')",
                content_id,
            )

        # Delete content
        result = await clean_db.delete_content(content_id)
        assert result is True

        # Verify cascade
        async with clean_db._pool.acquire() as conn:
            chunks = await conn.fetchval(
                "SELECT COUNT(*) FROM chunks WHERE content_id = $1",
                content_id,
            )
            assert chunks == 0

    async def test_namespace_filtering(self, clean_db: Database):
        """Test namespace-based content filtering."""
        # Insert content in different namespaces
        await clean_db.insert_content(
            title="Work Doc",
            content_type="note",
            namespace="work",
        )
        await clean_db.insert_content(
            title="Personal Doc",
            content_type="note",
            namespace="personal",
        )

        # Query by namespace
        async with clean_db._pool.acquire() as conn:
            work_count = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE namespace = 'work'"
            )
            personal_count = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE namespace = 'personal'"
            )

        assert work_count == 1
        assert personal_count == 1


@pytest.mark.integration
class TestPoolBehavior:
    """Test connection pool behavior under load."""

    async def test_pool_under_concurrent_load(self, clean_db: Database):
        """Test pool handles concurrent queries."""

        async def query():
            async with clean_db._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")

        # Run 50 concurrent queries
        await asyncio.gather(*[query() for _ in range(50)])

    async def test_pool_recovers_from_errors(self, clean_db: Database):
        """Test pool recovers after query errors."""
        # Cause an error
        try:
            async with clean_db._pool.acquire() as conn:
                await conn.execute("SELECT * FROM nonexistent_table")
        except Exception:
            pass

        # Pool should still work
        async with clean_db._pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            assert result == 1
