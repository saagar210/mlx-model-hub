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
        # Insert content using current API
        content_id = await clean_db.insert_content(
            filepath="test/content.md",
            content_type="note",
            title="Test Content",
            content_for_hash="Test content for hashing",
            metadata={"namespace": "default"},
            add_to_review=False,
        )

        assert content_id is not None
        assert isinstance(content_id, UUID)

        # Retrieve content using current API
        content = await clean_db.get_content_by_id(content_id)
        assert content is not None
        assert content.title == "Test Content"
        assert content.type == "note"

    async def test_insert_chunks(self, clean_db: Database):
        """Test chunk insertion and retrieval."""
        # Insert content first using current API
        content_id = await clean_db.insert_content(
            filepath="test/chunked.md",
            content_type="note",
            title="Chunked Content",
            content_for_hash="Chunked content for hashing",
            add_to_review=False,
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
                filepath=f"test/concurrent_{n}.md",
                content_type="note",
                title=f"Concurrent Content {n}",
                content_for_hash=f"Concurrent content {n} for hashing",
                add_to_review=False,
            )

        # Run 20 concurrent inserts
        ids = await asyncio.gather(*[insert_content(i) for i in range(20)])

        assert len(ids) == 20
        assert len(set(ids)) == 20  # All unique

    async def test_pool_stats(self, clean_db: Database):
        """Test connection pool statistics."""
        stats = clean_db.get_pool_stats()

        assert stats is not None
        assert hasattr(stats, "size")
        assert hasattr(stats, "free_size")
        assert hasattr(stats, "min_size")
        assert hasattr(stats, "max_size")
        assert stats.size >= stats.min_size

    async def test_health_check(self, clean_db: Database):
        """Test database health check."""
        health = await clean_db.check_health()

        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        # check_health returns content stats instead of latency
        if health["status"] == "healthy":
            assert "extensions" in health
            assert "pool" in health

    async def test_delete_content(self, clean_db: Database):
        """Test content soft deletion."""
        # Insert content and chunk using current API
        content_id = await clean_db.insert_content(
            filepath="test/to_delete.md",
            content_type="note",
            title="To Delete",
            content_for_hash="Content to delete for hashing",
            add_to_review=False,
        )

        async with clean_db._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chunks (content_id, chunk_index, chunk_text) VALUES ($1, 0, 'chunk')",
                content_id,
            )

        # Soft delete content (current API)
        result = await clean_db.soft_delete_content(content_id)
        assert result is True

        # Verify content is soft-deleted (not retrieved by get_content_by_id)
        content = await clean_db.get_content_by_id(content_id)
        assert content is None

    async def test_namespace_filtering(self, clean_db: Database):
        """Test namespace-based content filtering via metadata."""
        # Insert content in different namespaces using metadata
        await clean_db.insert_content(
            filepath="test/work_doc.md",
            content_type="note",
            title="Work Doc",
            content_for_hash="Work doc content for hashing",
            metadata={"namespace": "work"},
            add_to_review=False,
        )
        await clean_db.insert_content(
            filepath="test/personal_doc.md",
            content_type="note",
            title="Personal Doc",
            content_for_hash="Personal doc content for hashing",
            metadata={"namespace": "personal"},
            add_to_review=False,
        )

        # Query by namespace (stored in metadata)
        async with clean_db._pool.acquire() as conn:
            work_count = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE metadata->>'namespace' = 'work' AND deleted_at IS NULL"
            )
            personal_count = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE metadata->>'namespace' = 'personal' AND deleted_at IS NULL"
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
