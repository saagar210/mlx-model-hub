"""
Context management API endpoints.
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
import asyncpg

from ...models.context_item import ContextItem, BiTemporalMetadata, RelevanceSignals
from ...models.search import RecentContextResponse, WorkingContextResponse
from ..deps import get_db

router = APIRouter(prefix="/context", tags=["context"])


@router.get("/recent", response_model=RecentContextResponse)
async def get_recent_context(
    hours: int = Query(24, le=168, description="How many hours back"),
    sources: list[str] | None = Query(None, description="Filter by sources"),
    limit: int = Query(50, le=200),
    db: asyncpg.Pool = Depends(get_db),
) -> RecentContextResponse:
    """Get recent context activity."""
    since = datetime.utcnow() - timedelta(hours=hours)

    async with db.acquire() as conn:
        params: list = [since, limit]
        source_filter = ""
        if sources:
            source_filter = "AND source = ANY($3)"
            params.append(sources)

        rows = await conn.fetch(
            f"""
            SELECT * FROM context_items
            WHERE t_valid >= $1
              AND t_expired IS NULL
              AND (expires_at IS NULL OR expires_at > NOW())
              {source_filter}
            ORDER BY t_valid DESC
            LIMIT $2
            """,
            *params,
        )

    items = [_row_to_item(row) for row in rows]

    # Count by source
    by_source: dict[str, int] = {}
    for item in items:
        by_source[item.source] = by_source.get(item.source, 0) + 1

    return RecentContextResponse(
        items=items,
        by_source=by_source,
        hours=hours,
    )


@router.get("/working", response_model=WorkingContextResponse)
async def get_working_context(
    db: asyncpg.Pool = Depends(get_db),
) -> WorkingContextResponse:
    """Get current working context."""
    async with db.acquire() as conn:
        # Recent git
        git_rows = await conn.fetch(
            """
            SELECT * FROM context_items
            WHERE source = 'git' AND t_valid >= NOW() - INTERVAL '4 hours'
              AND t_expired IS NULL
            ORDER BY t_valid DESC LIMIT 10
            """
        )

        # Browser tabs
        browser_rows = await conn.fetch(
            """
            SELECT * FROM context_items
            WHERE source = 'browser' AND t_expired IS NULL
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY t_valid DESC LIMIT 10
            """
        )

        # Recent documents
        doc_rows = await conn.fetch(
            """
            SELECT DISTINCT ON (source_id) * FROM context_items
            WHERE source = 'kas' AND t_valid >= NOW() - INTERVAL '24 hours'
              AND t_expired IS NULL
            ORDER BY source_id, t_valid DESC
            LIMIT 10
            """
        )

        # Active entities
        entity_rows = await conn.fetch(
            """
            SELECT unnest(entities) as entity
            FROM context_items
            WHERE t_valid >= NOW() - INTERVAL '24 hours'
              AND t_expired IS NULL
            GROUP BY entity
            ORDER BY count(*) DESC
            LIMIT 20
            """
        )

    return WorkingContextResponse(
        git_activity=[_row_to_item(r) for r in git_rows],
        browser_tabs=[_row_to_item(r) for r in browser_rows],
        recent_documents=[_row_to_item(r) for r in doc_rows],
        active_entities=[r["entity"] for r in entity_rows],
    )


@router.get("/{item_id}")
async def get_context_item(
    item_id: UUID,
    db: asyncpg.Pool = Depends(get_db),
) -> ContextItem:
    """Get a specific context item by ID."""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM context_items WHERE id = $1",
            item_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Context item not found")

    return _row_to_item(row)


@router.delete("/{item_id}")
async def expire_context_item(
    item_id: UUID,
    db: asyncpg.Pool = Depends(get_db),
) -> dict:
    """Expire a context item (soft delete)."""
    async with db.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE context_items
            SET t_expired = NOW()
            WHERE id = $1 AND t_expired IS NULL
            """,
            item_id,
        )

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Context item not found or already expired")

    return {"status": "expired", "id": str(item_id)}


def _row_to_item(row: asyncpg.Record) -> ContextItem:
    """Convert database row to ContextItem."""
    return ContextItem(
        id=row["id"],
        source=row["source"],
        source_id=row["source_id"],
        source_url=row["source_url"],
        content_type=row["content_type"],
        title=row["title"],
        content=row["content"],
        content_hash=row["content_hash"],
        temporal=BiTemporalMetadata(
            t_valid=row["t_valid"],
            t_invalid=row["t_invalid"],
            t_created=row["t_created"],
            t_expired=row["t_expired"],
        ),
        expires_at=row["expires_at"],
        entities=row["entities"] or [],
        entity_ids=[UUID(eid) for eid in (row["entity_ids"] or [])],
        tags=row["tags"] or [],
        namespace=row["namespace"],
        relevance=RelevanceSignals(**(row["relevance"] or {})),
        metadata=row["metadata"] or {},
    )
