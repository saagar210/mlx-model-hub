"""API routes for knowledge graph entities."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from knowledge.db import Database, get_db
from knowledge.entity_extraction import extract_entities
from knowledge.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/entities", tags=["entities"])


class EntityResponse(BaseModel):
    """Entity response model."""

    id: UUID
    name: str
    entity_type: str
    confidence: float


class RelationshipResponse(BaseModel):
    """Relationship response model."""

    id: UUID
    relation_type: str
    confidence: float
    from_name: str
    from_type: str
    to_name: str
    to_type: str


class EntityStatsResponse(BaseModel):
    """Entity statistics response."""

    entity_type: str
    count: int
    unique_names: int


class ConnectedEntityResponse(BaseModel):
    """Connected entity response."""

    name: str
    entity_type: str
    connection_count: int


class ExtractRequest(BaseModel):
    """Entity extraction request."""

    content_id: UUID


class ExtractResponse(BaseModel):
    """Entity extraction response."""

    success: bool
    entity_count: int
    relationship_count: int
    entities: list[EntityResponse]
    error: str | None = None


@router.get("/stats", response_model=list[EntityStatsResponse])
async def get_entity_stats(
    db: Database = Depends(get_db),
) -> list[dict]:
    """Get entity statistics by type."""
    return await db.get_entity_stats()


@router.get("/connected", response_model=list[ConnectedEntityResponse])
async def get_connected_entities(
    limit: int = 20,
    db: Database = Depends(get_db),
) -> list[dict]:
    """Get most connected entities."""
    return await db.get_connected_entities(limit=limit)


@router.get("/content/{content_id}", response_model=list[EntityResponse])
async def get_entities_by_content(
    content_id: UUID,
    db: Database = Depends(get_db),
) -> list[dict]:
    """Get all entities for a content item."""
    entities = await db.get_entities_by_content(content_id)
    return entities


@router.get("/{entity_id}/relationships", response_model=list[RelationshipResponse])
async def get_entity_relationships(
    entity_id: UUID,
    db: Database = Depends(get_db),
) -> list[dict]:
    """Get all relationships for an entity."""
    relationships = await db.get_relationships_by_entity(entity_id)
    return relationships


@router.post("/extract", response_model=ExtractResponse)
async def extract_entities_for_content(
    request: ExtractRequest,
    db: Database = Depends(get_db),
) -> ExtractResponse:
    """Extract entities from content and store in database.

    This will:
    1. Get the content by ID
    2. Run entity extraction using LLM
    3. Store entities and relationships in the database
    """
    # Get content
    content = await db.get_content_by_id(request.content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Get first chunk for content text
    chunks = await db.get_chunks_by_content_id(request.content_id)
    if not chunks:
        raise HTTPException(status_code=400, detail="Content has no chunks")

    # Combine chunk text for extraction
    full_text = " ".join(chunk.chunk_text for chunk in chunks[:5])  # First 5 chunks

    # Extract entities
    result = await extract_entities(
        title=content.title,
        content=full_text,
    )

    if not result.success:
        return ExtractResponse(
            success=False,
            entity_count=0,
            relationship_count=0,
            entities=[],
            error=result.error,
        )

    # Delete existing entities for this content (re-extraction)
    await db.delete_entities_by_content(request.content_id)

    # Insert entities
    entity_ids: dict[str, UUID] = {}
    stored_entities = []

    for entity in result.entities:
        entity_id = await db.insert_entity(
            content_id=request.content_id,
            name=entity.name,
            entity_type=entity.entity_type,
            confidence=entity.confidence,
        )
        entity_ids[entity.name.lower()] = entity_id
        stored_entities.append(
            EntityResponse(
                id=entity_id,
                name=entity.name,
                entity_type=entity.entity_type,
                confidence=entity.confidence,
            )
        )

    # Insert relationships (only if both entities exist)
    rel_count = 0
    for rel in result.relationships:
        from_id = entity_ids.get(rel.from_entity.lower())
        to_id = entity_ids.get(rel.to_entity.lower())
        if from_id and to_id:
            rel_id = await db.insert_relationship(
                from_entity_id=from_id,
                to_entity_id=to_id,
                relation_type=rel.relation_type,
                confidence=rel.confidence,
            )
            if rel_id:
                rel_count += 1

    logger.info(
        "entities_extracted",
        content_id=str(request.content_id),
        entity_count=len(stored_entities),
        relationship_count=rel_count,
    )

    return ExtractResponse(
        success=True,
        entity_count=len(stored_entities),
        relationship_count=rel_count,
        entities=stored_entities,
    )


class ContentByEntityResponse(BaseModel):
    """Content containing an entity."""

    content_id: UUID
    title: str
    content_type: str
    entity_count: int
    entities: list[EntityResponse]


class RelatedContentResponse(BaseModel):
    """Related content sharing entities."""

    content_id: UUID
    title: str
    content_type: str
    shared_entities: list[str]
    relevance_score: float


@router.get("/search/{name}")
async def search_entity_by_name(
    name: str,
    entity_type: str | None = None,
    db: Database = Depends(get_db),
) -> dict | None:
    """Search for an entity by name."""
    entity = await db.get_entity_by_name(name, entity_type)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/search", response_model=list[ContentByEntityResponse])
async def search_content_by_entity(
    name: str,
    limit: int = 10,
    db: Database = Depends(get_db),
) -> list[ContentByEntityResponse]:
    """Find all content containing a specific entity (by name).

    This searches for content where the entity name appears,
    returning content items with their associated entities.
    """
    results = await db.search_content_by_entity_name(name, limit=limit)
    return [
        ContentByEntityResponse(
            content_id=r["content_id"],
            title=r["title"],
            content_type=r["content_type"],
            entity_count=r["entity_count"],
            entities=[
                EntityResponse(
                    id=e["id"],
                    name=e["name"],
                    entity_type=e["entity_type"],
                    confidence=e["confidence"],
                )
                for e in r["entities"]
            ],
        )
        for r in results
    ]


@router.get("/{entity_id}/related-content", response_model=list[RelatedContentResponse])
async def get_related_content_by_entity(
    entity_id: UUID,
    limit: int = 10,
    db: Database = Depends(get_db),
) -> list[RelatedContentResponse]:
    """Find content that shares entities with the given entity's content.

    This finds other content items that have similar entities,
    useful for discovering related knowledge.
    """
    results = await db.get_related_content_by_entity(entity_id, limit=limit)
    return [
        RelatedContentResponse(
            content_id=r["content_id"],
            title=r["title"],
            content_type=r["content_type"],
            shared_entities=r["shared_entities"],
            relevance_score=r["relevance_score"],
        )
        for r in results
    ]


@router.delete("/content/{content_id}")
async def delete_entities_for_content(
    content_id: UUID,
    db: Database = Depends(get_db),
) -> dict:
    """Delete all entities for a content item."""
    count = await db.delete_entities_by_content(content_id)
    return {"deleted": count, "content_id": str(content_id)}
