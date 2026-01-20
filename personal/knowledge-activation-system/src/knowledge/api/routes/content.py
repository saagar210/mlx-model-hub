"""Content routes.

Provides CRUD operations for content items in the knowledge base.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from knowledge.api.auth import require_scope
from knowledge.api.schemas import (
    ContentDetailResponse,
    ContentItem,
    ContentListResponse,
)
from knowledge.api.utils import handle_exceptions
from knowledge.autotag import extract_tags, suggest_tags
from knowledge.db import get_db

router = APIRouter(prefix="/content", tags=["content"])


@router.get("", response_model=ContentListResponse, dependencies=[Depends(require_scope("read"))])
@handle_exceptions("list_content")
async def list_content(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    content_type: str | None = Query(None, description="Filter by content type"),
) -> ContentListResponse:
    """
    List all content items with pagination.

    Optionally filter by content type (youtube, bookmark, file, note).
    """
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


@router.get("/{content_id}", response_model=ContentDetailResponse, dependencies=[Depends(require_scope("read"))])
@handle_exceptions("get_content")
async def get_content(content_id: UUID) -> ContentDetailResponse:
    """
    Get detailed information about a specific content item.
    """
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


@router.delete("/{content_id}", dependencies=[Depends(require_scope("delete"))])
@handle_exceptions("delete_content")
async def delete_content(content_id: UUID) -> dict:
    """
    Soft delete a content item.

    The content is marked as deleted but not removed from the database.
    """
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


@router.post("/{content_id}/autotag", dependencies=[Depends(require_scope("write"))])
@handle_exceptions("autotag_content")
async def autotag_content(
    content_id: UUID,
    replace: bool = Query(False, description="Replace existing tags instead of appending"),
) -> dict:
    """
    Auto-generate tags for a content item using LLM.

    By default, appends new tags to existing ones. Set `replace=true` to replace all tags.
    """
    db = await get_db()

    # Get content
    content = await db.get_content_by_id(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Get content text from chunks
    chunks = await db.get_chunks_by_content_id(content_id)
    if not chunks:
        raise HTTPException(status_code=400, detail="Content has no chunks to analyze")

    # Combine chunk text (limit to first 5 chunks for efficiency)
    content_text = " ".join(chunk.chunk_text for chunk in chunks[:5])

    # Extract tags
    if replace:
        new_tags = await extract_tags(content.title, content_text)
    else:
        # Suggest tags that aren't already present
        new_tags = await suggest_tags(
            content.title,
            content_text,
            existing_tags=content.tags or [],
        )

    if not new_tags:
        return {
            "content_id": str(content_id),
            "message": "No new tags suggested",
            "tags": content.tags or [],
        }

    # Update tags in database
    if replace:
        final_tags = new_tags
    else:
        final_tags = list(dict.fromkeys((content.tags or []) + new_tags))

    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE content SET tags = $1, updated_at = NOW() WHERE id = $2",
            final_tags,
            content_id,
        )

    return {
        "content_id": str(content_id),
        "new_tags": new_tags,
        "all_tags": final_tags,
        "replaced": replace,
    }
