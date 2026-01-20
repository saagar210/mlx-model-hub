"""iOS Shortcuts integration routes.

Simplified endpoints optimized for iOS Shortcuts app:
- Plain text responses for easy parsing
- Minimal parameters
- Fast execution
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from knowledge.api.utils import handle_exceptions
from knowledge.db import get_db
from knowledge.search import hybrid_search

router = APIRouter(prefix="/shortcuts", tags=["shortcuts"])


class ShortcutSearchResponse(BaseModel):
    """Simplified search response for Shortcuts."""

    text: str
    result_count: int
    top_title: str | None = None
    top_source: str | None = None


class ShortcutCaptureResponse(BaseModel):
    """Capture response for Shortcuts."""

    success: bool
    message: str
    content_id: str | None = None


class ShortcutStatsResponse(BaseModel):
    """Quick stats for Shortcuts."""

    documents: int
    chunks: int
    review_due: int


@router.get("/search", response_model=ShortcutSearchResponse)
@handle_exceptions("shortcut_search")
async def shortcut_search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(3, ge=1, le=10, description="Max results"),
) -> ShortcutSearchResponse:
    """
    Simplified search for iOS Shortcuts.

    Returns plain text summary of top results, optimized for
    text-to-speech or notification display.
    """
    results = await hybrid_search(q, limit=limit)

    if not results:
        return ShortcutSearchResponse(
            text="No results found.",
            result_count=0,
        )

    # Format results as readable text
    lines = []
    for i, r in enumerate(results, 1):
        title = r.title or "Untitled"
        snippet = (r.chunk_text[:150] + "...") if len(r.chunk_text) > 150 else r.chunk_text
        lines.append(f"{i}. {title}: {snippet}")

    text = "\n\n".join(lines)
    top_result = results[0]

    return ShortcutSearchResponse(
        text=text,
        result_count=len(results),
        top_title=top_result.title,
        top_source=top_result.source_ref,
    )


@router.post("/capture", response_model=ShortcutCaptureResponse)
@handle_exceptions("shortcut_capture")
async def shortcut_capture(
    text: str = Query(..., description="Text to capture"),
    title: str = Query(None, description="Optional title"),
    tags: str = Query(None, description="Comma-separated tags"),
) -> ShortcutCaptureResponse:
    """
    Quick capture from iOS Shortcuts.

    Captures text as a quick note in the knowledge base.
    """
    from datetime import datetime
    from uuid import uuid4

    import json
    from pgvector.asyncpg import register_vector

    db = await get_db()

    # Generate title if not provided
    if not title:
        title = f"Quick Capture {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    # Create content record
    content_id = uuid4()
    filepath = f"captures/{content_id}.md"

    # Create chunk with embedding
    from knowledge.embeddings import generate_embedding

    embedding = await generate_embedding(text)

    async with db.acquire() as conn:
        await register_vector(conn)

        await conn.execute(
            """
            INSERT INTO content (id, filepath, content_hash, type, title, tags, metadata, namespace)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
            """,
            content_id,
            filepath,
            f"shortcut-{content_id}",
            "capture",
            title,
            tag_list,
            json.dumps({"source": "ios_shortcut", "captured_at": datetime.now().isoformat()}),
            "quick-capture",
        )

        await conn.execute(
            """
            INSERT INTO chunks (id, content_id, chunk_index, chunk_text, embedding, embedding_model)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid4(),
            content_id,
            0,
            text,
            embedding,
            "nomic-embed-text",
        )

    return ShortcutCaptureResponse(
        success=True,
        message=f"Captured: {title}",
        content_id=str(content_id),
    )


@router.get("/stats", response_model=ShortcutStatsResponse)
@handle_exceptions("shortcut_stats")
async def shortcut_stats() -> ShortcutStatsResponse:
    """
    Quick stats for iOS Shortcuts.

    Returns document count, chunk count, and review items due.
    """
    db = await get_db()

    # Get counts using connection
    async with db.acquire() as conn:
        content_count = await conn.fetchval(
            "SELECT COUNT(*) FROM content WHERE deleted_at IS NULL"
        )
        chunk_count = await conn.fetchval("SELECT COUNT(*) FROM chunks")
        review_due = await conn.fetchval(
            "SELECT COUNT(*) FROM review_queue WHERE next_review <= NOW()"
        )

    return ShortcutStatsResponse(
        documents=content_count or 0,
        chunks=chunk_count or 0,
        review_due=review_due or 0,
    )


@router.get("/review-count")
@handle_exceptions("shortcut_review_count")
async def shortcut_review_count() -> dict:
    """Get count of items due for review."""
    db = await get_db()
    async with db.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM review_queue WHERE next_review <= NOW()"
        )
    return {"due": count or 0, "text": f"{count or 0} items due for review"}
