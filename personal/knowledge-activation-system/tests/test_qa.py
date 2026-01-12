"""Tests for Q&A module."""

import pytest
from unittest.mock import AsyncMock, patch

from knowledge.qa import (
    QAResult,
    Citation,
    ConfidenceLevel,
    calculate_confidence,
    build_citations,
    ask,
    search_and_summarize,
)
from knowledge.rerank import RankedResult
from knowledge.search import SearchResult


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_confidence_levels(self):
        """Test all confidence levels exist."""
        assert ConfidenceLevel.LOW.value == "low"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.HIGH.value == "high"


class TestQAResult:
    """Tests for QAResult dataclass."""

    def test_successful_result(self):
        """Test successful Q&A result."""
        result = QAResult(
            query="What is X?",
            answer="X is Y.",
            confidence=ConfidenceLevel.HIGH,
            confidence_score=0.85,
        )
        assert result.success is True

    def test_failed_result_with_error(self):
        """Test failed Q&A result."""
        result = QAResult(
            query="What is X?",
            answer="",
            confidence=ConfidenceLevel.LOW,
            confidence_score=0.1,
            error="No results found",
        )
        assert result.success is False

    def test_result_with_citations(self):
        """Test result with citations."""
        citations = [
            Citation(index=1, title="Doc 1", content_type="note"),
            Citation(index=2, title="Doc 2", content_type="youtube"),
        ]
        result = QAResult(
            query="Test",
            answer="Answer",
            confidence=ConfidenceLevel.MEDIUM,
            confidence_score=0.5,
            citations=citations,
        )
        assert len(result.citations) == 2


class TestCitation:
    """Tests for Citation dataclass."""

    def test_citation_basic(self):
        """Test basic citation."""
        citation = Citation(index=1, title="Test", content_type="note")
        assert citation.index == 1
        assert citation.title == "Test"

    def test_citation_with_chunk_text(self):
        """Test citation with chunk text."""
        citation = Citation(
            index=1,
            title="Test",
            content_type="bookmark",
            chunk_text="Some content preview",
        )
        assert citation.chunk_text == "Some content preview"


class TestCalculateConfidence:
    """Tests for calculate_confidence function."""

    def test_empty_results(self):
        """Test with no results."""
        level, score = calculate_confidence([])
        assert level == ConfidenceLevel.LOW
        assert score == 0.0

    def test_high_confidence(self):
        """Test high confidence scores."""
        # Create mock ranked results with high scores
        results = [
            RankedResult(
                result=_mock_search_result(),
                rerank_score=0.9,
                original_rank=1,
            ),
            RankedResult(
                result=_mock_search_result(),
                rerank_score=0.85,
                original_rank=2,
            ),
            RankedResult(
                result=_mock_search_result(),
                rerank_score=0.8,
                original_rank=3,
            ),
        ]

        level, score = calculate_confidence(results)
        assert level == ConfidenceLevel.HIGH
        assert score >= 0.7

    def test_medium_confidence(self):
        """Test medium confidence scores."""
        results = [
            RankedResult(
                result=_mock_search_result(),
                rerank_score=0.6,
                original_rank=1,
            ),
            RankedResult(
                result=_mock_search_result(),
                rerank_score=0.5,
                original_rank=2,
            ),
        ]

        level, score = calculate_confidence(results)
        assert level == ConfidenceLevel.MEDIUM

    def test_low_confidence(self):
        """Test low confidence scores."""
        results = [
            RankedResult(
                result=_mock_search_result(),
                rerank_score=0.2,
                original_rank=1,
            ),
        ]

        level, score = calculate_confidence(results)
        assert level == ConfidenceLevel.LOW


class TestBuildCitations:
    """Tests for build_citations function."""

    def test_builds_citations(self):
        """Test citation building."""
        results = [
            RankedResult(
                result=_mock_search_result(title="Doc 1", content_type="note"),
                rerank_score=0.9,
                original_rank=1,
            ),
            RankedResult(
                result=_mock_search_result(title="Doc 2", content_type="youtube"),
                rerank_score=0.8,
                original_rank=2,
            ),
        ]

        citations = build_citations(results)

        assert len(citations) == 2
        assert citations[0].index == 1
        assert citations[0].title == "Doc 1"
        assert citations[1].title == "Doc 2"

    def test_respects_max_citations(self):
        """Test max citations limit."""
        results = [
            RankedResult(
                result=_mock_search_result(title=f"Doc {i}"),
                rerank_score=0.9 - i * 0.1,
                original_rank=i,
            )
            for i in range(10)
        ]

        citations = build_citations(results, max_citations=3)

        assert len(citations) == 3


class TestAsk:
    """Tests for ask function."""

    @pytest.mark.asyncio
    async def test_no_results_returns_error(self):
        """Test that no search results returns error."""
        with patch("knowledge.qa.hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            result = await ask("What is X?")

            assert result.success is False
            assert "No relevant content" in result.error

    @pytest.mark.asyncio
    async def test_successful_qa(self):
        """Test successful Q&A flow."""
        search_results = [_mock_search_result(title="Relevant Doc")]

        with patch("knowledge.qa.hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results

            with patch("knowledge.qa.rerank_results", new_callable=AsyncMock) as mock_rerank:
                mock_rerank.return_value = [
                    RankedResult(
                        result=search_results[0],
                        rerank_score=0.8,
                        original_rank=1,
                    )
                ]

                with patch("knowledge.qa.generate_answer", new_callable=AsyncMock) as mock_gen:
                    from knowledge.ai import AIResponse

                    mock_gen.return_value = AIResponse(
                        content="The answer is Y.", model="test"
                    )

                    result = await ask("What is X?")

                    assert result.success is True
                    assert result.answer == "The answer is Y."
                    assert len(result.citations) > 0

    @pytest.mark.asyncio
    async def test_low_confidence_warning(self):
        """Test that low confidence adds warning."""
        search_results = [_mock_search_result()]

        with patch("knowledge.qa.hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results

            with patch("knowledge.qa.rerank_results", new_callable=AsyncMock) as mock_rerank:
                mock_rerank.return_value = [
                    RankedResult(
                        result=search_results[0],
                        rerank_score=0.2,  # Low score
                        original_rank=1,
                    )
                ]

                with patch("knowledge.qa.generate_answer", new_callable=AsyncMock) as mock_gen:
                    from knowledge.ai import AIResponse

                    mock_gen.return_value = AIResponse(content="Answer", model="test")

                    result = await ask("What is X?")

                    assert result.warning is not None
                    assert "Low confidence" in result.warning


class TestSearchAndSummarize:
    """Tests for search_and_summarize function."""

    @pytest.mark.asyncio
    async def test_returns_summary_without_ai(self):
        """Test that search_and_summarize doesn't call AI."""
        search_results = [
            _mock_search_result(title="Doc 1", chunk_text="Content 1"),
            _mock_search_result(title="Doc 2", chunk_text="Content 2"),
        ]

        with patch("knowledge.qa.hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = search_results

            with patch("knowledge.qa.rerank_results", new_callable=AsyncMock) as mock_rerank:
                mock_rerank.return_value = [
                    RankedResult(result=r, rerank_score=0.8 - i * 0.1, original_rank=i + 1)
                    for i, r in enumerate(search_results)
                ]

                result = await search_and_summarize("query")

                assert result.success is True
                assert "Found 2" in result.answer
                assert "Doc 1" in result.answer

    @pytest.mark.asyncio
    async def test_no_results(self):
        """Test with no search results."""
        with patch("knowledge.qa.hybrid_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            result = await search_and_summarize("query")

            assert "No relevant content" in result.answer


# Helper functions


def _mock_search_result(
    title: str = "Test Doc",
    content_type: str = "note",
    chunk_text: str = "Test content",
) -> SearchResult:
    """Create a mock SearchResult for testing."""
    from uuid import uuid4

    return SearchResult(
        content_id=uuid4(),
        title=title,
        content_type=content_type,
        chunk_text=chunk_text,
        score=0.5,
        bm25_rank=1,
        vector_rank=1,
    )
