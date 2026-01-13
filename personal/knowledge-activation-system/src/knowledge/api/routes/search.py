"""Search and Q&A routes.

Provides search functionality with:
- Hybrid search (BM25 + vector)
- AI-powered Q&A with citations
- Search result summarization
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from knowledge.api.schemas import (
    AskRequest,
    AskResponse,
    CitationItem,
    ConfidenceLevel,
    SearchMode,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from knowledge.qa import ask as qa_ask
from knowledge.qa import search_and_summarize
from knowledge.search import (
    hybrid_search_with_status,
    search_bm25_only,
    search_vector_only,
)
from knowledge.security import sanitize_error_message, is_production

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Search the knowledge base.

    Supports hybrid (BM25 + vector), BM25-only, or vector-only search modes.

    When hybrid search is used, the system will gracefully degrade to BM25-only
    if the embedding service (Ollama) is unavailable. Check the 'degraded' and
    'search_mode' fields in the response to see if degradation occurred.
    """
    try:
        degraded = False
        search_mode = request.mode.value
        warnings: list[str] = []

        if request.mode == SearchMode.HYBRID:
            response = await hybrid_search_with_status(request.query, limit=request.limit)
            results = response.results
            degraded = response.degraded
            search_mode = response.search_mode
            warnings = response.warnings
        elif request.mode == SearchMode.BM25:
            results = await search_bm25_only(request.query, limit=request.limit)
            search_mode = "bm25_only"
        else:
            results = await search_vector_only(request.query, limit=request.limit)
            search_mode = "vector_only"

        return SearchResponse(
            query=request.query,
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
                for r in results
            ],
            total=len(results),
            mode=request.mode.value,
            degraded=degraded,
            search_mode=search_mode,
            warnings=warnings,
        )
    except Exception as e:
        logger.exception(f"Search failed for: {request.query[:50]}...")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    """
    Ask a question and get an AI-generated answer with citations.

    Uses hybrid search, reranking, and LLM generation to provide
    answers based on your knowledge base.
    """
    try:
        result = await qa_ask(request.query, limit=request.limit)

        return AskResponse(
            query=result.query,
            answer=result.answer,
            confidence=ConfidenceLevel(result.confidence.value),
            confidence_score=result.confidence_score,
            citations=[
                CitationItem(
                    index=c.index,
                    title=c.title,
                    content_type=c.content_type,
                    chunk_text=c.chunk_text,
                )
                for c in result.citations
            ],
            warning=result.warning,
            error=result.error,
        )
    except Exception as e:
        logger.exception(f"Ask failed for: {request.query[:50]}...")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e


@router.post("/summarize", response_model=AskResponse)
async def summarize(request: AskRequest) -> AskResponse:
    """
    Search and summarize results without AI generation.

    Useful for exploring what's in the knowledge base.
    """
    try:
        result = await search_and_summarize(request.query, limit=request.limit)

        return AskResponse(
            query=result.query,
            answer=result.answer,
            confidence=ConfidenceLevel(result.confidence.value),
            confidence_score=result.confidence_score,
            citations=[
                CitationItem(
                    index=c.index,
                    title=c.title,
                    content_type=c.content_type,
                    chunk_text=c.chunk_text,
                )
                for c in result.citations
            ],
            warning=result.warning,
            error=result.error,
        )
    except Exception as e:
        logger.exception(f"Summarize failed for: {request.query[:50]}...")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e
