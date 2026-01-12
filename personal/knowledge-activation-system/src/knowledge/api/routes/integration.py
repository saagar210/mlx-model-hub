"""External integration API routes.

These endpoints are designed for integration with other applications
like LocalCrew, Unified MLX App, etc. They use simple GET requests
where possible and provide consistent response formats.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from knowledge.db import get_db
from knowledge.embeddings import check_ollama_health
from knowledge.search import hybrid_search

router = APIRouter(prefix="/api/v1", tags=["integration"])


# =============================================================================
# Schemas for External Integration
# =============================================================================


class ExternalSearchResult(BaseModel):
    """Search result optimized for external consumption."""

    content_id: str  # String UUID for easier JSON handling
    title: str
    content_type: str
    score: float = Field(ge=0.0, le=1.0)
    chunk_text: str | None = None
    source_ref: str | None = None


class ExternalSearchResponse(BaseModel):
    """Search response for external apps."""

    results: list[ExternalSearchResult]
    query: str
    total: int
    source: str = "knowledge-activation-system"


class ResearchIngestRequest(BaseModel):
    """Request to ingest research findings."""

    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=10, description="Markdown content")
    tags: list[str] = Field(default_factory=list)
    source: str = Field(default="external", description="Source application")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchIngestResponse(BaseModel):
    """Response after ingesting research."""

    content_id: str
    success: bool
    chunks_created: int
    message: str


class IntegrationHealthResponse(BaseModel):
    """Health check for integration clients."""

    status: str
    version: str
    services: dict[str, str]
    stats: dict[str, int]


# =============================================================================
# External API Endpoints
# =============================================================================


@router.get("/search", response_model=ExternalSearchResponse)
async def external_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
) -> ExternalSearchResponse:
    """
    Search the knowledge base (GET endpoint for easy integration).

    This endpoint uses hybrid search (BM25 + vector with RRF fusion)
    to find the most relevant content.

    Example:
        GET /api/v1/search?q=React%20hooks&limit=5

    Returns results with confidence scores from 0.0 to 1.0.
    """
    try:
        results = await hybrid_search(q, limit=limit)

        return ExternalSearchResponse(
            results=[
                ExternalSearchResult(
                    content_id=str(r.content_id),
                    title=r.title,
                    content_type=r.content_type,
                    score=min(r.score, 1.0),  # Normalize to 0-1
                    chunk_text=r.chunk_text,
                    source_ref=r.source_ref,
                )
                for r in results
            ],
            query=q,
            total=len(results),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}") from e


@router.post("/ingest/research", response_model=ResearchIngestResponse)
async def ingest_research(request: ResearchIngestRequest) -> ResearchIngestResponse:
    """
    Ingest research findings into the knowledge base.

    Use this endpoint to store research reports, findings, or any
    markdown content from external applications like LocalCrew.

    The content will be:
    1. Saved as a markdown file in the Obsidian vault
    2. Chunked and embedded for semantic search
    3. Tagged with the provided tags + auto-generated tags

    Example:
        POST /api/v1/ingest/research
        {
            "title": "Research: React Server Components",
            "content": "# Research Report\\n\\n...",
            "tags": ["research", "react", "frontend"],
            "source": "localcrew",
            "metadata": {"execution_id": "abc123", "confidence": 0.85}
        }
    """
    try:
        from pathlib import Path

        from knowledge.config import get_settings
        from knowledge.db import get_db
        from knowledge.embeddings import embed_text
        from knowledge.ingest.files import chunk_text

        settings = get_settings()

        # Create filename from title
        safe_title = "".join(
            c if c.isalnum() or c in " -_" else "_" for c in request.title
        )
        safe_title = safe_title.replace(" ", "-").lower()[:100]
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        filename = f"research-{safe_title}-{timestamp}.md"

        # Build the file path
        vault_path = Path(settings.vault_path).expanduser()
        knowledge_folder = vault_path / settings.knowledge_folder / "Research"
        knowledge_folder.mkdir(parents=True, exist_ok=True)
        filepath = knowledge_folder / filename

        # Build YAML frontmatter
        all_tags = list(set(["research", request.source] + request.tags))
        frontmatter = [
            "---",
            f"title: {request.title}",
            f"type: research",
            f"source: {request.source}",
            f"tags: [{', '.join(all_tags)}]",
            f"created_at: '{datetime.now(UTC).isoformat()}'",
        ]

        # Add metadata fields
        for key, value in request.metadata.items():
            if isinstance(value, str):
                frontmatter.append(f"{key}: '{value}'")
            else:
                frontmatter.append(f"{key}: {value}")

        frontmatter.append("---")
        frontmatter.append("")

        # Write the file
        full_content = "\n".join(frontmatter) + request.content
        filepath.write_text(full_content, encoding="utf-8")

        # Now ingest into database
        db = await get_db()

        # Create content record
        content_id = await db.create_content(
            filepath=str(filepath),
            content_type="research",
            title=request.title,
            summary=request.content[:500] if len(request.content) > 500 else request.content,
            tags=all_tags,
            metadata={
                "source": request.source,
                "ingested_via": "api",
                **request.metadata,
            },
        )

        # Chunk and embed the content (strip frontmatter for embedding)
        content_for_embedding = request.content
        chunks = chunk_text(content_for_embedding, chunk_size=1000, chunk_overlap=200)

        chunk_count = 0
        for i, chunk in enumerate(chunks):
            embedding = await embed_text(chunk)
            await db.create_chunk(
                content_id=content_id,
                chunk_text=chunk,
                embedding=embedding,
                chunk_index=i,
                source_ref=f"{filepath.name}#chunk-{i}",
            )
            chunk_count += 1

        return ResearchIngestResponse(
            content_id=str(content_id),
            success=True,
            chunks_created=chunk_count,
            message=f"Successfully ingested '{request.title}' with {chunk_count} chunks",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ingest failed: {str(e)}"
        ) from e


@router.get("/health", response_model=IntegrationHealthResponse)
async def integration_health() -> IntegrationHealthResponse:
    """
    Health check endpoint for integration clients.

    Returns service status and basic statistics. Use this to verify
    connectivity before making other API calls.

    Example:
        GET /api/v1/health

    Response:
        {
            "status": "healthy",
            "version": "0.1.0",
            "services": {
                "database": "connected",
                "embeddings": "available"
            },
            "stats": {
                "total_content": 1000,
                "total_chunks": 5000
            }
        }
    """
    services = {}
    stats = {}

    # Check database
    try:
        db = await get_db()
        db_stats = await db.get_stats()
        services["database"] = "connected"
        stats["total_content"] = db_stats.get("total_content", 0)
        stats["total_chunks"] = db_stats.get("total_chunks", 0)
    except Exception as e:
        services["database"] = f"error: {str(e)}"

    # Check Ollama/embeddings
    try:
        ollama_status = await check_ollama_health()
        if ollama_status.healthy:
            services["embeddings"] = "available"
        else:
            services["embeddings"] = f"unavailable: {ollama_status.error}"
    except Exception as e:
        services["embeddings"] = f"error: {str(e)}"

    # Determine overall status
    all_healthy = all(
        v in ("connected", "available") for v in services.values()
    )

    return IntegrationHealthResponse(
        status="healthy" if all_healthy else "degraded",
        version="0.1.0",
        services=services,
        stats=stats,
    )


@router.get("/stats")
async def integration_stats() -> dict:
    """
    Get detailed statistics about the knowledge base.

    Useful for dashboards and monitoring integration.
    """
    try:
        db = await get_db()
        stats = await db.get_stats()

        return {
            "total_content": stats.get("total_content", 0),
            "total_chunks": stats.get("total_chunks", 0),
            "content_by_type": stats.get("content_by_type", {}),
            "review_active": stats.get("review_active", 0),
            "review_due": stats.get("review_due", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
