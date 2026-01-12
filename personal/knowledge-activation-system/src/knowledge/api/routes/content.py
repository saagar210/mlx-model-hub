"""Content routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from knowledge.api.schemas import (
    ContentDetailResponse,
    ContentItem,
    ContentListResponse,
)
from knowledge.db import get_db

router = APIRouter(prefix="/content", tags=["content"])


@router.get("", response_model=ContentListResponse)
async def list_content(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    content_type: str | None = Query(None, description="Filter by content type"),
) -> ContentListResponse:
    """
    List all content items with pagination.

    Optionally filter by content type (youtube, bookmark, file, note).
    """
    try:
        db = await get_db()

        # Get content with pagination
        offset = (page - 1) * page_size

        async with db.acquire() as conn:
            # Build query based on filter
            if content_type:
                rows = await conn.fetch(
                    """
                    SELECT id, filepath, type, title, summary, tags, created_at, updated_at
                    FROM content
                    WHERE deleted_at IS NULL AND type = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    content_type,
                    page_size,
                    offset,
                )
                count_row = await conn.fetchrow(
                    "SELECT COUNT(*) FROM content WHERE deleted_at IS NULL AND type = $1",
                    content_type,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT id, filepath, type, title, summary, tags, created_at, updated_at
                    FROM content
                    WHERE deleted_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT $1 OFFSET $2
                    """,
                    page_size,
                    offset,
                )
                count_row = await conn.fetchrow(
                    "SELECT COUNT(*) FROM content WHERE deleted_at IS NULL"
                )

        total = count_row["count"] if count_row else 0

        return ContentListResponse(
            items=[
                ContentItem(
                    id=row["id"],
                    filepath=row["filepath"],
                    content_type=row["type"],
                    title=row["title"],
                    summary=row["summary"],
                    tags=row["tags"] or [],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{content_id}", response_model=ContentDetailResponse)
async def get_content(content_id: UUID) -> ContentDetailResponse:
    """
    Get detailed information about a specific content item.
    """
    try:
        db = await get_db()
        content = await db.get_content_by_id(content_id)

        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        # Get chunk count
        async with db.acquire() as conn:
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) FROM chunks WHERE content_id = $1",
                content_id,
            )

        chunk_count = count_row["count"] if count_row else 0

        return ContentDetailResponse(
            id=content.id,
            filepath=content.filepath,
            content_type=content.type,
            title=content.title,
            summary=content.summary,
            tags=content.tags or [],
            metadata=content.metadata or {},
            created_at=content.created_at,
            updated_at=content.updated_at,
            chunk_count=chunk_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{content_id}")
async def delete_content(content_id: UUID) -> dict:
    """
    Soft delete a content item.

    The content is marked as deleted but not removed from the database.
    """
    try:
        db = await get_db()

        # Check if exists
        content = await db.get_content_by_id(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        # Soft delete
        async with db.acquire() as conn:
            await conn.execute(
                "UPDATE content SET deleted_at = NOW() WHERE id = $1",
                content_id,
            )

        return {"status": "deleted", "id": str(content_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
