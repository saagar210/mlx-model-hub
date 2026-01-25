"""RAG query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from knowledge_engine.api.deps import get_engine
from knowledge_engine.core.engine import KnowledgeEngine
from knowledge_engine.models.query import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(
    query_request: QueryRequest,
    request: Request,
    engine: KnowledgeEngine = Depends(get_engine),
) -> QueryResponse:
    """
    Perform RAG query with confidence scoring and citations.

    The query pipeline:
    1. Hybrid search for relevant context
    2. Build context from top results
    3. Generate answer with Claude
    4. Calculate confidence based on retrieval scores
    5. Extract and return citations
    """
    return await engine.query(query_request)


@router.post("/query/stream")
async def query_stream(
    query_request: QueryRequest,
    request: Request,
    engine: KnowledgeEngine = Depends(get_engine),
) -> StreamingResponse:
    """
    Stream RAG query response.

    Returns Server-Sent Events with answer tokens as they're generated.
    """
    query_request.stream = True

    # TODO: Implement streaming response
    async def generate():
        response = await engine.query(query_request)
        yield f"data: {response.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.post("/query/simple")
async def simple_query(
    question: str,
    namespace: str = "default",
    request: Request = None,
    engine: KnowledgeEngine = Depends(get_engine),
) -> QueryResponse:
    """
    Simple query endpoint for quick questions.

    Uses default settings for RAG query.
    """
    query_request = QueryRequest(
        question=question,
        namespace=namespace,
        include_citations=True,
    )
    return await engine.query(query_request)
