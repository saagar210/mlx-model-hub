"""Hybrid search with RRF fusion, caching, and query expansion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from knowledge.cache import CacheType, get_cache
from knowledge.config import Settings, get_settings
from knowledge.db import Database, get_db
from knowledge.embeddings import embed_text
from knowledge.exceptions import CircuitOpenError
from knowledge.logging import get_logger
from knowledge.query_expansion import ExpandedQuery, expand_query

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
    cached: bool = False  # Whether result was served from cache
    query_expanded: bool = False  # Whether query expansion was applied
    expanded_terms: list[str] = field(default_factory=list)  # Terms added by expansion


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
    use_cache: bool = True,
    use_expansion: bool = True,
    settings: Settings | None = None,
    db: Database | None = None,
) -> HybridSearchResponse:
    """
    Perform hybrid search with graceful degradation (P27).

    Falls back to BM25-only search if vector search fails (Ollama down, circuit open, etc.).
    Supports caching and query expansion for improved performance and recall.

    Args:
        query: Search query text
        limit: Number of results to return (default from settings)
        namespace: Optional namespace filter (exact match or prefix with *)
        min_score: Optional minimum score threshold
        quality_boost: Apply quality score boosting (default True)
        use_cache: Enable result caching (default True)
        use_expansion: Enable query expansion (default True)
        settings: Optional settings override
        db: Optional database instance override

    Returns:
        HybridSearchResponse with results and degradation status
    """
    settings = settings or get_settings()
    db = db or await get_db()
    limit = limit or settings.search_default_limit

    # Check cache first
    cache = await get_cache()
    cache_key = (query, limit, namespace, min_score, quality_boost)

    if use_cache and cache.is_connected:
        cached_result = await cache.get(CacheType.SEARCH, *cache_key)
        if cached_result:
            logger.debug("search_cache_hit", query=query[:50])
            # Reconstruct response from cache
            results = [
                SearchResult(
                    content_id=UUID(r["content_id"]),
                    title=r["title"],
                    content_type=r["content_type"],
                    score=r["score"],
                    chunk_text=r.get("chunk_text"),
                    namespace=r.get("namespace"),
                    vector_similarity=r.get("vector_similarity"),
                    bm25_score=r.get("bm25_score"),
                )
                for r in cached_result["results"]
            ]
            return HybridSearchResponse(
                results=results,
                degraded=cached_result.get("degraded", False),
                search_mode=cached_result.get("search_mode", "hybrid"),
                warnings=cached_result.get("warnings", []),
                cached=True,
                query_expanded=cached_result.get("query_expanded", False),
                expanded_terms=cached_result.get("expanded_terms", []),
            )

    # Apply query expansion
    expanded: ExpandedQuery | None = None
    search_query = query
    if use_expansion and settings.search_enable_query_expansion:
        expanded = await expand_query(query)
        if expanded.expansion_applied:
            search_query = expanded.expanded
            logger.debug(
                "query_expansion_applied",
                original=query[:50],
                terms_added=expanded.terms_added,
            )

    warnings: list[str] = []
    degraded = False
    search_mode = "hybrid"
    vector_results: list[tuple[UUID, str, str, str | None, str | None, float]] = []
    bm25_results: list[tuple[UUID, str, str, str | None, float]] = []

    # Run BM25 search and embedding generation in parallel for better performance
    # BM25 uses expanded query, vector uses original query
    async def run_bm25() -> list[tuple[UUID, str, str, str | None, float]]:
        return await db.bm25_search(search_query, limit=settings.bm25_candidates, namespace=namespace)

    async def run_embedding() -> list[float]:
        return await embed_text(query)

    # Execute in parallel
    bm25_task = asyncio.create_task(run_bm25())
    embedding_task = asyncio.create_task(run_embedding())

    # Gather BM25 results
    try:
        bm25_results = await bm25_task
    except Exception as e:
        logger.error(
            "bm25_search_failed",
            error=str(e),
            error_type=type(e).__name__,
            query=query[:50],
            query_length=len(query),
            namespace=namespace,
        )
        warnings.append(f"BM25 search failed: {type(e).__name__}: {str(e)[:100]}")

    # Gather embedding and run vector search
    try:
        query_embedding = await embedding_task
        vector_results = await db.vector_search(
            query_embedding, limit=settings.vector_candidates, namespace=namespace
        )
    except CircuitOpenError as e:
        logger.warning(
            "vector_search_skipped",
            reason="circuit_open",
            circuit=str(e),
            query=query[:50],
            query_length=len(query),
            namespace=namespace,
        )
        warnings.append("Semantic search unavailable: embedding service circuit open")
        degraded = True
        search_mode = "bm25_only"
    except Exception as e:
        logger.error(
            "vector_search_failed",
            error=str(e),
            error_type=type(e).__name__,
            query=query[:50],
            query_length=len(query),
            namespace=namespace,
            embedding_generated=len(locals().get('query_embedding', [])) > 0,
        )
        warnings.append(f"Semantic search failed: {type(e).__name__}: {str(e)[:100]}")
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

    # Build response
    response = HybridSearchResponse(
        results=combined[:limit],
        degraded=degraded,
        search_mode=search_mode,
        warnings=warnings,
        cached=False,
        query_expanded=expanded.expansion_applied if expanded else False,
        expanded_terms=expanded.terms_added if expanded else [],
    )

    # Cache the results
    if use_cache and cache.is_connected and response.results:
        cache_data = {
            "results": [
                {
                    "content_id": str(r.content_id),
                    "title": r.title,
                    "content_type": r.content_type,
                    "score": r.score,
                    "chunk_text": r.chunk_text,
                    "namespace": r.namespace,
                    "vector_similarity": r.vector_similarity,
                    "bm25_score": r.bm25_score,
                }
                for r in response.results
            ],
            "degraded": response.degraded,
            "search_mode": response.search_mode,
            "warnings": response.warnings,
            "query_expanded": response.query_expanded,
            "expanded_terms": response.expanded_terms,
        }
        await cache.set(CacheType.SEARCH, cache_data, *cache_key)
        logger.debug("search_cache_set", query=query[:50])

    return response


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
