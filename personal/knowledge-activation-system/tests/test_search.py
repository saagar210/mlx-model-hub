"""Tests for search module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from knowledge.config import Settings
from knowledge.search import (
    SearchResult,
    hybrid_search,
    rrf_fusion,
    search_bm25_only,
    search_vector_only,
)


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_search_result_creation(self):
        """Test creating a search result."""
        result = SearchResult(
            content_id=uuid4(),
            title="Test Title",
            content_type="youtube",
            score=0.85,
            chunk_text="Some text",
            bm25_rank=1,
            vector_rank=2,
        )

        assert result.title == "Test Title"
        assert result.score == 0.85
        assert result.bm25_rank == 1
        assert result.vector_rank == 2

    def test_search_result_optional_fields(self):
        """Test search result with optional fields."""
        result = SearchResult(
            content_id=uuid4(),
            title="Test",
            content_type="note",
            score=0.5,
        )

        assert result.chunk_text is None
        assert result.source_ref is None
        assert result.bm25_rank is None
        assert result.vector_rank is None


class TestRRFFusion:
    """Tests for RRF fusion algorithm."""

    def test_rrf_fusion_combines_results(self):
        """Test that RRF properly combines BM25 and vector results."""
        # Common ID for overlapping result
        common_id = uuid4()
        bm25_only_id = uuid4()
        vector_only_id = uuid4()

        bm25_results = [
            (common_id, "Common Result", "youtube", 0.9),
            (bm25_only_id, "BM25 Only", "bookmark", 0.7),
        ]

        vector_results = [
            (common_id, "Common Result", "youtube", "Some chunk text", 0.95),
            (vector_only_id, "Vector Only", "note", "Different chunk", 0.8),
        ]

        results = rrf_fusion(bm25_results, vector_results, k=60)

        # Common result should be first (appears in both)
        assert results[0].content_id == common_id
        assert results[0].bm25_rank == 1
        assert results[0].vector_rank == 1
        assert results[0].chunk_text == "Some chunk text"

        # Should have 3 unique results
        assert len(results) == 3

    def test_rrf_fusion_empty_inputs(self):
        """Test RRF with empty inputs."""
        results = rrf_fusion([], [], k=60)
        assert results == []

    def test_rrf_fusion_bm25_only(self):
        """Test RRF with only BM25 results."""
        id1 = uuid4()
        bm25_results = [(id1, "Title", "youtube", 0.9)]

        results = rrf_fusion(bm25_results, [], k=60)

        assert len(results) == 1
        assert results[0].bm25_rank == 1
        assert results[0].vector_rank is None

    def test_rrf_fusion_vector_only(self):
        """Test RRF with only vector results."""
        id1 = uuid4()
        vector_results = [(id1, "Title", "note", "Chunk", 0.9)]

        results = rrf_fusion([], vector_results, k=60)

        assert len(results) == 1
        assert results[0].vector_rank == 1
        assert results[0].bm25_rank is None
        assert results[0].chunk_text == "Chunk"

    def test_rrf_fusion_score_calculation(self):
        """Test that RRF scores are calculated correctly."""
        id1 = uuid4()
        id2 = uuid4()

        # Both at rank 1 in their respective lists
        bm25_results = [(id1, "Title 1", "youtube", 0.9)]
        vector_results = [(id1, "Title 1", "youtube", "Chunk", 0.9)]

        results = rrf_fusion(bm25_results, vector_results, k=60)

        # Score should be 2 * 1/(60+1) = 2/61 ≈ 0.0328
        expected_score = 2 * (1 / 61)
        assert abs(results[0].score - expected_score) < 0.001

    def test_rrf_fusion_preserves_metadata(self):
        """Test that RRF preserves chunk text from vector results."""
        common_id = uuid4()

        bm25_results = [(common_id, "Title", "youtube", 0.9)]
        vector_results = [(common_id, "Title", "youtube", "Important chunk text", 0.9)]

        results = rrf_fusion(bm25_results, vector_results, k=60)

        assert results[0].chunk_text == "Important chunk text"

    def test_rrf_fusion_custom_k(self):
        """Test RRF with custom k value."""
        id1 = uuid4()
        bm25_results = [(id1, "Title", "youtube", 0.9)]
        vector_results = [(id1, "Title", "youtube", "Chunk", 0.9)]

        # With k=1, score should be higher
        results_k1 = rrf_fusion(bm25_results, vector_results, k=1)
        # With k=100, score should be lower
        results_k100 = rrf_fusion(bm25_results, vector_results, k=100)

        assert results_k1[0].score > results_k100[0].score


class TestHybridSearch:
    """Tests for hybrid search function."""

    @pytest.mark.asyncio
    async def test_hybrid_search_calls_both_searches(
        self,
        test_settings: Settings,
        mock_embedding: list[float],
        sample_bm25_results: list[tuple],
        sample_vector_results: list[tuple],
    ):
        """Test that hybrid search calls both BM25 and vector search."""
        with patch("knowledge.search.get_settings") as mock_get_settings, \
             patch("knowledge.search.get_db") as mock_get_db, \
             patch("knowledge.search.embed_text") as mock_embed:

            mock_get_settings.return_value = test_settings

            mock_db = AsyncMock()
            mock_db.bm25_search = AsyncMock(return_value=sample_bm25_results)
            mock_db.vector_search = AsyncMock(return_value=sample_vector_results)
            mock_get_db.return_value = mock_db

            mock_embed.return_value = mock_embedding

            results = await hybrid_search("machine learning")

            mock_db.bm25_search.assert_called_once()
            mock_db.vector_search.assert_called_once()
            mock_embed.assert_called_once_with("machine learning")

    @pytest.mark.asyncio
    async def test_hybrid_search_respects_limit(
        self,
        test_settings: Settings,
        mock_embedding: list[float],
    ):
        """Test that hybrid search respects the limit parameter."""
        # Create many results
        bm25_results = [(uuid4(), f"Title {i}", "youtube", 0.9 - i * 0.1) for i in range(10)]
        vector_results = [(uuid4(), f"Vector {i}", "note", "Chunk", 0.9 - i * 0.1) for i in range(10)]

        with patch("knowledge.search.get_settings") as mock_get_settings, \
             patch("knowledge.search.get_db") as mock_get_db, \
             patch("knowledge.search.embed_text") as mock_embed:

            mock_get_settings.return_value = test_settings

            mock_db = AsyncMock()
            mock_db.bm25_search = AsyncMock(return_value=bm25_results)
            mock_db.vector_search = AsyncMock(return_value=vector_results)
            mock_get_db.return_value = mock_db

            mock_embed.return_value = mock_embedding

            results = await hybrid_search("test", limit=5)

            assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_hybrid_search_empty_results(
        self,
        test_settings: Settings,
        mock_embedding: list[float],
    ):
        """Test hybrid search with no results."""
        with patch("knowledge.search.get_settings") as mock_get_settings, \
             patch("knowledge.search.get_db") as mock_get_db, \
             patch("knowledge.search.embed_text") as mock_embed:

            mock_get_settings.return_value = test_settings

            mock_db = AsyncMock()
            mock_db.bm25_search = AsyncMock(return_value=[])
            mock_db.vector_search = AsyncMock(return_value=[])
            mock_get_db.return_value = mock_db

            mock_embed.return_value = mock_embedding

            results = await hybrid_search("nonexistent query")

            assert results == []


class TestBM25OnlySearch:
    """Tests for BM25-only search."""

    @pytest.mark.asyncio
    async def test_bm25_only_search(
        self,
        test_settings: Settings,
        sample_bm25_results: list[tuple],
    ):
        """Test BM25-only search returns results."""
        with patch("knowledge.search.get_settings") as mock_get_settings, \
             patch("knowledge.search.get_db") as mock_get_db:

            mock_get_settings.return_value = test_settings

            mock_db = AsyncMock()
            mock_db.bm25_search = AsyncMock(return_value=sample_bm25_results)
            mock_get_db.return_value = mock_db

            results = await search_bm25_only("machine learning")

            assert len(results) == 3
            assert all(r.vector_rank is None for r in results)
            assert all(r.bm25_rank is not None for r in results)

    @pytest.mark.asyncio
    async def test_bm25_only_ranks_correctly(
        self,
        test_settings: Settings,
    ):
        """Test BM25-only search assigns correct ranks."""
        bm25_results = [
            (uuid4(), "First", "youtube", 0.9),
            (uuid4(), "Second", "bookmark", 0.8),
        ]

        with patch("knowledge.search.get_settings") as mock_get_settings, \
             patch("knowledge.search.get_db") as mock_get_db:

            mock_get_settings.return_value = test_settings

            mock_db = AsyncMock()
            mock_db.bm25_search = AsyncMock(return_value=bm25_results)
            mock_get_db.return_value = mock_db

            results = await search_bm25_only("test")

            assert results[0].bm25_rank == 1
            assert results[1].bm25_rank == 2


class TestVectorOnlySearch:
    """Tests for vector-only search."""

    @pytest.mark.asyncio
    async def test_vector_only_search(
        self,
        test_settings: Settings,
        mock_embedding: list[float],
        sample_vector_results: list[tuple],
    ):
        """Test vector-only search returns results."""
        with patch("knowledge.search.get_settings") as mock_get_settings, \
             patch("knowledge.search.get_db") as mock_get_db, \
             patch("knowledge.search.embed_text") as mock_embed:

            mock_get_settings.return_value = test_settings

            mock_db = AsyncMock()
            mock_db.vector_search = AsyncMock(return_value=sample_vector_results)
            mock_get_db.return_value = mock_db

            mock_embed.return_value = mock_embedding

            results = await search_vector_only("machine learning")

            assert len(results) == 3
            assert all(r.bm25_rank is None for r in results)
            assert all(r.vector_rank is not None for r in results)

    @pytest.mark.asyncio
    async def test_vector_only_preserves_chunk_text(
        self,
        test_settings: Settings,
        mock_embedding: list[float],
    ):
        """Test vector-only search preserves chunk text."""
        vector_results = [
            (uuid4(), "Title", "youtube", "Important chunk content", 0.9),
        ]

        with patch("knowledge.search.get_settings") as mock_get_settings, \
             patch("knowledge.search.get_db") as mock_get_db, \
             patch("knowledge.search.embed_text") as mock_embed:

            mock_get_settings.return_value = test_settings

            mock_db = AsyncMock()
            mock_db.vector_search = AsyncMock(return_value=vector_results)
            mock_get_db.return_value = mock_db

            mock_embed.return_value = mock_embedding

            results = await search_vector_only("test")

            assert results[0].chunk_text == "Important chunk content"


@pytest.mark.integration
class TestSearchIntegration:
    """Integration tests requiring actual services."""

    @pytest.mark.asyncio
    async def test_real_hybrid_search(self, test_settings: Settings):
        """Test hybrid search with real database and Ollama."""
        from knowledge.db import get_db, close_db
        from knowledge.embeddings import check_ollama_health, close_embedding_service

        try:
            # Check prerequisites
            ollama_status = await check_ollama_health()
            if not ollama_status.healthy:
                pytest.skip(f"Ollama not available: {ollama_status.error}")

            db = await get_db()
            health = await db.check_health()
            if health["status"] != "healthy":
                pytest.skip(f"Database not available: {health.get('error')}")

            # Run search - may return empty results in empty DB
            results = await hybrid_search("test query", settings=test_settings)

            # Just verify it doesn't crash and returns list
            assert isinstance(results, list)

        finally:
            await close_db()
            await close_embedding_service()
