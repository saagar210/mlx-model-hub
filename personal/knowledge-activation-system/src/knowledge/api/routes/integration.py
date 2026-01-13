"""External integration API routes.

These endpoints are designed for integration with other applications
like LocalCrew, Unified MLX App, etc. They use simple GET requests
where possible and provide consistent response formats.

Security considerations:
- All inputs are validated via Pydantic
- File paths are sanitized before use
- Error messages are sanitized in production
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from knowledge.db import get_db
from knowledge.embeddings import check_ollama_health
from knowledge.reranker import rerank_results
from knowledge.search import hybrid_search
from knowledge.security import sanitize_filename, sanitize_error_message, is_production

logger = logging.getLogger(__name__)

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
    namespace: str | None = None
    chunk_text: str | None = None
    source_ref: str | None = None
    # Quality indicators for debugging/tuning
    vector_similarity: float | None = None
    bm25_score: float | None = None


class ExternalSearchResponse(BaseModel):
    """Search response for external apps."""

    results: list[ExternalSearchResult]
    query: str
    total: int
    source: str = "knowledge-activation-system"
    reranked: bool = False


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
# Document Ingestion Schema (for Knowledge Seeder integration)
# =============================================================================


class DocumentMetadata(BaseModel):
    """Metadata for document ingestion."""

    source: str | None = Field(None, description="Source URL or identifier")
    author: str | None = Field(None, description="Content author")
    created_at: str | None = Field(None, description="Original creation date (ISO format)")
    tags: list[str] = Field(default_factory=list, description="Content tags")
    language: str = Field(default="en", description="Content language code")
    custom: dict[str, Any] = Field(default_factory=dict, description="Custom metadata fields")


class DocumentCreateRequest(BaseModel):
    """
    Request to ingest a document from external sources (Knowledge Seeder).

    This schema is designed for batch ingestion from the Knowledge Seeder tool.
    """

    content: str = Field(
        ...,
        min_length=10,
        max_length=500000,  # ~500KB max
        description="Document content (markdown, text, or code)"
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Document title"
    )
    document_type: str = Field(
        default="markdown",
        description="Content type: markdown, text, code, youtube, arxiv"
    )
    namespace: str = Field(
        default="default",
        description="Namespace for organization (e.g., 'frameworks', 'projects/voice-ai')"
    )
    metadata: DocumentMetadata = Field(
        default_factory=DocumentMetadata,
        description="Document metadata"
    )


class DocumentCreateResponse(BaseModel):
    """Response after document ingestion."""

    content_id: str
    success: bool
    chunks_created: int
    message: str
    namespace: str
    quality_stored: bool = False  # Whether quality score was stored


class BatchIngestRequest(BaseModel):
    """Batch document ingestion request."""

    documents: list[DocumentCreateRequest] = Field(
        ...,
        min_length=1,
        max_length=50,  # Max 50 docs per batch
        description="Documents to ingest"
    )
    stop_on_error: bool = Field(
        default=False,
        description="Stop batch on first error"
    )


class BatchIngestResponse(BaseModel):
    """Batch ingestion response."""

    total: int
    succeeded: int
    failed: int
    results: list[DocumentCreateResponse]


# =============================================================================
# External API Endpoints
# =============================================================================


@router.get("/search", response_model=ExternalSearchResponse)
async def external_search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    namespace: str | None = Query(None, description="Filter by namespace (use * suffix for prefix match)"),
    min_score: float | None = Query(None, ge=0.0, le=1.0, description="Minimum score threshold"),
    rerank: bool = Query(False, description="Apply cross-encoder reranking for better quality"),
) -> ExternalSearchResponse:
    """
    Search the knowledge base (GET endpoint for easy integration).

    This endpoint uses hybrid search (BM25 + vector with RRF fusion)
    to find the most relevant content. Optionally apply cross-encoder
    reranking for improved result quality.

    Example:
        GET /api/v1/search?q=React%20hooks&limit=5
        GET /api/v1/search?q=FastAPI&namespace=frameworks
        GET /api/v1/search?q=deployment&namespace=projects/*
        GET /api/v1/search?q=complex%20query&rerank=true

    Returns results with confidence scores from 0.0 to 1.0.
    """
    try:
        # Get more results if reranking (reranker will re-sort)
        search_limit = limit * 2 if rerank else limit
        results = await hybrid_search(q, limit=search_limit, namespace=namespace, min_score=min_score)

        # Apply reranking if requested
        reranked = False
        if rerank and results:
            try:
                results = await rerank_results(q, results, top_k=limit)
                reranked = True
            except Exception as e:
                logger.warning(f"Reranking failed, using hybrid results: {e}")
                results = results[:limit]
        elif rerank:
            results = results[:limit]

        # Log search query for analytics (non-blocking, fire and forget)
        try:
            db = await get_db()
            top_score = results[0].score if results else None
            avg_score = sum(r.score for r in results) / len(results) if results else None
            await db.log_search_query(
                query=q,
                result_count=len(results),
                top_score=top_score,
                avg_score=avg_score,
                namespace=namespace,
                reranked=reranked,
                source="api",
            )
        except Exception as log_err:
            logger.warning(f"Failed to log search query: {log_err}")

        return ExternalSearchResponse(
            results=[
                ExternalSearchResult(
                    content_id=str(r.content_id),
                    title=r.title,
                    content_type=r.content_type,
                    score=min(r.score, 1.0),  # Normalize to 0-1
                    namespace=r.namespace,
                    chunk_text=r.chunk_text,
                    source_ref=r.source_ref,
                    vector_similarity=r.vector_similarity,
                    bm25_score=r.bm25_score,
                )
                for r in results
            ],
            query=q,
            total=len(results),
            reranked=reranked,
        )
    except Exception as e:
        logger.exception(f"Search failed for query: {q[:50]}...")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=f"Search failed: {error_msg}") from e


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

        from knowledge.chunking import ChunkingConfig, chunk_recursive
        from knowledge.config import get_settings
        from knowledge.embeddings import embed_text

        settings = get_settings()
        chunking_config = ChunkingConfig(chunk_size=250, chunk_overlap=40)

        # Create filename from title using security module
        safe_title = sanitize_filename(request.title, max_length=80)
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
        content_id = await db.insert_content(
            filepath=str(filepath),
            content_type="research",
            title=request.title,
            content_for_hash=request.content,  # For deduplication
            summary=request.content[:500] if len(request.content) > 500 else request.content,
            tags=all_tags,
            metadata={
                "source": request.source,
                "ingested_via": "api",
                **request.metadata,
            },
            add_to_review=False,  # Research doesn't need spaced repetition by default
        )

        # Chunk and embed the content
        content_for_embedding = request.content
        chunks = chunk_recursive(content_for_embedding, chunking_config)

        # Prepare chunks with embeddings for batch insert
        chunk_records = []
        for chunk in chunks:
            embedding = await embed_text(chunk.text)
            chunk_records.append({
                "chunk_index": chunk.index,
                "chunk_text": chunk.text,
                "embedding": embedding,
                "source_ref": f"{filepath.name}#chunk-{chunk.index}",
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            })

        # Batch insert chunks
        await db.insert_chunks(content_id, chunk_records)
        chunk_count = len(chunk_records)

        return ResearchIngestResponse(
            content_id=str(content_id),
            success=True,
            chunks_created=chunk_count,
            message=f"Successfully ingested '{request.title}' with {chunk_count} chunks",
        )

    except Exception as e:
        logger.exception(f"Ingest failed for: {request.title[:50]}...")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(
            status_code=500, detail=f"Ingest failed: {error_msg}"
        ) from e


# =============================================================================
# Document Ingestion Endpoints (for Knowledge Seeder)
# =============================================================================


@router.post("/ingest/document", response_model=DocumentCreateResponse)
async def ingest_document(request: DocumentCreateRequest) -> DocumentCreateResponse:
    """
    Ingest a document into the knowledge base.

    This is the primary endpoint for the Knowledge Seeder integration.
    Documents are:
    1. Saved as markdown files in the Obsidian vault (organized by namespace)
    2. Chunked using appropriate strategy based on document_type
    3. Embedded for semantic search
    4. Tagged and indexed for BM25 search

    Namespace Format:
        - Simple: "frameworks", "infrastructure", "tools"
        - Nested: "projects/voice-ai", "projects/browser-automation"
        - Namespaces become folder paths in the vault

    Document Types:
        - markdown: General markdown content (semantic chunking)
        - text: Plain text (recursive chunking)
        - code: Source code (recursive chunking, preserves structure)
        - youtube: Video transcripts (timestamp-based chunking)
        - arxiv: Academic papers (semantic chunking)

    Example:
        POST /api/v1/ingest/document
        {
            "content": "# FastAPI\\n\\nFastAPI is a modern...",
            "title": "FastAPI - Official Documentation",
            "document_type": "markdown",
            "namespace": "frameworks",
            "metadata": {
                "source": "https://fastapi.tiangolo.com/",
                "tags": ["python", "web-framework"],
                "custom": {
                    "seeder_source_id": "frameworks:fastapi-docs",
                    "seeder_quality_score": 92.5
                }
            }
        }
    """
    try:
        from pathlib import Path

        from knowledge.chunking import (
            ChunkingStrategy,
            chunk_content,
            get_strategy_for_content_type,
        )
        from knowledge.config import get_settings
        from knowledge.embeddings import embed_text

        settings = get_settings()

        # Map document_type to internal content_type
        type_mapping = {
            "markdown": "note",
            "text": "note",
            "code": "file",
            "youtube": "youtube",
            "arxiv": "note",
        }
        internal_type = type_mapping.get(request.document_type, "note")

        # Determine chunking strategy
        strategy_mapping = {
            "markdown": ChunkingStrategy.SEMANTIC,
            "text": ChunkingStrategy.RECURSIVE,
            "code": ChunkingStrategy.RECURSIVE,
            "youtube": ChunkingStrategy.YOUTUBE,
            "arxiv": ChunkingStrategy.SEMANTIC,
        }
        chunking_strategy = strategy_mapping.get(
            request.document_type, ChunkingStrategy.RECURSIVE
        )

        # Build file path from namespace
        # Convert namespace to path: "projects/voice-ai" -> "Projects/Voice-Ai"
        namespace_parts = request.namespace.split("/")
        namespace_path = "/".join(
            part.replace("-", " ").title().replace(" ", "-")
            for part in namespace_parts
        )

        safe_title = sanitize_filename(request.title, max_length=80)
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        filename = f"{safe_title}-{timestamp}.md"

        vault_path = Path(settings.vault_path).expanduser()
        knowledge_folder = vault_path / settings.knowledge_folder / namespace_path
        knowledge_folder.mkdir(parents=True, exist_ok=True)
        filepath = knowledge_folder / filename

        # Build YAML frontmatter
        all_tags = list(set(
            [request.document_type, request.namespace.replace("/", "-")]
            + request.metadata.tags
        ))
        frontmatter_lines = [
            "---",
            f"title: \"{request.title}\"",
            f"type: {internal_type}",
            f"document_type: {request.document_type}",
            f"namespace: {request.namespace}",
            f"tags: [{', '.join(all_tags)}]",
            f"created_at: '{datetime.now(UTC).isoformat()}'",
        ]

        if request.metadata.source:
            frontmatter_lines.append(f"source: \"{request.metadata.source}\"")
        if request.metadata.author:
            frontmatter_lines.append(f"author: \"{request.metadata.author}\"")
        if request.metadata.language:
            frontmatter_lines.append(f"language: {request.metadata.language}")

        # Add custom metadata
        for key, value in request.metadata.custom.items():
            if isinstance(value, str):
                frontmatter_lines.append(f"{key}: \"{value}\"")
            elif isinstance(value, (int, float)):
                frontmatter_lines.append(f"{key}: {value}")

        frontmatter_lines.append("---")
        frontmatter_lines.append("")

        # Write the file
        full_content = "\n".join(frontmatter_lines) + request.content
        filepath.write_text(full_content, encoding="utf-8")

        # Ingest into database
        db = await get_db()

        # Build metadata for storage
        storage_metadata = {
            "namespace": request.namespace,
            "document_type": request.document_type,
            "language": request.metadata.language,
            "ingested_via": "api",
            **request.metadata.custom,
        }
        if request.metadata.source:
            storage_metadata["source"] = request.metadata.source
        if request.metadata.author:
            storage_metadata["author"] = request.metadata.author

        # Create content record
        content_id = await db.insert_content(
            filepath=str(filepath),
            content_type=internal_type,
            title=request.title,
            content_for_hash=request.content,
            url=request.metadata.source,
            summary=request.content[:500] if len(request.content) > 500 else request.content,
            tags=all_tags,
            metadata=storage_metadata,
            add_to_review=False,  # Seeder content doesn't need spaced repetition by default
        )

        # Chunk and embed
        chunks = chunk_content(request.content, strategy=chunking_strategy)

        chunk_records = []
        for chunk in chunks:
            embedding = await embed_text(chunk.text)
            chunk_records.append({
                "chunk_index": chunk.index,
                "chunk_text": chunk.text,
                "embedding": embedding,
                "source_ref": chunk.source_ref or f"chunk-{chunk.index}",
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            })

        await db.insert_chunks(content_id, chunk_records)

        # Check if quality score was provided
        quality_stored = "seeder_quality_score" in request.metadata.custom

        return DocumentCreateResponse(
            content_id=str(content_id),
            success=True,
            chunks_created=len(chunk_records),
            message=f"Successfully ingested '{request.title}' with {len(chunk_records)} chunks",
            namespace=request.namespace,
            quality_stored=quality_stored,
        )

    except Exception as e:
        logger.exception(f"Document ingest failed for: {request.title[:50]}...")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(
            status_code=500, detail=f"Ingest failed: {error_msg}"
        ) from e


@router.post("/ingest/batch", response_model=BatchIngestResponse)
async def ingest_batch(request: BatchIngestRequest) -> BatchIngestResponse:
    """
    Batch ingest multiple documents.

    More efficient than individual calls for large imports.
    Rate limit: 50 documents per request.

    Example:
        POST /api/v1/ingest/batch
        {
            "documents": [
                {"content": "...", "title": "Doc 1", ...},
                {"content": "...", "title": "Doc 2", ...}
            ],
            "stop_on_error": false
        }
    """
    results = []
    succeeded = 0
    failed = 0

    for doc in request.documents:
        try:
            result = await ingest_document(doc)
            results.append(result)
            succeeded += 1
        except HTTPException as e:
            failed += 1
            results.append(DocumentCreateResponse(
                content_id="",
                success=False,
                chunks_created=0,
                message=str(e.detail),
                namespace=doc.namespace,
            ))
            if request.stop_on_error:
                break
        except Exception as e:
            failed += 1
            results.append(DocumentCreateResponse(
                content_id="",
                success=False,
                chunks_created=0,
                message=str(e),
                namespace=doc.namespace,
            ))
            if request.stop_on_error:
                break

    return BatchIngestResponse(
        total=len(request.documents),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


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
        logger.exception("Stats retrieval failed")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e


# =============================================================================
# Quick Capture Webhook (for Raycast, Alfred, Shortcuts, etc.)
# =============================================================================


class QuickCaptureRequest(BaseModel):
    """Quick capture request from external tools."""

    content: str = Field(..., min_length=1, max_length=50000, description="Content to capture")
    title: str | None = Field(None, max_length=200, description="Optional title (auto-generated if not provided)")
    namespace: str = Field(default="quick-capture", description="Namespace for organization")
    tags: list[str] = Field(default_factory=list, description="Optional tags")
    source: str = Field(default="webhook", description="Source identifier (e.g., 'raycast', 'alfred')")


class QuickCaptureResponse(BaseModel):
    """Quick capture response."""

    success: bool
    content_id: str | None
    title: str
    message: str


@router.post("/capture", response_model=QuickCaptureResponse)
async def quick_capture(request: QuickCaptureRequest) -> QuickCaptureResponse:
    """
    Quick capture endpoint for real-time knowledge capture.

    Designed for integration with:
    - Raycast extensions/scripts
    - Alfred workflows
    - Apple Shortcuts
    - Browser extensions
    - Any HTTP client

    Auto-generates title from content if not provided.
    Minimal required fields for fastest capture.

    Example Raycast script:
        curl -X POST http://localhost:8000/api/v1/capture \\
            -H "Content-Type: application/json" \\
            -d '{"content": "...", "source": "raycast"}'

    Example with title and tags:
        curl -X POST http://localhost:8000/api/v1/capture \\
            -H "Content-Type: application/json" \\
            -d '{"content": "...", "title": "My Note", "tags": ["idea", "project"]}'
    """
    try:
        from pathlib import Path

        from knowledge.chunking import ChunkingStrategy, chunk_content
        from knowledge.config import get_settings
        from knowledge.embeddings import embed_text

        settings = get_settings()

        # Auto-generate title from content if not provided
        if request.title:
            title = request.title
        else:
            # Use first line or first 50 chars
            first_line = request.content.split('\n')[0].strip()
            title = first_line[:50] + ('...' if len(first_line) > 50 else '')
            if not title:
                title = f"Quick Capture - {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}"

        # Build file path
        safe_title = sanitize_filename(title, max_length=60)
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        filename = f"capture-{safe_title}-{timestamp}.md"

        vault_path = Path(settings.vault_path).expanduser()
        capture_folder = vault_path / settings.knowledge_folder / "Captures" / request.namespace.replace("/", "-")
        capture_folder.mkdir(parents=True, exist_ok=True)
        filepath = capture_folder / filename

        # Build content with frontmatter
        all_tags = list(set(["capture", request.source] + request.tags))
        frontmatter = [
            "---",
            f'title: "{title}"',
            f"type: capture",
            f"source: {request.source}",
            f"namespace: {request.namespace}",
            f"tags: [{', '.join(all_tags)}]",
            f"captured_at: '{datetime.now(UTC).isoformat()}'",
            "---",
            "",
        ]
        full_content = "\n".join(frontmatter) + request.content
        filepath.write_text(full_content, encoding="utf-8")

        # Ingest into database
        db = await get_db()
        content_id = await db.insert_content(
            filepath=str(filepath),
            content_type="capture",
            title=title,
            content_for_hash=request.content,
            summary=request.content[:300] if len(request.content) > 300 else request.content,
            tags=all_tags,
            metadata={
                "namespace": request.namespace,
                "source": request.source,
                "captured_via": "webhook",
            },
            add_to_review=False,
        )

        # Chunk and embed
        chunks = chunk_content(request.content, strategy=ChunkingStrategy.RECURSIVE)
        chunk_records = []
        for chunk in chunks:
            embedding = await embed_text(chunk.text)
            chunk_records.append({
                "chunk_index": chunk.index,
                "chunk_text": chunk.text,
                "embedding": embedding,
                "source_ref": f"capture-{chunk.index}",
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            })

        await db.insert_chunks(content_id, chunk_records)

        return QuickCaptureResponse(
            success=True,
            content_id=str(content_id),
            title=title,
            message=f"Captured '{title}' with {len(chunk_records)} chunks",
        )

    except Exception as e:
        logger.exception("Quick capture failed")
        error_msg = sanitize_error_message(e, production=is_production())
        return QuickCaptureResponse(
            success=False,
            content_id=None,
            title=request.title or "Unknown",
            message=f"Capture failed: {error_msg}",
        )


@router.post("/capture/url", response_model=QuickCaptureResponse)
async def capture_url(
    url: str = Query(..., description="URL to capture"),
    namespace: str = Query(default="bookmarks", description="Namespace"),
    tags: str = Query(default="", description="Comma-separated tags"),
    source: str = Query(default="webhook", description="Source identifier"),
) -> QuickCaptureResponse:
    """
    Capture content from a URL.

    Fetches the URL, extracts readable content, and stores it.
    Ideal for Raycast "Capture URL" shortcuts.

    Example:
        POST /api/v1/capture/url?url=https://example.com&tags=article,read-later
    """
    try:
        import httpx
        from pathlib import Path

        from knowledge.chunking import ChunkingStrategy, chunk_content
        from knowledge.config import get_settings
        from knowledge.embeddings import embed_text

        settings = get_settings()

        # Fetch URL content
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            html_content = response.text

        # Extract title from HTML
        import re
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else url.split('/')[-1]

        # Basic HTML to text conversion (strip tags)
        text_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        text_content = re.sub(r'<style[^>]*>.*?</style>', '', text_content, flags=re.DOTALL | re.IGNORECASE)
        text_content = re.sub(r'<[^>]+>', ' ', text_content)
        text_content = re.sub(r'\s+', ' ', text_content).strip()

        if len(text_content) < 50:
            return QuickCaptureResponse(
                success=False,
                content_id=None,
                title=title,
                message="URL content too short or could not be extracted",
            )

        # Parse tags
        tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []

        # Build file path
        safe_title = sanitize_filename(title, max_length=60)
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        filename = f"bookmark-{safe_title}-{timestamp}.md"

        vault_path = Path(settings.vault_path).expanduser()
        bookmark_folder = vault_path / settings.knowledge_folder / "Bookmarks"
        bookmark_folder.mkdir(parents=True, exist_ok=True)
        filepath = bookmark_folder / filename

        # Build markdown content
        all_tags = list(set(["bookmark", source] + tag_list))
        content = f"""---
title: "{title}"
type: bookmark
url: "{url}"
source: {source}
namespace: {namespace}
tags: [{', '.join(all_tags)}]
captured_at: '{datetime.now(UTC).isoformat()}'
---

# {title}

**Source:** [{url}]({url})

---

{text_content[:10000]}
"""

        filepath.write_text(content, encoding="utf-8")

        # Ingest into database
        db = await get_db()
        content_id = await db.insert_content(
            filepath=str(filepath),
            content_type="bookmark",
            title=title,
            url=url,
            content_for_hash=text_content,
            summary=text_content[:300],
            tags=all_tags,
            metadata={
                "namespace": namespace,
                "source": source,
                "original_url": url,
            },
            add_to_review=False,
        )

        # Chunk and embed
        chunks = chunk_content(text_content[:10000], strategy=ChunkingStrategy.SEMANTIC)
        chunk_records = []
        for chunk in chunks:
            embedding = await embed_text(chunk.text)
            chunk_records.append({
                "chunk_index": chunk.index,
                "chunk_text": chunk.text,
                "embedding": embedding,
                "source_ref": url,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            })

        await db.insert_chunks(content_id, chunk_records)

        return QuickCaptureResponse(
            success=True,
            content_id=str(content_id),
            title=title,
            message=f"Captured '{title}' from URL with {len(chunk_records)} chunks",
        )

    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch URL {url}: {e}")
        return QuickCaptureResponse(
            success=False,
            content_id=None,
            title=url,
            message=f"Failed to fetch URL: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"URL capture failed for {url}")
        error_msg = sanitize_error_message(e, production=is_production())
        return QuickCaptureResponse(
            success=False,
            content_id=None,
            title=url,
            message=f"Capture failed: {error_msg}",
        )


# =============================================================================
# Search Analytics Endpoints
# =============================================================================


class SearchAnalyticsResponse(BaseModel):
    """Search analytics summary."""

    total_queries: int
    queries_today: int
    zero_results_count: int
    low_score_count: int
    avg_top_score: float | None
    gap_rate: float


class SearchGap(BaseModel):
    """A search query with poor results."""

    query_text: str
    search_count: int
    avg_results: float
    avg_top_score: float | None
    last_searched: datetime


class SearchGapsResponse(BaseModel):
    """Search gaps response."""

    gaps: list[SearchGap]
    total: int


@router.get("/analytics/search", response_model=SearchAnalyticsResponse)
async def get_search_analytics() -> SearchAnalyticsResponse:
    """
    Get search analytics summary.

    Returns metrics about search quality including:
    - Total queries processed
    - Queries with zero results
    - Queries with low scores
    - Average top score
    - Overall gap rate

    Example:
        GET /api/v1/analytics/search
    """
    try:
        db = await get_db()
        stats = await db.get_search_analytics()
        return SearchAnalyticsResponse(**stats)
    except Exception as e:
        logger.exception("Failed to get search analytics")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e


@router.get("/analytics/gaps", response_model=SearchGapsResponse)
async def get_search_gaps(
    limit: int = Query(20, ge=1, le=100, description="Number of gaps to return"),
) -> SearchGapsResponse:
    """
    Get search queries that had poor or no results.

    Use this for content gap analysis - identify what users are
    searching for but not finding.

    Example:
        GET /api/v1/analytics/gaps?limit=10
    """
    try:
        db = await get_db()
        gaps = await db.get_search_gaps(limit=limit)
        return SearchGapsResponse(
            gaps=[SearchGap(**gap) for gap in gaps],
            total=len(gaps),
        )
    except Exception as e:
        logger.exception("Failed to get search gaps")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e


# =============================================================================
# Content Quality Endpoints
# =============================================================================


class QualityDistribution(BaseModel):
    """Quality score distribution."""

    high: int  # >= 0.7
    medium: int  # 0.4-0.7
    low: int  # < 0.4
    unscored: int


class ContentQualityResponse(BaseModel):
    """Content quality metrics response."""

    total_content: int
    avg_quality: float | None
    distribution: QualityDistribution
    lowest_quality: list[dict]


@router.get("/analytics/quality", response_model=ContentQualityResponse)
async def get_content_quality() -> ContentQualityResponse:
    """
    Get content quality metrics and distribution.

    Returns quality score distribution across all content,
    plus the lowest quality items for review.

    Example:
        GET /api/v1/analytics/quality
    """
    try:
        db = await get_db()

        async with db.acquire() as conn:
            # Get distribution
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE deleted_at IS NULL"
            )
            high_count = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE deleted_at IS NULL AND quality_score >= 0.7"
            )
            medium_count = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE deleted_at IS NULL AND quality_score >= 0.4 AND quality_score < 0.7"
            )
            low_count = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE deleted_at IS NULL AND quality_score < 0.4"
            )
            unscored = await conn.fetchval(
                "SELECT COUNT(*) FROM content WHERE deleted_at IS NULL AND quality_score IS NULL"
            )
            avg_quality = await conn.fetchval(
                "SELECT AVG(quality_score) FROM content WHERE deleted_at IS NULL AND quality_score IS NOT NULL"
            )

            # Get lowest quality items
            lowest = await conn.fetch(
                """
                SELECT id, title, type, quality_score, created_at
                FROM content
                WHERE deleted_at IS NULL AND quality_score IS NOT NULL
                ORDER BY quality_score ASC
                LIMIT 10
                """
            )

        return ContentQualityResponse(
            total_content=total or 0,
            avg_quality=float(avg_quality) if avg_quality else None,
            distribution=QualityDistribution(
                high=high_count or 0,
                medium=medium_count or 0,
                low=low_count or 0,
                unscored=unscored or 0,
            ),
            lowest_quality=[
                {
                    "id": str(row["id"]),
                    "title": row["title"],
                    "type": row["type"],
                    "quality_score": row["quality_score"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in lowest
            ],
        )
    except Exception as e:
        logger.exception("Failed to get content quality")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e


@router.post("/content/{content_id}/quality")
async def update_content_quality(
    content_id: str,
    quality_score: float = Query(..., ge=0.0, le=1.0, description="Quality score 0-1"),
) -> dict:
    """
    Manually set quality score for a content item.

    Use this to override computed quality scores for specific items.

    Example:
        POST /api/v1/content/{content_id}/quality?quality_score=0.85
    """
    try:
        from uuid import UUID
        db = await get_db()

        async with db.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE content
                SET quality_score = $1
                WHERE id = $2 AND deleted_at IS NULL
                """,
                quality_score,
                UUID(content_id),
            )

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Content not found")

        return {
            "success": True,
            "content_id": content_id,
            "quality_score": quality_score,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid content ID format")
    except Exception as e:
        logger.exception(f"Failed to update quality for {content_id}")
        error_msg = sanitize_error_message(e, production=is_production())
        raise HTTPException(status_code=500, detail=error_msg) from e
