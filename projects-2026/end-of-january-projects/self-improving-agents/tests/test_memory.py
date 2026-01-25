"""Tests for Memory System."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from sia.memory import (
    EpisodicMemoryManager,
    EpisodicSearchResult,
    MemoryItem,
    ProceduralMemoryManager,
    SemanticMemoryManager,
    SemanticSearchResult,
    SkillSearchResult,
    UnifiedMemoryManager,
    UnifiedSearchResult,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    service = AsyncMock()
    service.embed = AsyncMock(
        return_value=MagicMock(embedding=[0.1] * 768, model="nomic-embed-text-v1.5")
    )
    service.close = AsyncMock()
    return service


@pytest.fixture
def mock_rerank_service():
    """Create a mock rerank service."""
    service = AsyncMock()
    service.rerank = AsyncMock(
        return_value=MagicMock(
            results=[
                MagicMock(index=0, relevance_score=0.9),
                MagicMock(index=1, relevance_score=0.7),
            ]
        )
    )
    service.close = AsyncMock()
    return service


# ============================================================================
# EpisodicSearchResult Tests
# ============================================================================


class TestEpisodicSearchResult:
    """Tests for EpisodicSearchResult dataclass."""

    def test_creation(self):
        """Test creating a search result."""
        memory = MagicMock()
        result = EpisodicSearchResult(
            memory=memory,
            similarity_score=0.8,
            recency_score=0.6,
            importance_score=0.7,
            combined_score=0.73,
        )
        assert result.memory == memory
        assert result.similarity_score == 0.8
        assert result.recency_score == 0.6
        assert result.importance_score == 0.7
        assert result.combined_score == 0.73


# ============================================================================
# SemanticSearchResult Tests
# ============================================================================


class TestSemanticSearchResult:
    """Tests for SemanticSearchResult dataclass."""

    def test_creation(self):
        """Test creating a search result."""
        memory = MagicMock()
        result = SemanticSearchResult(
            memory=memory,
            similarity_score=0.85,
            confidence_score=0.9,
            combined_score=0.87,
        )
        assert result.memory == memory
        assert result.similarity_score == 0.85
        assert result.confidence_score == 0.9
        assert result.combined_score == 0.87


# ============================================================================
# SkillSearchResult Tests
# ============================================================================


class TestSkillSearchResult:
    """Tests for SkillSearchResult dataclass."""

    def test_creation(self):
        """Test creating a search result."""
        skill = MagicMock()
        result = SkillSearchResult(
            skill=skill,
            similarity_score=0.75,
            success_score=0.9,
            recency_score=0.5,
            combined_score=0.72,
        )
        assert result.skill == skill
        assert result.similarity_score == 0.75
        assert result.success_score == 0.9
        assert result.recency_score == 0.5
        assert result.combined_score == 0.72


# ============================================================================
# MemoryItem Tests
# ============================================================================


class TestMemoryItem:
    """Tests for MemoryItem dataclass."""

    def test_creation_minimal(self):
        """Test creating a memory item with minimal fields."""
        item = MemoryItem(
            id=uuid4(),
            memory_type="episodic",
            content="Test content",
            score=0.8,
        )
        assert item.memory_type == "episodic"
        assert item.content == "Test content"
        assert item.score == 0.8
        assert item.metadata == {}

    def test_creation_full(self):
        """Test creating a memory item with all fields."""
        item_id = uuid4()
        now = datetime.utcnow()
        item = MemoryItem(
            id=item_id,
            memory_type="semantic",
            content="A known fact",
            score=0.9,
            timestamp=now,
            confidence=0.95,
            importance=0.7,
            metadata={"fact_type": "rule"},
        )
        assert item.id == item_id
        assert item.memory_type == "semantic"
        assert item.timestamp == now
        assert item.confidence == 0.95
        assert item.importance == 0.7
        assert item.metadata == {"fact_type": "rule"}


# ============================================================================
# UnifiedSearchResult Tests
# ============================================================================


class TestUnifiedSearchResult:
    """Tests for UnifiedSearchResult dataclass."""

    def test_creation(self):
        """Test creating a unified search result."""
        items = [
            MemoryItem(
                id=uuid4(), memory_type="episodic", content="Event 1", score=0.8
            ),
            MemoryItem(
                id=uuid4(), memory_type="semantic", content="Fact 1", score=0.7
            ),
        ]
        result = UnifiedSearchResult(
            items=items,
            episodic_count=5,
            semantic_count=3,
            procedural_count=2,
            total_retrieved=10,
            reranked=True,
        )
        assert len(result.items) == 2
        assert result.episodic_count == 5
        assert result.semantic_count == 3
        assert result.procedural_count == 2
        assert result.total_retrieved == 10
        assert result.reranked is True


# ============================================================================
# EpisodicMemoryManager Tests
# ============================================================================


class TestEpisodicMemoryManager:
    """Tests for EpisodicMemoryManager."""

    def test_init(self, mock_session, mock_embedding_service):
        """Test manager initialization."""
        manager = EpisodicMemoryManager(
            session=mock_session,
            embedding_service=mock_embedding_service,
            recency_weight=0.3,
            importance_weight=0.2,
            similarity_weight=0.5,
        )
        assert manager.recency_weight == 0.3
        assert manager.importance_weight == 0.2
        assert manager.similarity_weight == 0.5

    def test_build_embedding_content(self, mock_session):
        """Test building content for embedding."""
        manager = EpisodicMemoryManager(session=mock_session)

        content = manager._build_embedding_content(
            event_type="task_start",
            description="Started processing user request",
            details={"task": "search", "context": "user query"},
        )

        assert "Event: task_start" in content
        assert "Description: Started processing user request" in content
        assert "Task: search" in content

    def test_weight_normalization(self, mock_session):
        """Test that weights work correctly."""
        manager = EpisodicMemoryManager(
            session=mock_session,
            recency_weight=0.5,
            importance_weight=0.3,
            similarity_weight=0.2,
        )
        # Weights should be stored as provided
        total = (
            manager.recency_weight
            + manager.importance_weight
            + manager.similarity_weight
        )
        assert abs(total - 1.0) < 0.01


# ============================================================================
# SemanticMemoryManager Tests
# ============================================================================


class TestSemanticMemoryManager:
    """Tests for SemanticMemoryManager."""

    def test_init(self, mock_session, mock_embedding_service):
        """Test manager initialization."""
        manager = SemanticMemoryManager(
            session=mock_session,
            embedding_service=mock_embedding_service,
            confidence_weight=0.3,
            similarity_weight=0.7,
        )
        assert manager.confidence_weight == 0.3
        assert manager.similarity_weight == 0.7

    def test_apply_confidence_decay(self, mock_session):
        """Test confidence decay calculation."""
        manager = SemanticMemoryManager(
            session=mock_session,
            confidence_decay_rate=0.1,  # 10% per day
        )

        # Create mock memory
        memory = MagicMock()
        memory.confidence = 1.0
        memory.updated_at = datetime.utcnow() - timedelta(days=7)
        memory.created_at = datetime.utcnow() - timedelta(days=10)

        decayed = manager._apply_confidence_decay(memory)

        # After 7 days at 10% decay per day: 1.0 * 0.9^7 ≈ 0.478
        assert 0.4 < decayed < 0.6

    def test_confidence_decay_no_decay(self, mock_session):
        """Test confidence decay with zero time passed."""
        manager = SemanticMemoryManager(
            session=mock_session,
            confidence_decay_rate=0.1,
        )

        memory = MagicMock()
        memory.confidence = 0.8
        memory.updated_at = datetime.utcnow()
        memory.created_at = datetime.utcnow()

        decayed = manager._apply_confidence_decay(memory)

        # Should be approximately the original confidence
        assert abs(decayed - 0.8) < 0.01


# ============================================================================
# ProceduralMemoryManager Tests
# ============================================================================


class TestProceduralMemoryManager:
    """Tests for ProceduralMemoryManager."""

    def test_init(self, mock_session, mock_embedding_service):
        """Test manager initialization."""
        manager = ProceduralMemoryManager(
            session=mock_session,
            embedding_service=mock_embedding_service,
            similarity_weight=0.5,
            success_weight=0.3,
            recency_weight=0.2,
        )
        assert manager.similarity_weight == 0.5
        assert manager.success_weight == 0.3
        assert manager.recency_weight == 0.2


# ============================================================================
# UnifiedMemoryManager Tests
# ============================================================================


class TestUnifiedMemoryManager:
    """Tests for UnifiedMemoryManager."""

    def test_init(self, mock_session, mock_embedding_service, mock_rerank_service):
        """Test manager initialization."""
        manager = UnifiedMemoryManager(
            session=mock_session,
            embedding_service=mock_embedding_service,
            rerank_service=mock_rerank_service,
            episodic_weight=0.3,
            semantic_weight=0.4,
            procedural_weight=0.3,
        )
        assert manager.episodic_weight == 0.3
        assert manager.semantic_weight == 0.4
        assert manager.procedural_weight == 0.3

    def test_submanagers_created(self, mock_session, mock_embedding_service):
        """Test that sub-managers are created."""
        manager = UnifiedMemoryManager(
            session=mock_session,
            embedding_service=mock_embedding_service,
        )
        assert manager.episodic is not None
        assert manager.semantic is not None
        assert manager.procedural is not None

    def test_rrf_default_k(self, mock_session):
        """Test default RRF k value."""
        manager = UnifiedMemoryManager(session=mock_session)
        assert manager.rrf_k == 60

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_session, mock_embedding_service):
        """Test getting memory statistics."""
        manager = UnifiedMemoryManager(
            session=mock_session,
            embedding_service=mock_embedding_service,
        )

        # Mock the count methods
        manager.episodic.count = AsyncMock(return_value=10)
        manager.semantic.count = AsyncMock(return_value=20)
        manager.procedural.count = AsyncMock(return_value=5)

        stats = await manager.get_stats()

        assert stats["episodic"]["count"] == 10
        assert stats["semantic"]["count"] == 20
        assert stats["procedural"]["count"] == 5
        assert stats["total"] == 35

    @pytest.mark.asyncio
    async def test_close(self, mock_session, mock_embedding_service, mock_rerank_service):
        """Test closing resources."""
        manager = UnifiedMemoryManager(
            session=mock_session,
            embedding_service=mock_embedding_service,
            rerank_service=mock_rerank_service,
        )

        await manager.close()

        mock_embedding_service.close.assert_called()

    @pytest.mark.asyncio
    async def test_clear_all_requires_confirm(self, mock_session):
        """Test that clear_all requires confirmation."""
        manager = UnifiedMemoryManager(session=mock_session)

        with pytest.raises(ValueError, match="Must set confirm=True"):
            await manager.clear_all(confirm=False)


# ============================================================================
# Integration Tests (require database)
# ============================================================================


@pytest.mark.skipif(
    True,  # Skip by default
    reason="Requires database connection",
)
class TestMemoryIntegration:
    """Integration tests requiring actual database."""

    @pytest.mark.asyncio
    async def test_episodic_record_and_search(self, db_session):
        """Test recording and searching episodic memory."""
        manager = EpisodicMemoryManager(session=db_session)

        # Record an event
        execution_id = uuid4()
        memory = await manager.record_event(
            execution_id=execution_id,
            sequence_num=1,
            event_type="task_start",
            description="Started processing search request",
            importance_score=0.8,
        )

        assert memory is not None
        assert memory.event_type == "task_start"

        # Search for it
        results = await manager.search(
            query="search request",
            limit=5,
        )

        assert len(results) > 0

        await manager.close()

    @pytest.mark.asyncio
    async def test_semantic_store_and_search(self, db_session):
        """Test storing and searching semantic memory."""
        manager = SemanticMemoryManager(session=db_session)

        # Store a fact
        memory = await manager.store_fact(
            fact="Python uses indentation for code blocks",
            fact_type="rule",
            category="programming",
            confidence=0.95,
        )

        assert memory is not None
        assert memory.fact_type == "rule"

        # Search for it
        results = await manager.search(
            query="Python syntax rules",
            limit=5,
        )

        assert len(results) > 0

        await manager.close()

    @pytest.mark.asyncio
    async def test_unified_search(self, db_session):
        """Test unified search across memory types."""
        manager = UnifiedMemoryManager(session=db_session)

        # Store some data first
        await manager.semantic.store_fact(
            fact="FastAPI uses async handlers",
            fact_type="pattern",
            category="web",
        )

        # Search across all types
        results = await manager.search(
            query="FastAPI async patterns",
            limit=10,
            rerank=False,
        )

        assert isinstance(results, UnifiedSearchResult)

        await manager.close()
