"""Memory API routes."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sia.crud import EpisodicMemoryCRUD, SemanticMemoryCRUD
from sia.db import get_db
from sia.schemas.memory import (
    EpisodicMemoryCreate,
    EpisodicMemoryRead,
    SemanticMemoryCreate,
    SemanticMemoryRead,
    SemanticMemoryUpdate,
    UnifiedMemorySearch,
    UnifiedMemorySearchResponse,
    MemorySearchResult,
)

router = APIRouter()


# ============================================================================
# Episodic Memory
# ============================================================================


@router.get("/episodic")
async def list_episodic_memories(
    execution_id: UUID | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    min_importance: float | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List episodic memories with optional filters."""
    crud = EpisodicMemoryCRUD(db)

    if execution_id:
        memories = await crud.list_by_execution(execution_id)
    else:
        memories = await crud.list(
            event_type=event_type,
            since=since,
            min_importance=min_importance,
            skip=(page - 1) * page_size,
            limit=page_size,
        )

    return {
        "items": [EpisodicMemoryRead.model_validate(m) for m in memories],
        "count": len(memories),
    }


@router.post("/episodic", response_model=EpisodicMemoryRead, status_code=201)
async def create_episodic_memory(
    data: EpisodicMemoryCreate,
    db: AsyncSession = Depends(get_db),
) -> EpisodicMemoryRead:
    """Create a new episodic memory entry."""
    crud = EpisodicMemoryCRUD(db)
    memory = await crud.create(data)
    return EpisodicMemoryRead.model_validate(memory)


@router.get("/episodic/{memory_id}", response_model=EpisodicMemoryRead)
async def get_episodic_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EpisodicMemoryRead:
    """Get an episodic memory by ID."""
    crud = EpisodicMemoryCRUD(db)
    memory = await crud.get(memory_id)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return EpisodicMemoryRead.model_validate(memory)


# ============================================================================
# Semantic Memory
# ============================================================================


@router.get("/semantic")
async def list_semantic_memories(
    fact_type: str | None = None,
    category: str | None = None,
    min_confidence: float | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List semantic memories with optional filters."""
    crud = SemanticMemoryCRUD(db)

    memories = await crud.list(
        fact_type=fact_type,
        category=category,
        min_confidence=min_confidence,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total = await crud.count()

    return {
        "items": [SemanticMemoryRead.model_validate(m) for m in memories],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/semantic", response_model=SemanticMemoryRead, status_code=201)
async def create_semantic_memory(
    data: SemanticMemoryCreate,
    db: AsyncSession = Depends(get_db),
) -> SemanticMemoryRead:
    """Create a new semantic memory entry."""
    crud = SemanticMemoryCRUD(db)
    memory = await crud.create(data)
    return SemanticMemoryRead.model_validate(memory)


@router.get("/semantic/{memory_id}", response_model=SemanticMemoryRead)
async def get_semantic_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SemanticMemoryRead:
    """Get a semantic memory by ID."""
    crud = SemanticMemoryCRUD(db)
    memory = await crud.get(memory_id)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return SemanticMemoryRead.model_validate(memory)


@router.patch("/semantic/{memory_id}", response_model=SemanticMemoryRead)
async def update_semantic_memory(
    memory_id: UUID,
    data: SemanticMemoryUpdate,
    db: AsyncSession = Depends(get_db),
) -> SemanticMemoryRead:
    """Update a semantic memory."""
    crud = SemanticMemoryCRUD(db)
    memory = await crud.update(memory_id, data)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return SemanticMemoryRead.model_validate(memory)


@router.delete("/semantic/{memory_id}", status_code=204)
async def delete_semantic_memory(
    memory_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft delete a semantic memory."""
    crud = SemanticMemoryCRUD(db)
    memory = await crud.soft_delete(memory_id)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")


@router.post("/semantic/{memory_id}/reinforce")
async def reinforce_semantic_memory(
    memory_id: UUID,
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Reinforce a semantic memory with supporting evidence."""
    crud = SemanticMemoryCRUD(db)
    memory = await crud.reinforce(memory_id, execution_id)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return SemanticMemoryRead.model_validate(memory)


# ============================================================================
# Unified Search
# ============================================================================


@router.post("/search", response_model=UnifiedMemorySearchResponse)
async def search_memory(
    data: UnifiedMemorySearch,
    db: AsyncSession = Depends(get_db),
) -> UnifiedMemorySearchResponse:
    """Search across all memory types."""
    from sia.llm import EmbeddingService

    # Generate query embedding
    embedding_service = EmbeddingService()
    try:
        result = await embedding_service.embed(data.query)
        query_embedding = result.embedding
    finally:
        await embedding_service.close()

    all_results: list[MemorySearchResult] = []

    # Search episodic memory
    if "episodic" in data.memory_types:
        episodic_crud = EpisodicMemoryCRUD(db)
        episodic_results = await episodic_crud.search_by_embedding(
            query_embedding,
            limit=data.limit_per_type,
        )
        for memory, distance in episodic_results:
            all_results.append(MemorySearchResult(
                memory_type="episodic",
                id=memory.id,
                content=memory.description,
                relevance_score=1 - distance,
                metadata={
                    "event_type": memory.event_type,
                    "timestamp": memory.timestamp.isoformat(),
                    "importance": memory.importance_score,
                },
            ))

    # Search semantic memory
    if "semantic" in data.memory_types:
        semantic_crud = SemanticMemoryCRUD(db)
        semantic_results = await semantic_crud.search_by_embedding(
            query_embedding,
            limit=data.limit_per_type,
        )
        for memory, distance in semantic_results:
            all_results.append(MemorySearchResult(
                memory_type="semantic",
                id=memory.id,
                content=memory.fact,
                relevance_score=1 - distance,
                metadata={
                    "fact_type": memory.fact_type,
                    "confidence": memory.confidence,
                    "category": memory.category,
                },
            ))

    # Search procedural memory (skills)
    if "procedural" in data.memory_types:
        from sia.crud import SkillCRUD
        skill_crud = SkillCRUD(db)
        skill_results = await skill_crud.search_by_embedding(
            query_embedding,
            limit=data.limit_per_type,
        )
        for skill, distance in skill_results:
            all_results.append(MemorySearchResult(
                memory_type="procedural",
                id=skill.id,
                content=f"{skill.name}: {skill.description}",
                relevance_score=1 - distance,
                metadata={
                    "category": skill.category,
                    "success_rate": skill.success_rate,
                    "usage_count": skill.usage_count,
                },
            ))

    # Sort by relevance
    all_results.sort(key=lambda x: x.relevance_score, reverse=True)

    # Optionally rerank (placeholder - actual reranking in Phase 4)
    reranked = data.rerank and len(all_results) > 0

    return UnifiedMemorySearchResponse(
        query=data.query,
        results=all_results,
        total_results=len(all_results),
        reranked=reranked,
    )
