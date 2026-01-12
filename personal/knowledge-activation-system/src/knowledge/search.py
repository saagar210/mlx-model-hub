"""Hybrid search with RRF fusion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from knowledge.config import Settings, get_settings
from knowledge.db import Database, get_db
from knowledge.embeddings import embed_text


@dataclass
class SearchResult:
    """Search result with RRF score."""

    content_id: UUID
    title: str
    content_type: str
    score: float
    chunk_text: str | None = None
    source_ref: str | None = None

    # Source tracking for debugging
    bm25_rank: int | None = None
    vector_rank: int | None = None


def rrf_fusion(
    bm25_results: list[tuple[UUID, str, str, float]],
    vector_results: list[tuple[UUID, str, str, str | None, float]],
    k: int = 60,
) -> list[SearchResult]:
    """
    Reciprocal Rank Fusion to combine BM25 and vector search results.

    RRF Score = Σ (1 / (k + rank))

    Args:
        bm25_results: List of (content_id, title, type, bm25_rank)
        vector_results: List of (content_id, title, type, chunk_text, similarity)
        k: RRF constant (default 60) to prevent division by small numbers

    Returns:
        List of SearchResult sorted by combined RRF score
    """
    # Track scores and metadata by content_id
    scores: dict[UUID, float] = {}
    metadata: dict[UUID, dict[str, Any]] = {}

    # Process BM25 results (1-indexed rank)
    for rank, (content_id, title, content_type, _bm25_score) in enumerate(bm25_results, start=1):
        rrf_score = 1.0 / (k + rank)
        scores[content_id] = scores.get(content_id, 0.0) + rrf_score

        if content_id not in metadata:
            metadata[content_id] = {
                "title": title,
                "content_type": content_type,
                "chunk_text": None,
                "bm25_rank": rank,
                "vector_rank": None,
            }
        else:
            metadata[content_id]["bm25_rank"] = rank

    # Process vector results (1-indexed rank)
    for rank, (content_id, title, content_type, chunk_text, _similarity) in enumerate(
        vector_results, start=1
    ):
        rrf_score = 1.0 / (k + rank)
        scores[content_id] = scores.get(content_id, 0.0) + rrf_score

        if content_id not in metadata:
            metadata[content_id] = {
                "title": title,
                "content_type": content_type,
                "chunk_text": chunk_text,
                "bm25_rank": None,
                "vector_rank": rank,
            }
        else:
            metadata[content_id]["vector_rank"] = rank
            # Prefer chunk_text from vector results
            if chunk_text:
                metadata[content_id]["chunk_text"] = chunk_text

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
                bm25_rank=meta["bm25_rank"],
                vector_rank=meta["vector_rank"],
            )
        )

    return results


async def hybrid_search(
    query: str,
    limit: int | None = None,
    settings: Settings | None = None,
    db: Database | None = None,
) -> list[SearchResult]:
    """
    Perform hybrid search combining BM25 and vector similarity.

    Args:
        query: Search query text
        limit: Number of results to return (default from settings)
        settings: Optional settings override
        db: Optional database instance override

    Returns:
        List of SearchResult sorted by RRF score
    """
    settings = settings or get_settings()
    db = db or await get_db()
    limit = limit or settings.search_limit

    # Generate query embedding
    query_embedding = await embed_text(query)

    # Run BM25 and vector search in parallel
    bm25_results = await db.bm25_search(query, limit=settings.bm25_candidates)
    vector_results = await db.vector_search(query_embedding, limit=settings.vector_candidates)

    # Combine with RRF
    combined = rrf_fusion(bm25_results, vector_results, k=settings.rrf_k)

    # Return top N
    return combined[:limit]


async def search_bm25_only(
    query: str,
    limit: int | None = None,
    settings: Settings | None = None,
    db: Database | None = None,
) -> list[SearchResult]:
    """
    Perform BM25-only search (for comparison/debugging).

    Args:
        query: Search query text
        limit: Number of results to return
        settings: Optional settings override
        db: Optional database instance override

    Returns:
        List of SearchResult sorted by BM25 rank
    """
    settings = settings or get_settings()
    db = db or await get_db()
    limit = limit or settings.search_limit

    bm25_results = await db.bm25_search(query, limit=limit)

    return [
        SearchResult(
            content_id=content_id,
            title=title,
            content_type=content_type,
            score=bm25_rank,
            bm25_rank=rank,
        )
        for rank, (content_id, title, content_type, bm25_rank) in enumerate(bm25_results, start=1)
    ]


async def search_vector_only(
    query: str,
    limit: int | None = None,
    settings: Settings | None = None,
    db: Database | None = None,
) -> list[SearchResult]:
    """
    Perform vector-only search (for comparison/debugging).

    Args:
        query: Search query text
        limit: Number of results to return
        settings: Optional settings override
        db: Optional database instance override

    Returns:
        List of SearchResult sorted by vector similarity
    """
    settings = settings or get_settings()
    db = db or await get_db()
    limit = limit or settings.search_limit

    query_embedding = await embed_text(query)
    vector_results = await db.vector_search(query_embedding, limit=limit)

    return [
        SearchResult(
            content_id=content_id,
            title=title,
            content_type=content_type,
            score=similarity,
            chunk_text=chunk_text,
            vector_rank=rank,
        )
        for rank, (content_id, title, content_type, chunk_text, similarity) in enumerate(
            vector_results, start=1
        )
    ]
