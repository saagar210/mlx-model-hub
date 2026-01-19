"""Tests for database operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from knowledge.config import Settings
from knowledge.db import ChunkRecord, ContentRecord, Database
from knowledge.exceptions import DatabaseError


class TestDatabaseConnection:
    """Tests for database connection management."""

    @pytest.mark.asyncio
    async def test_connect_creates_pool(self, test_settings: Settings):
        """Test that connect creates a connection pool."""
        db = Database(test_settings)

        with patch("knowledge.db.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = MagicMock()
            await db.connect()

            mock_pool.assert_called_once()
            assert db._pool is not None

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, test_settings: Settings):
        """Test that multiple connect calls don't create multiple pools."""
        db = Database(test_settings)

        with patch("knowledge.db.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = MagicMock()

            await db.connect()
            await db.connect()

            # Should only create pool once
            mock_pool.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_closes_pool(self, test_settings: Settings):
        """Test that disconnect closes the pool."""
        db = Database(test_settings)

        mock_pool = MagicMock()
        mock_pool.close = AsyncMock()

        with patch("knowledge.db.asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_pool

            await db.connect()
            await db.disconnect()

            mock_pool.close.assert_called_once()
            assert db._pool is None

    @pytest.mark.asyncio
    async def test_acquire_without_connect_raises(self, test_settings: Settings):
        """Test that acquire raises without connect."""
        db = Database(test_settings)

        with pytest.raises(DatabaseError, match="not connected"):
            async with db.acquire():
                pass


class TestHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, mock_db: MagicMock):
        """Test health check returns healthy status."""
        result = await mock_db.check_health()

        assert result["status"] == "healthy"
        assert "vector" in result["extensions"]
        assert result["content_count"] == 10

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, test_settings: Settings):
        """Test health check returns unhealthy on error."""
        db = Database(test_settings)

        # Don't connect - should fail
        result = await db.check_health()

        assert result["status"] == "unhealthy"
        assert "error" in result


class TestContentOperations:
    """Tests for content CRUD operations."""

    @pytest.mark.asyncio
    async def test_insert_content_returns_uuid(self, mock_db: MagicMock):
        """Test that insert_content returns a UUID."""
        expected_id = uuid4()
        mock_db.insert_content = AsyncMock(return_value=expected_id)

        result = await mock_db.insert_content(
            filepath="test.md",
            content_type="note",
            title="Test Note",
            content_for_hash="test content",
        )

        assert result == expected_id
        assert isinstance(result, UUID)

    @pytest.mark.asyncio
    async def test_get_content_by_id(self, mock_db: MagicMock):
        """Test retrieving content by ID."""
        content_id = uuid4()
        mock_record = ContentRecord(
            id=content_id,
            filepath="test.md",
            content_hash="abc123",
            type="note",
            url=None,
            title="Test Note",
            summary=None,
            auto_tags=[],
            tags=["test"],
            metadata={},
            created_at=None,
            updated_at=None,
            captured_at=None,
            deleted_at=None,
        )
        mock_db.get_content_by_id = AsyncMock(return_value=mock_record)

        result = await mock_db.get_content_by_id(content_id)

        assert result.id == content_id
        assert result.title == "Test Note"

    @pytest.mark.asyncio
    async def test_content_exists(self, mock_db: MagicMock):
        """Test checking if content exists."""
        mock_db.content_exists = AsyncMock(return_value=True)

        result = await mock_db.content_exists("test.md")

        assert result is True

    @pytest.mark.asyncio
    async def test_soft_delete_content(self, mock_db: MagicMock):
        """Test soft deleting content."""
        content_id = uuid4()
        mock_db.soft_delete_content = AsyncMock(return_value=True)

        result = await mock_db.soft_delete_content(content_id)

        assert result is True


class TestChunkOperations:
    """Tests for chunk operations."""

    @pytest.mark.asyncio
    async def test_insert_chunks(self, mock_db: MagicMock, sample_chunks: list[dict]):
        """Test inserting chunks."""
        content_id = uuid4()
        expected_ids = [uuid4(), uuid4()]
        mock_db.insert_chunks = AsyncMock(return_value=expected_ids)

        result = await mock_db.insert_chunks(content_id, sample_chunks)

        assert len(result) == len(expected_ids)
        assert all(isinstance(id, UUID) for id in result)

    @pytest.mark.asyncio
    async def test_get_chunks_by_content_id(self, mock_db: MagicMock):
        """Test retrieving chunks by content ID."""
        content_id = uuid4()
        mock_chunks = [
            ChunkRecord(
                id=uuid4(),
                content_id=content_id,
                chunk_index=0,
                chunk_text="First chunk",
                embedding=None,
                embedding_model="nomic-embed-text",
                embedding_version="v1.5",
                source_ref=None,
                start_char=0,
                end_char=11,
            )
        ]
        mock_db.get_chunks_by_content_id = AsyncMock(return_value=mock_chunks)

        result = await mock_db.get_chunks_by_content_id(content_id)

        assert len(result) == 1
        assert result[0].chunk_index == 0


class TestSearchOperations:
    """Tests for search operations."""

    @pytest.mark.asyncio
    async def test_bm25_search(
        self, mock_db: MagicMock, sample_bm25_results: list[tuple]
    ):
        """Test BM25 search returns results."""
        mock_db.bm25_search = AsyncMock(return_value=sample_bm25_results)

        result = await mock_db.bm25_search("machine learning", limit=10)

        assert len(result) == 3
        # Results should be tuples of (id, title, type, namespace, chunk_text, rank)
        assert len(result[0]) == 6

    @pytest.mark.asyncio
    async def test_vector_search(
        self, mock_db: MagicMock, sample_vector_results: list[tuple], mock_embedding: list[float]
    ):
        """Test vector search returns results."""
        mock_db.vector_search = AsyncMock(return_value=sample_vector_results)

        result = await mock_db.vector_search(mock_embedding, limit=10)

        assert len(result) == 3
        # Results should be tuples of (id, title, type, namespace, chunk_text, similarity)
        assert len(result[0]) == 6


class TestStats:
    """Tests for statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_db: MagicMock):
        """Test getting database statistics."""
        result = await mock_db.get_stats()

        assert "content_by_type" in result
        assert "total_content" in result
        assert "total_chunks" in result
        assert "review_active" in result
        assert "review_due" in result
        assert result["total_content"] == 10


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests requiring actual database."""

    @pytest.mark.asyncio
    async def test_full_content_lifecycle(self, db: Database, sample_content_data: dict):
        """Test creating, retrieving, and deleting content."""
        # Insert content
        content_id = await db.insert_content(**sample_content_data)
        assert isinstance(content_id, UUID)

        # Retrieve by ID
        content = await db.get_content_by_id(content_id)
        assert content is not None
        assert content.title == sample_content_data["title"]

        # Check exists
        exists = await db.content_exists(sample_content_data["filepath"])
        assert exists is True

        # Soft delete
        deleted = await db.soft_delete_content(content_id)
        assert deleted is True

        # Should not find after deletion
        content = await db.get_content_by_id(content_id)
        assert content is None

    @pytest.mark.asyncio
    async def test_health_check_integration(self, db: Database):
        """Test health check with actual database."""
        result = await db.check_health()

        assert result["status"] == "healthy"
        assert "vector" in result["extensions"]
