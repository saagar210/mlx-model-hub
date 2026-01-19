"""Batch Operations API (P20: Bulk Operations Support).

Provides endpoints for performing multiple operations in a single request:
- Batch search (multiple queries)
- Batch content operations (create, delete)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from knowledge.api.auth import require_scope
from knowledge.api.schemas import SearchMode, SearchResponse, SearchResultItem
from knowledge.db import get_db
from knowledge.logging import get_logger
from knowledge.search import (
    hybrid_search_with_status,
    search_bm25_only,
    search_vector_only,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/batch", tags=["batch"])


# =============================================================================
# Schemas
# =============================================================================


class BatchSearchQuery(BaseModel):
    """Single search query in a batch."""

    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=10, ge=1, le=100)
    mode: SearchMode = SearchMode.HYBRID
    namespace: str | None = None


class BatchSearchRequest(BaseModel):
    """Batch search request."""

    queries: list[BatchSearchQuery] = Field(..., min_length=1, max_length=10)


class BatchSearchResponse(BaseModel):
    """Batch search response."""

    results: list[SearchResponse]
    total_queries: int
    succeeded: int
    failed: int
    errors: list[dict] = []


class BatchDeleteRequest(BaseModel):
    """Batch delete request."""

    ids: list[UUID] = Field(..., min_length=1, max_length=100)


class BatchDeleteResponse(BaseModel):
    """Batch delete response."""

    total: int
    deleted: int
    not_found: int
    errors: list[dict] = []


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/search", response_model=BatchSearchResponse, dependencies=[Depends(require_scope("read"))])
async def batch_search(request: BatchSearchRequest) -> BatchSearchResponse:
    """
    Execute multiple search queries in a single request.

    Maximum 10 queries per batch. Each query is executed independently,
    and results are returned in the same order as the queries.
    """
    results: list[SearchResponse] = []
    errors: list[dict] = []
    succeeded = 0

    for i, query in enumerate(request.queries):
        try:
            if query.mode == SearchMode.HYBRID:
                response = await hybrid_search_with_status(
                    query.query,
                    limit=query.limit,
                    namespace=query.namespace,
                )
                search_results = response.results
                degraded = response.degraded
                search_mode = response.search_mode
                warnings = response.warnings
            elif query.mode == SearchMode.BM25:
                search_results = await search_bm25_only(
                    query.query,
                    limit=query.limit,
                    namespace=query.namespace,
                )
                degraded = False
                search_mode = "bm25_only"
                warnings = []
            else:
                search_results = await search_vector_only(
                    query.query,
                    limit=query.limit,
                    namespace=query.namespace,
                )
                degraded = False
                search_mode = "vector_only"
                warnings = []

            results.append(
                SearchResponse(
                    query=query.query,
                    results=[
                        SearchResultItem(
                            content_id=r.content_id,
                            title=r.title,
                            content_type=r.content_type,
                            score=r.score,
                            chunk_text=r.chunk_text,
                            source_ref=r.source_ref,
                            bm25_rank=r.bm25_rank,
                            vector_rank=r.vector_rank,
                        )
                        for r in search_results
                    ],
                    total=len(search_results),
                    mode=query.mode.value,
                    degraded=degraded,
                    search_mode=search_mode,
                    warnings=warnings,
                )
            )
            succeeded += 1
        except Exception as e:
            logger.error("batch_search_query_failed", index=i, error=str(e))
            errors.append({"index": i, "query": query.query[:50], "error": str(e)})
            # Add empty result to maintain order
            results.append(
                SearchResponse(
                    query=query.query,
                    results=[],
                    total=0,
                    mode=query.mode.value,
                    degraded=True,
                    search_mode="error",
                    warnings=[f"Query failed: {str(e)[:100]}"],
                )
            )

    return BatchSearchResponse(
        results=results,
        total_queries=len(request.queries),
        succeeded=succeeded,
        failed=len(errors),
        errors=errors,
    )


@router.delete("/content", response_model=BatchDeleteResponse)
async def batch_delete_content(
    request: BatchDeleteRequest,
    _: bool = Depends(require_scope("write")),
) -> BatchDeleteResponse:
    """
    Delete multiple content items in a single request.

    Maximum 100 items per batch. Requires write scope.
    Items that don't exist are counted as not_found but don't cause errors.
    """
    db = await get_db()
    deleted = 0
    not_found = 0
    errors: list[dict] = []

    for content_id in request.ids:
        try:
            result = await db.soft_delete_content(content_id)
            if result:
                deleted += 1
            else:
                not_found += 1
        except Exception as e:
            logger.error("batch_delete_failed", content_id=str(content_id), error=str(e))
            errors.append({"id": str(content_id), "error": str(e)})

    logger.info(
        "batch_delete_completed",
        total=len(request.ids),
        deleted=deleted,
        not_found=not_found,
        errors=len(errors),
    )

    return BatchDeleteResponse(
        total=len(request.ids),
        deleted=deleted,
        not_found=not_found,
        errors=errors,
    )
