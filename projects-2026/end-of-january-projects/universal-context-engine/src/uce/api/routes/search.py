"""
Search API endpoints.
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException

from ...models.search import SearchQuery, SearchResponse, SearchResult
from ...search.hybrid_search import HybridSearchEngine
from ..deps import get_search_engine

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_context(
    q: str = Query(..., description="Search query"),
    sources: list[str] | None = Query(None, description="Filter by sources (kas, git, browser)"),
    types: list[str] | None = Query(None, description="Filter by content types"),
    hours: int | None = Query(None, description="Only include items from last N hours"),
    entities: list[str] | None = Query(None, description="Filter by entity names"),
    namespace: str | None = Query(None, description="Filter by namespace"),
    limit: int = Query(20, le=100, description="Maximum results"),
    rerank: bool = Query(True, description="Apply reranking"),
    engine: HybridSearchEngine = Depends(get_search_engine),
) -> SearchResponse:
    """
    Hybrid search across all context sources.

    Combines vector similarity, BM25 full-text, and entity filtering
    using Reciprocal Rank Fusion (RRF).
    """
    query = SearchQuery(
        query=q,
        sources=sources,
        content_types=types,
        since=datetime.utcnow() - timedelta(hours=hours) if hours else None,
        entities=entities,
        namespace=namespace,
    )

    return await engine.search(query, limit=limit, rerank=rerank)


@router.get("/similar/{item_id}")
async def search_similar(
    item_id: UUID,
    limit: int = Query(10, le=50),
    engine: HybridSearchEngine = Depends(get_search_engine),
) -> list[SearchResult]:
    """Find items similar to a given item."""
    return await engine.search_similar(item_id, limit=limit)
