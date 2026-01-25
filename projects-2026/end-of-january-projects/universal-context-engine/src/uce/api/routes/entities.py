"""
Entity management API endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
import asyncpg

from ...models.entity import Entity
from ...entity_resolution.resolver import EntityResolver
from ..deps import get_entity_resolver, get_db

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("")
async def list_entities(
    entity_type: str | None = Query(None, description="Filter by entity type"),
    min_mentions: int = Query(1, description="Minimum mention count"),
    limit: int = Query(50, le=200),
    db: asyncpg.Pool = Depends(get_db),
) -> list[Entity]:
    """List entities with optional filtering."""
    async with db.acquire() as conn:
        params: list = [min_mentions, limit]
        type_filter = ""
        if entity_type:
            type_filter = "AND entity_type = $3"
            params.append(entity_type)

        rows = await conn.fetch(
            f"""
            SELECT * FROM entities
            WHERE mention_count >= $1
            {type_filter}
            ORDER BY mention_count DESC
            LIMIT $2
            """,
            *params,
        )

    return [_row_to_entity(row) for row in rows]


@router.get("/search")
async def search_entities(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, le=100),
    resolver: EntityResolver = Depends(get_entity_resolver),
) -> list[Entity]:
    """Search entities by name or alias."""
    return await resolver.search_entities(q, limit=limit)


@router.get("/active")
async def get_active_entities(
    hours: int = Query(24, le=168),
    limit: int = Query(20, le=100),
    db: asyncpg.Pool = Depends(get_db),
) -> list[dict]:
    """Get entities active in recent context."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT unnest(entities) as entity, count(*) as mention_count
            FROM context_items
            WHERE t_valid >= NOW() - INTERVAL '1 hour' * $1
              AND t_expired IS NULL
            GROUP BY entity
            ORDER BY mention_count DESC
            LIMIT $2
            """,
            hours,
            limit,
        )

    return [{"entity": r["entity"], "mentions": r["mention_count"]} for r in rows]


@router.get("/{entity_id}")
async def get_entity(
    entity_id: UUID,
    resolver: EntityResolver = Depends(get_entity_resolver),
) -> Entity:
    """Get entity by ID."""
    entity = await resolver.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/{entity_id}/related")
async def get_related_entities(
    entity_id: UUID,
    limit: int = Query(10, le=50),
    resolver: EntityResolver = Depends(get_entity_resolver),
) -> list[dict]:
    """Get entities related by co-occurrence."""
    related = await resolver.get_related_entities(entity_id, limit=limit)
    return [
        {"entity": e.model_dump(), "cooccurrence_count": count}
        for e, count in related
    ]


@router.get("/by-name/{name}")
async def get_entity_by_name(
    name: str,
    resolver: EntityResolver = Depends(get_entity_resolver),
) -> Entity:
    """Get entity by name (resolves aliases)."""
    entity = await resolver.get_entity_by_name(name)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


def _row_to_entity(row: asyncpg.Record) -> Entity:
    """Convert database row to Entity."""
    return Entity(
        id=row["id"],
        canonical_name=row["canonical_name"],
        display_name=row["display_name"],
        entity_type=row["entity_type"],
        aliases=row["aliases"] or [],
        description=row["description"],
        metadata=row["metadata"] or {},
        mention_count=row["mention_count"],
        last_seen_at=row["last_seen_at"],
        first_seen_at=row["first_seen_at"],
    )
