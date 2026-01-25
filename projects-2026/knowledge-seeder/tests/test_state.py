"""Tests for state manager."""

from datetime import datetime
from pathlib import Path

import pytest

from knowledge_seeder.state import StateManager
from knowledge_seeder.models import SourceState, SourceStatus, SourceType


@pytest.fixture
async def state_manager(tmp_path):
    """Create a state manager with temporary database."""
    db_path = tmp_path / "test_state.db"
    manager = StateManager(db_path=db_path)
    await manager.connect()
    yield manager
    await manager.close()


@pytest.fixture
def sample_state():
    """Create a sample source state."""
    return SourceState(
        source_id="test:sample",
        name="sample",
        url="https://example.com",
        namespace="test",
        source_type=SourceType.URL,
        status=SourceStatus.PENDING,
    )


class TestStateManager:
    """Tests for StateManager."""

    @pytest.mark.asyncio
    async def test_create_and_get_source(self, state_manager, sample_state):
        """Test creating and retrieving a source."""
        await state_manager.upsert_source(sample_state)

        retrieved = await state_manager.get_source(sample_state.source_id)
        assert retrieved is not None
        assert retrieved.source_id == sample_state.source_id
        assert retrieved.name == sample_state.name
        assert retrieved.status == SourceStatus.PENDING

    @pytest.mark.asyncio
    async def test_update_status(self, state_manager, sample_state):
        """Test updating source status."""
        await state_manager.upsert_source(sample_state)

        await state_manager.update_status(
            sample_state.source_id,
            SourceStatus.EXTRACTING,
        )

        retrieved = await state_manager.get_source(sample_state.source_id)
        assert retrieved.status == SourceStatus.EXTRACTING

    @pytest.mark.asyncio
    async def test_mark_extracted(self, state_manager, sample_state):
        """Test marking source as extracted."""
        await state_manager.upsert_source(sample_state)

        await state_manager.mark_extracted(
            sample_state.source_id,
            content_hash="abc123",
            content_length=1000,
        )

        retrieved = await state_manager.get_source(sample_state.source_id)
        assert retrieved.status == SourceStatus.EXTRACTED
        assert retrieved.content_hash == "abc123"
        assert retrieved.content_length == 1000

    @pytest.mark.asyncio
    async def test_mark_completed(self, state_manager, sample_state):
        """Test marking source as completed."""
        await state_manager.upsert_source(sample_state)

        await state_manager.mark_completed(
            sample_state.source_id,
            document_id="doc-123",
            chunk_count=5,
        )

        retrieved = await state_manager.get_source(sample_state.source_id)
        assert retrieved.status == SourceStatus.COMPLETED
        assert retrieved.document_id == "doc-123"
        assert retrieved.chunk_count == 5

    @pytest.mark.asyncio
    async def test_mark_failed(self, state_manager, sample_state):
        """Test marking source as failed."""
        await state_manager.upsert_source(sample_state)

        await state_manager.mark_failed(sample_state.source_id, "Connection error")

        retrieved = await state_manager.get_source(sample_state.source_id)
        assert retrieved.status == SourceStatus.FAILED
        assert retrieved.error_message == "Connection error"
        assert retrieved.retry_count == 1

    @pytest.mark.asyncio
    async def test_list_sources_by_status(self, state_manager):
        """Test listing sources by status."""
        # Create sources with different statuses
        for i, status in enumerate([SourceStatus.PENDING, SourceStatus.COMPLETED, SourceStatus.FAILED]):
            state = SourceState(
                source_id=f"test:source-{i}",
                name=f"source-{i}",
                url=f"https://example.com/{i}",
                namespace="test",
                source_type=SourceType.URL,
                status=status,
            )
            await state_manager.upsert_source(state)

        # List pending only
        pending = await state_manager.list_sources(status=SourceStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].status == SourceStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_stats(self, state_manager):
        """Test getting statistics."""
        # Create some sources
        for i in range(3):
            state = SourceState(
                source_id=f"test:source-{i}",
                name=f"source-{i}",
                url=f"https://example.com/{i}",
                namespace="test",
                source_type=SourceType.URL,
                status=SourceStatus.PENDING,
            )
            await state_manager.upsert_source(state)

        stats = await state_manager.get_stats()
        assert stats["total"] == 3
        assert stats["pending"] == 3

    @pytest.mark.asyncio
    async def test_get_namespaces(self, state_manager):
        """Test getting list of namespaces."""
        # Create sources in different namespaces
        for ns in ["alpha", "beta", "gamma"]:
            state = SourceState(
                source_id=f"{ns}:source",
                name="source",
                url=f"https://example.com/{ns}",
                namespace=ns,
                source_type=SourceType.URL,
                status=SourceStatus.PENDING,
            )
            await state_manager.upsert_source(state)

        namespaces = await state_manager.get_namespaces()
        assert set(namespaces) == {"alpha", "beta", "gamma"}

    def test_compute_content_hash(self):
        """Test content hash computation."""
        hash1 = StateManager.compute_content_hash("test content")
        hash2 = StateManager.compute_content_hash("test content")
        hash3 = StateManager.compute_content_hash("different content")

        assert hash1 == hash2  # Same content, same hash
        assert hash1 != hash3  # Different content, different hash
        assert len(hash1) == 16  # Truncated to 16 chars
