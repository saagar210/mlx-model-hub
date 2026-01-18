"""Export/Import API (P21: Backup and Data Portability).

Provides endpoints for:
- Exporting knowledge base content (JSON, Markdown)
- Importing content from backups
- Streaming exports for large datasets
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from knowledge.api.auth import require_scope
from knowledge.db import get_db
from knowledge.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/export", tags=["export"])


# =============================================================================
# Schemas
# =============================================================================


class ExportFormat(str, Enum):
    """Supported export formats."""

    JSON = "json"
    JSONL = "jsonl"  # JSON Lines for streaming


class ExportRequest(BaseModel):
    """Export request configuration."""

    format: ExportFormat = ExportFormat.JSON
    namespace: str | None = Field(default=None, description="Filter by namespace")
    content_types: list[str] | None = Field(default=None, description="Filter by content types")
    include_chunks: bool = Field(default=True, description="Include text chunks")
    include_embeddings: bool = Field(default=False, description="Include embedding vectors")


class ExportMetadata(BaseModel):
    """Metadata included in exports."""

    exported_at: str
    version: str = "1.0"
    total_items: int
    namespace: str | None = None
    content_types: list[str] | None = None


class ImportResult(BaseModel):
    """Import operation result."""

    total: int
    imported: int
    skipped: int
    errors: list[dict] = []


class ContentExportItem(BaseModel):
    """Single content item for export."""

    id: str
    title: str
    content_type: str
    source_ref: str | None = None
    namespace: str
    tags: list[str] = []
    created_at: str
    updated_at: str
    chunks: list[dict] | None = None


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_class=StreamingResponse)
async def export_content(
    request: ExportRequest,
    _: bool = Depends(require_scope("read")),
) -> StreamingResponse:
    """
    Export knowledge base content.

    Supports JSON and JSONL (streaming) formats.
    Use JSONL for large exports to avoid memory issues.
    """
    db = await get_db()

    async def generate_json() -> AsyncIterator[bytes]:
        """Generate JSON export with all items in array."""
        items = []
        count = 0

        async for item in _export_items(db, request):
            items.append(item)
            count += 1

        export_data = {
            "metadata": ExportMetadata(
                exported_at=datetime.now(UTC).isoformat(),
                total_items=count,
                namespace=request.namespace,
                content_types=request.content_types,
            ).model_dump(),
            "items": items,
        }

        yield json.dumps(export_data, indent=2, default=str).encode("utf-8")

    async def generate_jsonl() -> AsyncIterator[bytes]:
        """Generate JSONL export (one item per line)."""
        count = 0

        # First line is metadata (will update count at end via separate request)
        metadata = ExportMetadata(
            exported_at=datetime.now(UTC).isoformat(),
            total_items=0,  # Will be actual count in footer
            namespace=request.namespace,
            content_types=request.content_types,
        )
        yield (json.dumps({"type": "metadata", "data": metadata.model_dump()}, default=str) + "\n").encode("utf-8")

        # Stream items
        async for item in _export_items(db, request):
            yield (json.dumps({"type": "item", "data": item}, default=str) + "\n").encode("utf-8")
            count += 1

        # Footer with actual count
        yield (json.dumps({"type": "footer", "total_items": count}) + "\n").encode("utf-8")

    if request.format == ExportFormat.JSONL:
        generator = generate_jsonl()
        media_type = "application/x-ndjson"
        filename = f"kas-export-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.jsonl"
    else:
        generator = generate_json()
        media_type = "application/json"
        filename = f"kas-export-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.json"

    logger.info(
        "export_started",
        format=request.format.value,
        namespace=request.namespace,
        include_chunks=request.include_chunks,
    )

    return StreamingResponse(
        generator,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=ImportResult)
async def import_content(
    file: UploadFile = File(...),  # noqa: B008
    skip_existing: bool = True,
    _: bool = Depends(require_scope("write")),  # noqa: B008
) -> ImportResult:
    """
    Import content from a backup file.

    Supports JSON and JSONL formats.
    Set skip_existing=false to update existing items.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    is_jsonl = file.filename.endswith(".jsonl")
    db = await get_db()

    total = 0
    imported = 0
    skipped = 0
    errors: list[dict] = []

    try:
        content = await file.read()
        content_str = content.decode("utf-8")

        if is_jsonl:
            items = _parse_jsonl(content_str)
        else:
            data = json.loads(content_str)
            items = data.get("items", [])

        for item in items:
            total += 1
            try:
                result = await _import_item(db, item, skip_existing)
                if result == "imported":
                    imported += 1
                elif result == "skipped":
                    skipped += 1
            except Exception as e:
                errors.append({
                    "item_id": item.get("id", "unknown"),
                    "error": str(e)[:200],
                })

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)[:100]}") from e
    except Exception as e:
        logger.error("import_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)[:100]}") from e

    logger.info(
        "import_completed",
        total=total,
        imported=imported,
        skipped=skipped,
        errors=len(errors),
    )

    return ImportResult(
        total=total,
        imported=imported,
        skipped=skipped,
        errors=errors,
    )


# =============================================================================
# Helper Functions
# =============================================================================


async def _export_items(db: Any, request: ExportRequest) -> AsyncIterator[dict]:
    """Generate export items from database."""
    # Get content with optional filters
    query = """
        SELECT
            c.id, c.title, c.content_type, c.source_ref, c.namespace,
            c.tags, c.created_at, c.updated_at
        FROM content c
        WHERE 1=1
    """
    params: list = []
    param_idx = 1

    if request.namespace:
        query += f" AND c.namespace = ${param_idx}"
        params.append(request.namespace)
        param_idx += 1

    if request.content_types:
        query += f" AND c.content_type = ANY(${param_idx})"
        params.append(request.content_types)
        param_idx += 1

    query += " ORDER BY c.created_at"

    async for row in db.iterate(query, *params):
        item = {
            "id": str(row["id"]),
            "title": row["title"],
            "content_type": row["content_type"],
            "source_ref": row["source_ref"],
            "namespace": row["namespace"],
            "tags": row["tags"] or [],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

        if request.include_chunks:
            chunks = await _get_chunks(db, row["id"], request.include_embeddings)
            item["chunks"] = chunks

        yield item


async def _get_chunks(db: Any, content_id: UUID, include_embeddings: bool) -> list[dict]:
    """Get chunks for a content item."""
    if include_embeddings:
        query = """
            SELECT chunk_index, chunk_text, embedding
            FROM chunks
            WHERE content_id = $1
            ORDER BY chunk_index
        """
    else:
        query = """
            SELECT chunk_index, chunk_text
            FROM chunks
            WHERE content_id = $1
            ORDER BY chunk_index
        """

    chunks = []
    async for row in db.iterate(query, content_id):
        chunk = {
            "index": row["chunk_index"],
            "text": row["chunk_text"],
        }
        if include_embeddings and row.get("embedding"):
            # Convert pgvector to list
            chunk["embedding"] = list(row["embedding"])
        chunks.append(chunk)

    return chunks


def _parse_jsonl(content: str) -> list[dict]:
    """Parse JSONL content, extracting items only."""
    items = []
    for line in content.strip().split("\n"):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if obj.get("type") == "item":
                items.append(obj.get("data", {}))
        except json.JSONDecodeError:
            continue
    return items


async def _import_item(db: Any, item: dict, skip_existing: bool) -> str:
    """Import a single item. Returns 'imported', 'skipped', or raises."""
    content_id = item.get("id")

    # Check if exists
    if content_id:
        existing = await db.fetchrow(
            "SELECT id FROM content WHERE id = $1",
            UUID(content_id),
        )
        if existing and skip_existing:
            return "skipped"

    # Create or update content
    if content_id and not skip_existing:
        # Update existing
        await db.execute(
            """
            UPDATE content SET
                title = $2,
                content_type = $3,
                source_ref = $4,
                namespace = $5,
                tags = $6,
                updated_at = NOW()
            WHERE id = $1
            """,
            UUID(content_id),
            item["title"],
            item["content_type"],
            item.get("source_ref"),
            item.get("namespace", "default"),
            item.get("tags", []),
        )
        result_id = UUID(content_id)
    else:
        # Insert new
        result = await db.fetchrow(
            """
            INSERT INTO content (title, content_type, source_ref, namespace, tags)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            item["title"],
            item["content_type"],
            item.get("source_ref"),
            item.get("namespace", "default"),
            item.get("tags", []),
        )
        result_id = result["id"]

    # Import chunks if present
    chunks = item.get("chunks", [])
    if chunks:
        # Clear existing chunks first
        await db.execute("DELETE FROM chunks WHERE content_id = $1", result_id)

        for chunk in chunks:
            embedding = chunk.get("embedding")
            if embedding:
                await db.execute(
                    """
                    INSERT INTO chunks (content_id, chunk_index, chunk_text, embedding)
                    VALUES ($1, $2, $3, $4)
                    """,
                    result_id,
                    chunk["index"],
                    chunk["text"],
                    embedding,
                )
            else:
                await db.execute(
                    """
                    INSERT INTO chunks (content_id, chunk_index, chunk_text)
                    VALUES ($1, $2, $3)
                    """,
                    result_id,
                    chunk["index"],
                    chunk["text"],
                )

    return "imported"
