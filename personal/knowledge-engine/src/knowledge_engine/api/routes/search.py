"""Search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from knowledge_engine.api.deps import get_engine
from knowledge_engine.core.engine import KnowledgeEngine
from knowledge_engine.models.search import (
    HybridSearchRequest,
    SearchResult,
)

router = APIRouter()


@router.post("/search", response_model=SearchResult)
async def hybrid_search(
    search_request: HybridSearchRequest,
    request: Request,
    engine: KnowledgeEngine = Depends(get_engine),
) -> SearchResult:
    """
    Perform hybrid search combining vector, graph, and BM25 ranking.

    The search pipeline:
    1. Generate query embedding with Voyage AI
    2. Vector search in Qdrant
    3. Graph traversal in Neo4j (optional)
    4. Combine results with Reciprocal Rank Fusion
    5. Rerank with Cohere (optional)
    """
    return await engine.search(search_request)


@router.post("/search/vector", response_model=SearchResult)
async def vector_search(
    search_request: HybridSearchRequest,
    request: Request,
    engine: KnowledgeEngine = Depends(get_engine),
) -> SearchResult:
    """
    Perform vector-only search.

    Useful for debugging or when graph traversal is not needed.
    """
    search_request.include_graph = False
    return await engine.search(search_request)


@router.post("/search/simple")
async def simple_search(
    query: str,
    namespace: str = "default",
    limit: int = 10,
    request: Request = None,
    engine: KnowledgeEngine = Depends(get_engine),
) -> SearchResult:
    """
    Simple search endpoint for quick queries.

    Uses default settings for hybrid search with reranking.
    """
    search_request = HybridSearchRequest(
        query=query,
        namespace=namespace,
        limit=limit,
        rerank=True,
        include_graph=True,
    )
    return await engine.search(search_request)
