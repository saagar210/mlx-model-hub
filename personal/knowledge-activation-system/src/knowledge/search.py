"""Hybrid search with RRF fusion (P27: Graceful Degradation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from knowledge.config import Settings, get_settings
from knowledge.db import Database, get_db
from knowledge.embeddings import embed_text
from knowledge.exceptions import CircuitOpenError
from knowledge.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Search result with RRF score."""

    content_id: UUID
    title: str
    content_type: str
    score: float
    chunk_text: str | None = None
    source_ref: str | None = None
    namespace: str | None = None

    # Source tracking for debugging
    bm25_rank: int | None = None
    vector_rank: int | None = None

    # Quality indicators
    vector_similarity: float | None = None
    bm25_score: float | None = None


@dataclass
class HybridSearchResponse:
    """Response from hybrid search with degradation status (P27)."""

    results: list[SearchResult]
    degraded: bool = False
    search_mode: str = "hybrid"  # hybrid, bm25_only, vector_only
    warnings: list[str] = field(default_factory=list)


def rrf_fusion(
    bm25_results: list[tuple[UUID, str, str, str | None, float]],
    vector_results: list[tuple[UUID, str, str, str | None, str | None, float]],
    k: int = 60,
) -> list[SearchResult]:
    """
    Reciprocal Rank Fusion to combine BM25 and vector search results.

    RRF Score = Σ (1 / (k + rank))

    Args:
        bm25_results: List of (content_id, title, type, namespace, bm25_score)
        vector_results: List of (content_id, title, type, namespace, chunk_text, similarity)
        k: RRF constant (default 60) to prevent division by small numbers

    Returns:
        List of SearchResult sorted by combined RRF score
    """
    # Track scores and metadata by content_id
    scores: dict[UUID, float] = {}
    metadata: dict[UUID, dict[str, Any]] = {}

    # Process BM25 results (1-indexed rank)
    for rank, (content_id, title, content_type, namespace, bm25_score) in enumerate(bm25_results, start=1):
        rrf_score = 1.0 / (k + rank)
        scores[content_id] = scores.get(content_id, 0.0) + rrf_score

        if content_id not in metadata:
            metadata[content_id] = {
                "title": title,
                "content_type": content_type,
                "namespace": namespace,
                "chunk_text": None,
                "bm25_rank": rank,
                "bm25_score": bm25_score,
                "vector_rank": None,
                "vector_similarity": None,
            }
        else:
            metadata[content_id]["bm25_rank"] = rank
            metadata[content_id]["bm25_score"] = bm25_score
            if namespace and not metadata[content_id].get("namespace"):
                metadata[content_id]["namespace"] = namespace

    # Process vector results (1-indexed rank)
    for rank, (content_id, title, content_type, namespace, chunk_text, similarity) in enumerate(
        vector_results, start=1
    ):
        rrf_score = 1.0 / (k + rank)
        scores[content_id] = scores.get(content_id, 0.0) + rrf_score

        if content_id not in metadata:
            metadata[content_id] = {
                "title": title,
                "content_type": content_type,
                "namespace": namespace,
                "chunk_text": chunk_text,
                "bm25_rank": None,
                "bm25_score": None,
                "vector_rank": rank,
                "vector_similarity": similarity,
            }
        else:
            metadata[content_id]["vector_rank"] = rank
            metadata[content_id]["vector_similarity"] = similarity
            # Prefer chunk_text from vector results
            if chunk_text:
                metadata[content_id]["chunk_text"] = chunk_text
            if namespace and not metadata[content_id].get("namespace"):
                metadata[content_id]["namespace"] = namespace

    # Sort by combined score descending
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    # Build results
    results = []
    for content_id in sorted_ids:
        meta = metadata[content_id]
        results.append(
            SearchResult(
                content_id=content_id,
                title=meta["title"],
                content_type=meta["content_type"],
                score=scores[content_id],
                chunk_text=meta["chunk_text"],
                namespace=meta["namespace"],
                bm25_rank=meta["bm25_rank"],
                vector_rank=meta["vector_rank"],
                vector_similarity=meta["vector_similarity"],
                bm25_score=meta["bm25_score"],
            )
        )

    return results


async def hybrid_search(
    query: str,
    limit: int | None = None,
    namespace: str | None = None,
    min_score: float | None = None,
    quality_boost: bool = True,
    settings: Settings | None = None,
    db: Database | None = None,
) -> list[SearchResult]:
    """
    Perform hybrid search combining BM25 and vector similarity.

    This is a convenience wrapper that returns just the results list.
    For full degradation status, use hybrid_search_with_status().

    Args:
        query: Search query text
        limit: Number of results to return (default from settings)
        namespace: Optional namespace filter (exact match or prefix with *)
        min_score: Optional minimum score threshold
        quality_boost: Apply quality score boosting (default True)
        settings: Optional settings override
        db: Optional database instance override

    Returns:
        List of SearchResult sorted by RRF score (with quality boost if enabled)
    """
    response = await hybrid_search_with_status(
        query=query,
        limit=limit,
        namespace=namespace,
        min_score=min_score,
        quality_boost=quality_boost,
        settings=settings,
        db=db,
    )
    return response.results


async def hybrid_search_with_status(
    query: str,
    limit: int | None = None,
    namespace: str | None = None,
    min_score: float | None = None,
    quality_boost: bool = True,
    settings: Settings | None = None,
    db: Database | None = None,
) -> HybridSearchResponse:
    """
    Perform hybrid search with graceful degradation (P27).

    Falls back to BM25-only search if vector search fails (Ollama down, circuit open, etc.).

    Args:
        query: Search query text
        limit: Number of results to return (default from settings)
        namespace: Optional namespace filter (exact match or prefix with *)
        min_score: Optional minimum score threshold
        quality_boost: Apply quality score boosting (default True)
        settings: Optional settings override
        db: Optional database instance override

    Returns:
        HybridSearchResponse with results and degradation status
    """
    settings = settings or get_settings()
    db = db or await get_db()
    limit = limit or settings.search_default_limit

    warnings: list[str] = []
    degraded = False
    search_mode = "hybrid"
    vector_results: list[tuple[UUID, str, str, str | None, str | None, float]] = []

    # BM25 search (always attempt - this is our fallback)
    bm25_results: list[tuple[UUID, str, str, str | None, float]] = []
    try:
        bm25_results = await db.bm25_search(query, limit=settings.bm25_candidates, namespace=namespace)
    except Exception as e:
        logger.error("bm25_search_failed", error=str(e), query=query[:50])
        warnings.append(f"BM25 search failed: {str(e)[:100]}")

    # Vector search (may fail if Ollama is down)
    try:
        query_embedding = await embed_text(query)
        vector_results = await db.vector_search(
            query_embedding, limit=settings.vector_candidates, namespace=namespace
        )
    except CircuitOpenError as e:
        logger.warning(
            "vector_search_skipped",
            reason="circuit_open",
            circuit=str(e),
            query=query[:50],
        )
        warnings.append("Semantic search unavailable: embedding service circuit open")
        degraded = True
        search_mode = "bm25_only"
    except Exception as e:
        logger.error("vector_search_failed", error=str(e), query=query[:50])
        warnings.append(f"Semantic search failed: {str(e)[:100]}")
        degraded = True
        search_mode = "bm25_only"

    # Combine results
    if vector_results:
        combined = rrf_fusion(bm25_results, vector_results, k=settings.rrf_k)
    else:
        # Fallback to BM25-only results
        combined = [
            SearchResult(
                content_id=content_id,
                title=title,
                content_type=content_type,
                score=bm25_score,
                namespace=ns,
                bm25_rank=rank,
                bm25_score=bm25_score,
            )
            for rank, (content_id, title, content_type, ns, bm25_score) in enumerate(
                bm25_results, start=1
            )
        ]

    # Apply quality boosting if enabled
    if quality_boost and combined:
        content_ids = [r.content_id for r in combined]
        try:
            quality_scores = await db.get_quality_scores(content_ids)

            # Apply quality boost (multiply score by quality factor)
            # Quality factor = 0.8 + 0.4 * quality_score (range 0.8 to 1.2)
            boosted = []
            for result in combined:
                quality = quality_scores.get(result.content_id, 0.5)
                quality_factor = 0.8 + 0.4 * quality
                boosted.append(
                    SearchResult(
                        content_id=result.content_id,
                        title=result.title,
                        content_type=result.content_type,
                        score=result.score * quality_factor,
                        chunk_text=result.chunk_text,
                        source_ref=result.source_ref,
                        namespace=result.namespace,
                        bm25_rank=result.bm25_rank,
                        vector_rank=result.vector_rank,
                        vector_similarity=result.vector_similarity,
                        bm25_score=result.bm25_score,
                    )
                )
            # Re-sort by boosted score
            combined = sorted(boosted, key=lambda x: x.score, reverse=True)
        except Exception as e:
            logger.warning("quality_boost_failed", error=str(e))
            # Continue without quality boost

    # Apply minimum score filter if specified
    if min_score is not None:
        combined = [r for r in combined if r.score >= min_score]

    # Return response with degradation info
    return HybridSearchResponse(
        results=combined[:limit],
        degraded=degraded,
        search_mode=search_mode,
        warnings=warnings,
    )


async def search_bm25_only(
    query: str,
    limit: int | None = None,
    namespace: str | None = None,
    settings: Settings | None = None,
    db: Database | None = None,
) -> list[SearchResult]:
    """
    Perform BM25-only search (for comparison/debugging).

    Args:
        query: Search query text
        limit: Number of results to return
        namespace: Optional namespace filter
        settings: Optional settings override
        db: Optional database instance override

    Returns:
        List of SearchResult sorted by BM25 rank
    """
    settings = settings or get_settings()
    db = db or await get_db()
    limit = limit or settings.search_default_limit

    bm25_results = await db.bm25_search(query, limit=limit, namespace=namespace)

    return [
        SearchResult(
            content_id=content_id,
            title=title,
            content_type=content_type,
            score=bm25_score,
            namespace=ns,
            bm25_rank=rank,
            bm25_score=bm25_score,
        )
        for rank, (content_id, title, content_type, ns, bm25_score) in enumerate(bm25_results, start=1)
    ]


async def search_vector_only(
    query: str,
    limit: int | None = None,
    namespace: str | None = None,
    settings: Settings | None = None,
    db: Database | None = None,
) -> list[SearchResult]:
    """
    Perform vector-only search (for comparison/debugging).

    Args:
        query: Search query text
        limit: Number of results to return
        namespace: Optional namespace filter
        settings: Optional settings override
        db: Optional database instance override

    Returns:
        List of SearchResult sorted by vector similarity
    """
    settings = settings or get_settings()
    db = db or await get_db()
    limit = limit or settings.search_default_limit

    query_embedding = await embed_text(query)
    vector_results = await db.vector_search(query_embedding, limit=limit, namespace=namespace)

    return [
        SearchResult(
            content_id=content_id,
            title=title,
            content_type=content_type,
            score=similarity,
            chunk_text=chunk_text,
            namespace=ns,
            vector_rank=rank,
            vector_similarity=similarity,
        )
        for rank, (content_id, title, content_type, ns, chunk_text, similarity) in enumerate(
            vector_results, start=1
        )
    ]
