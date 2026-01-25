"""Memory management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from knowledge_engine.api.deps import get_engine
from knowledge_engine.core.engine import KnowledgeEngine
from knowledge_engine.models.memory import (
    Memory,
    MemoryCreate,
    MemoryRecallRequest,
    MemoryRecallResponse,
)

router = APIRouter()


@router.post("/memory/store", response_model=Memory)
async def store_memory(
    memory: MemoryCreate,
    request: Request,
    engine: KnowledgeEngine = Depends(get_engine),
) -> Memory:
    """
    Store a memory for later recall.

    Memories are:
    - Embedded with Voyage AI
    - Stored in Qdrant for vector search
    - Linked in Neo4j for graph traversal
    - Indexed in PostgreSQL for metadata queries
    """
    return await engine.store_memory(memory)


@router.post("/memory/recall", response_model=MemoryRecallResponse)
async def recall_memories(
    recall_request: MemoryRecallRequest,
    request: Request,
    engine: KnowledgeEngine = Depends(get_engine),
) -> MemoryRecallResponse:
    """
    Recall memories relevant to a query.

    Uses semantic search to find related memories,
    optionally including graph-connected memories.
    """
    import time

    start = time.time()
    memories = await engine.recall_memories(
        query=recall_request.query,
        namespace=recall_request.namespace,
        limit=recall_request.limit,
    )
    recall_time = (time.time() - start) * 1000

    return MemoryRecallResponse(
        query=recall_request.query,
        namespace=recall_request.namespace,
        memories=memories,
        total_found=len(memories),
        recall_time_ms=recall_time,
    )


@router.get("/memory/{memory_id}", response_model=Memory)
async def get_memory(
    memory_id: str,
    namespace: str = "default",
    request: Request = None,
    engine: KnowledgeEngine = Depends(get_engine),
) -> Memory:
    """Get a specific memory by ID."""
    from uuid import UUID

    from fastapi import HTTPException

    memory_data = await engine._postgres.get_memory(UUID(memory_id), namespace)
    if not memory_data:
        raise HTTPException(status_code=404, detail="Memory not found")

    return Memory(
        id=memory_data["id"],
        content=memory_data["content"],
        memory_type=memory_data["memory_type"],
        namespace=namespace,
        context=memory_data.get("context"),
        source=memory_data.get("source"),
        importance=memory_data["importance"],
        tags=memory_data.get("tags", []),
        metadata=memory_data.get("metadata", {}),
        created_at=memory_data["created_at"],
        updated_at=memory_data["updated_at"],
    )
