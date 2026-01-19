"""Question-answering with citations and confidence scoring."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum

from knowledge.ai import generate_answer
from knowledge.config import get_settings
from knowledge.reranker import RankedResult, rerank_results
from knowledge.search import hybrid_search


class ConfidenceLevel(Enum):
    """Confidence level for answers."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Citation:
    """A citation to a source."""

    index: int
    title: str
    content_type: str
    url: str | None = None
    chunk_text: str | None = None


@dataclass
class QAResult:
    """Result of a Q&A query."""

    query: str
    answer: str
    confidence: ConfidenceLevel
    confidence_score: float
    citations: list[Citation] = field(default_factory=list)
    warning: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        """Check if Q&A was successful."""
        return self.error is None and bool(self.answer)


def calculate_confidence(
    results: list[RankedResult],
    top_n: int = 3,
) -> tuple[ConfidenceLevel, float]:
    """
    Calculate confidence based on search/rerank scores.

    Formula: confidence = (top_score * 0.6) + (avg_top3_score * 0.4)

    Args:
        results: Reranked search results
        top_n: Number of top results to consider

    Returns:
        Tuple of (ConfidenceLevel, raw_score)
    """
    if not results:
        return ConfidenceLevel.LOW, 0.0

    # Get scores from top results
    top_scores = [r.rerank_score for r in results[:top_n]]

    if not top_scores:
        return ConfidenceLevel.LOW, 0.0

    # Calculate weighted confidence
    top_score = top_scores[0]
    avg_score = sum(top_scores) / len(top_scores)
    confidence_score = (top_score * 0.6) + (avg_score * 0.4)

    # Determine confidence level
    # Note: These thresholds are tuned for cosine similarity scores (0-1)
    if confidence_score < 0.3:
        level = ConfidenceLevel.LOW
    elif confidence_score < 0.7:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.HIGH

    return level, confidence_score


def build_citations(
    results: list[RankedResult],
    max_citations: int = 5,
) -> list[Citation]:
    """
    Build citation list from search results.

    Args:
        results: Reranked search results
        max_citations: Maximum number of citations

    Returns:
        List of Citation objects
    """
    citations = []
    for i, ranked in enumerate(results[:max_citations], 1):
        result = ranked.result
        citations.append(
            Citation(
                index=i,
                title=result.title,
                content_type=result.content_type,
                chunk_text=result.chunk_text,
            )
        )
    return citations


async def ask(
    query: str,
    limit: int = 10,
    rerank_top_k: int = 5,
    min_confidence: float = 0.0,
) -> QAResult:
    """
    Answer a question using the knowledge base.

    Pipeline:
    1. Hybrid search for relevant content
    2. Rerank results
    3. Calculate confidence
    4. Generate answer with citations (if confidence sufficient)

    Args:
        query: User's question
        limit: Number of search results to retrieve
        rerank_top_k: Number of results to use after reranking
        min_confidence: Minimum confidence to generate answer (0-1)

    Returns:
        QAResult with answer, confidence, and citations
    """
    try:
        # Step 1: Hybrid search
        search_results = await hybrid_search(query, limit=limit)

        if not search_results:
            return QAResult(
                query=query,
                answer="",
                confidence=ConfidenceLevel.LOW,
                confidence_score=0.0,
                error="No relevant content found in knowledge base.",
            )

        # Step 2: Rerank results
        ranked_results = await rerank_results(query, search_results, top_k=rerank_top_k)

        if not ranked_results:
            return QAResult(
                query=query,
                answer="",
                confidence=ConfidenceLevel.LOW,
                confidence_score=0.0,
                error="Reranking failed.",
            )

        # Step 3: Calculate confidence
        confidence_level, confidence_score = calculate_confidence(ranked_results)

        # Build citations
        citations = build_citations(ranked_results)

        # Check minimum confidence threshold
        warning = None
        if confidence_score < min_confidence:
            return QAResult(
                query=query,
                answer="",
                confidence=confidence_level,
                confidence_score=confidence_score,
                citations=citations,
                warning=f"Confidence too low ({confidence_score:.2f} < {min_confidence}). "
                "The knowledge base may not contain relevant information for this query.",
            )

        # Add warning for low confidence
        if confidence_level == ConfidenceLevel.LOW:
            warning = (
                "Low confidence answer. The knowledge base may not contain "
                "sufficient information for this query."
            )

        # Step 4: Generate answer with timeout protection
        context = [
            {
                "title": r.result.title,
                "text": r.result.chunk_text or "",
                "source": r.result.source_ref or "",
            }
            for r in ranked_results
        ]

        settings = get_settings()
        try:
            ai_response = await asyncio.wait_for(
                generate_answer(query, context),
                timeout=settings.llm_timeout,
            )
        except TimeoutError:
            # Return partial result with citations but no AI answer
            return QAResult(
                query=query,
                answer="",
                confidence=confidence_level,
                confidence_score=confidence_score,
                citations=citations,
                warning="LLM generation timed out. Results shown without synthesized answer.",
                error=f"LLM timeout after {settings.llm_timeout}s",
            )

        if not ai_response.success:
            return QAResult(
                query=query,
                answer="",
                confidence=confidence_level,
                confidence_score=confidence_score,
                citations=citations,
                error=f"Failed to generate answer: {ai_response.error}",
            )

        return QAResult(
            query=query,
            answer=ai_response.content,
            confidence=confidence_level,
            confidence_score=confidence_score,
            citations=citations,
            warning=warning,
        )

    except Exception as e:
        return QAResult(
            query=query,
            answer="",
            confidence=ConfidenceLevel.LOW,
            confidence_score=0.0,
            error=f"Q&A failed: {str(e)}",
        )


async def search_and_summarize(
    query: str,
    limit: int = 5,
) -> QAResult:
    """
    Search and summarize results without generating a direct answer.

    Useful for exploratory queries where the user wants to see
    what's in the knowledge base rather than a synthesized answer.

    Args:
        query: Search query
        limit: Number of results to return

    Returns:
        QAResult with summary of findings
    """
    try:
        # Search
        search_results = await hybrid_search(query, limit=limit)

        if not search_results:
            return QAResult(
                query=query,
                answer="No relevant content found.",
                confidence=ConfidenceLevel.LOW,
                confidence_score=0.0,
            )

        # Rerank
        ranked_results = await rerank_results(query, search_results, top_k=limit)
        confidence_level, confidence_score = calculate_confidence(ranked_results)
        citations = build_citations(ranked_results)

        # Build summary without AI
        summary_parts = [f"Found {len(ranked_results)} relevant items:\n"]
        for i, ranked in enumerate(ranked_results, 1):
            result = ranked.result
            summary_parts.append(
                f"[{i}] **{result.title}** ({result.content_type})\n"
                f"    Score: {ranked.rerank_score:.3f}"
            )
            if result.chunk_text:
                preview = result.chunk_text[:200].replace("\n", " ")
                if len(result.chunk_text) > 200:
                    preview += "..."
                summary_parts.append(f"    Preview: {preview}")
            summary_parts.append("")

        return QAResult(
            query=query,
            answer="\n".join(summary_parts),
            confidence=confidence_level,
            confidence_score=confidence_score,
            citations=citations,
        )

    except Exception as e:
        return QAResult(
            query=query,
            answer="",
            confidence=ConfidenceLevel.LOW,
            confidence_score=0.0,
            error=f"Search failed: {str(e)}",
        )
