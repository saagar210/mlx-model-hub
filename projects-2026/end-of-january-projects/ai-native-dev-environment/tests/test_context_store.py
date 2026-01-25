"""Tests for the ChromaDB context store."""

import tempfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from universal_context_engine.models import ContextType


class MockEmbeddingClient:
    """Mock embedding client for testing."""

    async def embed(self, text: str) -> list[float]:
        # Create a simple hash-based embedding for testing
        hash_val = hash(text) % 1000
        return [float(hash_val + i) / 1000 for i in range(768)]


@pytest.fixture
def temp_store():
    """Create a temporary context store for testing with mocked embedding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch before importing to avoid module-level instantiation issues
        with patch("universal_context_engine.context_store.embedding_client", MockEmbeddingClient()):
            from universal_context_engine.context_store import ContextStore
            store = ContextStore(persist_directory=tmpdir)
            store._embedding_client = MockEmbeddingClient()
            yield store


@pytest.mark.asyncio
async def test_save_context(temp_store):
    """Test saving a context item."""
    item = await temp_store.save(
        content="Test content for saving",
        context_type=ContextType.CONTEXT,
        project="/test/project",
        metadata={"key": "value"},
    )

    assert item.id is not None
    assert item.content == "Test content for saving"
    assert item.context_type == ContextType.CONTEXT
    assert item.project == "/test/project"
    assert item.metadata == {"key": "value"}


@pytest.mark.asyncio
async def test_save_and_search(temp_store):
    """Test saving and then searching for context."""
    # Save some items
    await temp_store.save(
        content="Working on authentication system",
        context_type=ContextType.SESSION,
        project="/test/project",
    )
    await temp_store.save(
        content="Decided to use JWT for auth tokens",
        context_type=ContextType.DECISION,
        project="/test/project",
    )
    await temp_store.save(
        content="Database connection pooling setup",
        context_type=ContextType.PATTERN,
        project="/test/project",
    )

    # Search for auth-related items
    results = await temp_store.search(
        query="authentication",
        project="/test/project",
        limit=5,
    )

    assert len(results) > 0
    # Results should be sorted by score
    for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score


@pytest.mark.asyncio
async def test_search_with_type_filter(temp_store):
    """Test searching with a type filter."""
    # Save items of different types
    await temp_store.save(
        content="Session about API design",
        context_type=ContextType.SESSION,
        project="/test/project",
    )
    await temp_store.save(
        content="Decision about API versioning",
        context_type=ContextType.DECISION,
        project="/test/project",
    )

    # Search only decisions
    results = await temp_store.search(
        query="API",
        context_type=ContextType.DECISION,
        project="/test/project",
    )

    # Should only return decisions
    for result in results:
        assert result.item.context_type == ContextType.DECISION


@pytest.mark.asyncio
async def test_get_recent(temp_store):
    """Test getting recent items."""
    # Save some items
    await temp_store.save(
        content="Recent work item 1",
        context_type=ContextType.CONTEXT,
        project="/test/project",
    )
    await temp_store.save(
        content="Recent work item 2",
        context_type=ContextType.CONTEXT,
        project="/test/project",
    )

    # Get recent items
    items = await temp_store.get_recent(
        project="/test/project",
        hours=1,
        limit=10,
    )

    assert len(items) == 2
    # Should be sorted by timestamp descending
    assert items[0].timestamp >= items[1].timestamp


@pytest.mark.asyncio
async def test_get_stats(temp_store):
    """Test getting statistics."""
    # Save some items
    await temp_store.save(
        content="Session 1",
        context_type=ContextType.SESSION,
    )
    await temp_store.save(
        content="Decision 1",
        context_type=ContextType.DECISION,
    )
    await temp_store.save(
        content="Decision 2",
        context_type=ContextType.DECISION,
    )

    stats = await temp_store.get_stats()

    assert stats["session"] == 1
    assert stats["decision"] == 2


@pytest.mark.asyncio
async def test_delete(temp_store):
    """Test deleting a context item."""
    # Save an item
    item = await temp_store.save(
        content="Item to delete",
        context_type=ContextType.CONTEXT,
    )

    # Delete it
    result = await temp_store.delete(item.id, ContextType.CONTEXT)
    assert result is True

    # Verify it's gone
    stats = await temp_store.get_stats()
    assert stats["context"] == 0
