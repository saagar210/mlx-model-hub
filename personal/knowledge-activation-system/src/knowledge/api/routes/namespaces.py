"""Namespace management routes.

Provides endpoints for managing content namespaces (organizational categories).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from knowledge.db import get_db
from knowledge.security import is_production, sanitize_error_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/namespaces", tags=["namespaces"])


class NamespaceInfo(BaseModel):
    """Information about a namespace."""

    name: str
    document_count: int
    chunk_count: int
    latest_update: str | None = None


class NamespaceListResponse(BaseModel):
    """Response for listing namespaces."""

    namespaces: list[NamespaceInfo]
    total: int


class NamespaceContentItem(BaseModel):
    """Content item within a namespace."""

    id: str
    title: str
    content_type: str
    created_at: str
    tags: list[str] = Field(default_factory=list)


class NamespaceContentResponse(BaseModel):
    """Response for namespace content listing."""

    namespace: str
    items: list[NamespaceContentItem]
    total: int
    page: int
    page_size: int


@router.get("", response_model=NamespaceListResponse)
async def list_namespaces() -> NamespaceListResponse:
    """
    List all namespaces with document and chunk counts.

    Returns namespaces extracted from content metadata, including:
    - namespace name
    - count of documents in that namespace
    - count of chunks in that namespace
    - date of most recent update
    """
    try:
        db = await get_db()

        async with db.acquire() as conn:
            # Query namespaces from metadata JSONB field
            rows = await conn.fetch(
                """
                SELECT
                    COALESCE(metadata->>'namespace', 'default') as namespace,
                    COUNT(DISTINCT c.id) as doc_count,
                    COUNT(ch.id) as chunk_count,
                    MAX(c.updated_at) as latest_update
                FROM content c
                LEFT JOIN chunks ch ON c.id = ch.content_id
                WHERE c.deleted_at IS NULL
                GROUP BY COALESCE(metadata->>'namespace', 'default')
                ORDER BY doc_count DESC
                """
            )

        namespaces = [
            NamespaceInfo(
                name=row["namespace"],
                document_count=row["doc_count"],
                chunk_count=row["chunk_count"],
                latest_update=row["latest_update"].isoformat() if row["latest_update"] else None,
            )
            for row in rows
        ]

        return NamespaceListResponse(
            namespaces=namespaces,
            total=len(namespaces),
        )

    except Exception as e:
        logger.exception("Failed to list namespaces")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e


@router.get("/content/{namespace:path}", response_model=NamespaceContentResponse)
async def get_namespace_content(
    namespace: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> NamespaceContentResponse:
    """
    Get content items within a specific namespace.

    Namespace can be hierarchical (e.g., "projects/voice-ai").
    Use URL encoding for slashes: "projects%2Fvoice-ai"
    """
    try:
        db = await get_db()
        offset = (page - 1) * page_size

        async with db.acquire() as conn:
            # Query content by namespace
            rows = await conn.fetch(
                """
                SELECT id, title, type, tags, created_at
                FROM content
                WHERE deleted_at IS NULL
                    AND COALESCE(metadata->>'namespace', 'default') = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                namespace,
                page_size,
                offset,
            )

            # Get total count
            count_row = await conn.fetchrow(
                """
                SELECT COUNT(*) FROM content
                WHERE deleted_at IS NULL
                    AND COALESCE(metadata->>'namespace', 'default') = $1
                """,
                namespace,
            )

        total = count_row["count"] if count_row else 0

        return NamespaceContentResponse(
            namespace=namespace,
            items=[
                NamespaceContentItem(
                    id=str(row["id"]),
                    title=row["title"],
                    content_type=row["type"],
                    created_at=row["created_at"].isoformat(),
                    tags=row["tags"] or [],
                )
                for row in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.exception(f"Failed to get namespace content: {namespace}")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e


@router.get("/stats/{namespace:path}")
async def get_namespace_stats(namespace: str) -> dict[str, Any]:
    """
    Get detailed statistics for a namespace.

    Includes content type breakdown and chunk statistics.
    """
    try:
        db = await get_db()

        async with db.acquire() as conn:
            # Get content stats by type
            type_rows = await conn.fetch(
                """
                SELECT type, COUNT(*) as count
                FROM content
                WHERE deleted_at IS NULL
                    AND COALESCE(metadata->>'namespace', 'default') = $1
                GROUP BY type
                """,
                namespace,
            )

            # Get chunk stats
            chunk_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_chunks,
                    AVG(LENGTH(chunk_text)) as avg_chunk_length
                FROM chunks ch
                JOIN content c ON ch.content_id = c.id
                WHERE c.deleted_at IS NULL
                    AND COALESCE(c.metadata->>'namespace', 'default') = $1
                """,
                namespace,
            )

            # Get recent activity
            recent_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as added_last_week
                FROM content
                WHERE deleted_at IS NULL
                    AND COALESCE(metadata->>'namespace', 'default') = $1
                    AND created_at > NOW() - INTERVAL '7 days'
                """,
                namespace,
            )

        return {
            "namespace": namespace,
            "content_by_type": {row["type"]: row["count"] for row in type_rows},
            "total_documents": sum(row["count"] for row in type_rows),
            "total_chunks": chunk_row["total_chunks"] if chunk_row else 0,
            "avg_chunk_length": round(chunk_row["avg_chunk_length"] or 0, 1) if chunk_row else 0,
            "added_last_week": recent_row["added_last_week"] if recent_row else 0,
        }

    except Exception as e:
        logger.exception(f"Failed to get namespace stats: {namespace}")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e
