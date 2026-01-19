"""Tests for multi-hop reasoning module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from knowledge.ai import AIResponse
from knowledge.multihop import (
    MultiHopResult,
    decompose_query,
    multihop_search,
)
from knowledge.search import SearchResult


class TestDecomposeQuery:
    """Tests for decompose_query function."""

    @pytest.mark.asyncio
    async def test_decompose_success(self):
        """Test successful query decomposition."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="What is PostgreSQL?\nWhat is MySQL?\nHow do they compare?",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        sub_queries = await decompose_query(
            "What are the differences between PostgreSQL and MySQL for web applications?",
            ai=mock_ai,
        )

        assert len(sub_queries) == 3
        assert "PostgreSQL" in sub_queries[0]

    @pytest.mark.asyncio
    async def test_decompose_handles_numbered_list(self):
        """Test handling of numbered list in response."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="1. What is FastAPI?\n2. What is Flask?\n3. Performance comparison",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        sub_queries = await decompose_query("Compare FastAPI and Flask", ai=mock_ai)

        assert len(sub_queries) == 3
        # Numbers should be stripped
        assert not sub_queries[0].startswith("1.")

    @pytest.mark.asyncio
    async def test_decompose_handles_bullet_list(self):
        """Test handling of bullet list in response."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="- What is Docker?\n- What is Kubernetes?\n- Container orchestration",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        sub_queries = await decompose_query("Docker vs Kubernetes", ai=mock_ai)

        assert len(sub_queries) == 3
        assert not sub_queries[0].startswith("-")

    @pytest.mark.asyncio
    async def test_decompose_limits_to_three(self):
        """Test that decomposition is limited to 3 sub-queries."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="Query 1\nQuery 2\nQuery 3\nQuery 4\nQuery 5",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        sub_queries = await decompose_query("Complex question", ai=mock_ai)

        assert len(sub_queries) <= 3

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_error(self):
        """Test fallback to original query on AI error."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="",
                model="deepseek",
                error="API error",
            )
        )
        mock_ai.close = AsyncMock()

        original_query = "What are the differences?"

        # Also mock Ollama to fail so we test the full fallback
        with patch(
            "knowledge.multihop._decompose_with_ollama",
            new_callable=AsyncMock,
            return_value=None,
        ):
            sub_queries = await decompose_query(original_query, ai=mock_ai)

        assert sub_queries == [original_query]

    @pytest.mark.asyncio
    async def test_decompose_fallback_on_empty(self):
        """Test fallback when no sub-queries generated."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="\n\n",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        original_query = "What is this?"
        sub_queries = await decompose_query(original_query, ai=mock_ai)

        assert sub_queries == [original_query]

    @pytest.mark.asyncio
    async def test_decompose_filters_short_lines(self):
        """Test that short lines are filtered out."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="Yes\nWhat is PostgreSQL used for?\nNo",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        sub_queries = await decompose_query("Tell me about PostgreSQL", ai=mock_ai)

        # Only the longer query should be included
        assert len(sub_queries) == 1
        assert "PostgreSQL" in sub_queries[0]


class TestMultihopSearch:
    """Tests for multihop_search function."""

    @pytest.mark.asyncio
    async def test_multihop_combines_results(self):
        """Test that multi-hop search combines results from sub-queries."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="What is PostgreSQL?\nWhat is MySQL?",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        result1 = SearchResult(
            content_id=uuid4(),
            title="PostgreSQL Guide",
            content_type="document",
            score=0.9,
        )
        result2 = SearchResult(
            content_id=uuid4(),
            title="MySQL Tutorial",
            content_type="document",
            score=0.85,
        )

        with patch("knowledge.multihop.hybrid_search") as mock_search:
            mock_search.side_effect = [[result1], [result2]]

            result = await multihop_search(
                "PostgreSQL vs MySQL",
                limit=10,
                ai=mock_ai,
            )

        assert isinstance(result, MultiHopResult)
        assert len(result.results) == 2
        assert len(result.sub_queries) == 2

    @pytest.mark.asyncio
    async def test_multihop_deduplicates(self):
        """Test that multi-hop search deduplicates results."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="Query 1\nQuery 2",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        shared_id = uuid4()
        result1 = SearchResult(
            content_id=shared_id,  # Same ID
            title="Shared Result",
            content_type="document",
            score=0.9,
        )
        result2 = SearchResult(
            content_id=shared_id,  # Same ID
            title="Shared Result",
            content_type="document",
            score=0.85,
        )
        result3 = SearchResult(
            content_id=uuid4(),
            title="Unique Result",
            content_type="document",
            score=0.8,
        )

        with patch("knowledge.multihop.hybrid_search") as mock_search:
            mock_search.side_effect = [[result1], [result2, result3]]

            result = await multihop_search(
                "Complex query",
                limit=10,
                ai=mock_ai,
            )

        # Should have 2 unique results (one deduplicated)
        assert len(result.results) == 2
        assert result.deduplicated is True

    @pytest.mark.asyncio
    async def test_multihop_respects_limit(self):
        """Test that multi-hop search respects limit."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="Query 1\nQuery 2",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        results = [
            SearchResult(content_id=uuid4(), title=f"Result {i}", content_type="document", score=0.9 - i * 0.1)
            for i in range(10)
        ]

        with patch("knowledge.multihop.hybrid_search") as mock_search:
            mock_search.side_effect = [results[:5], results[5:]]

            result = await multihop_search(
                "Complex query",
                limit=3,
                ai=mock_ai,
            )

        assert len(result.results) <= 3

    @pytest.mark.asyncio
    async def test_multihop_sorts_by_score(self):
        """Test that multi-hop results are sorted by score."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="Query 1\nQuery 2",
                model="deepseek",
            )
        )
        mock_ai.close = AsyncMock()

        low_score = SearchResult(
            content_id=uuid4(),
            title="Low Score",
            content_type="document",
            score=0.5,
        )
        high_score = SearchResult(
            content_id=uuid4(),
            title="High Score",
            content_type="document",
            score=0.95,
        )

        with patch("knowledge.multihop.hybrid_search") as mock_search:
            mock_search.side_effect = [[low_score], [high_score]]

            result = await multihop_search(
                "Complex query",
                limit=10,
                ai=mock_ai,
            )

        # High score should be first
        assert result.results[0].score > result.results[1].score


class TestMultiHopResult:
    """Tests for MultiHopResult dataclass."""

    def test_creation(self):
        """Test creating MultiHopResult."""
        result = MultiHopResult(
            query="Original query",
            sub_queries=["Sub 1", "Sub 2"],
            results=[],
            deduplicated=True,
        )

        assert result.query == "Original query"
        assert len(result.sub_queries) == 2
        assert result.deduplicated is True

    def test_default_deduplicated(self):
        """Test default value for deduplicated."""
        result = MultiHopResult(
            query="Query",
            sub_queries=[],
            results=[],
        )
        assert result.deduplicated is True
