"""Document ingestion endpoints."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from knowledge_engine.api.deps import get_engine
from knowledge_engine.core.engine import KnowledgeEngine
from knowledge_engine.ingestors import IngestorService
from knowledge_engine.models.documents import Document, DocumentCreate, DocumentType

logger = logging.getLogger(__name__)

router = APIRouter()

# Ingestion timeout in seconds
INGEST_TIMEOUT = 120


class SourceIngestRequest(BaseModel):
    """Request to ingest content from a source (URL, file, or YouTube)."""

    source: str = Field(..., description="URL, file path, or YouTube video ID/URL")
    namespace: str = Field(default="default", description="Namespace for the document")
    tags: list[str] = Field(default_factory=list, description="Tags for the document")


class SourceIngestResponse(BaseModel):
    """Response from source ingestion."""

    document_id: str
    title: str | None
    source: str
    source_type: str
    chunk_count: int
    content_preview: str


@router.post("/ingest/document", response_model=Document)
async def ingest_document(
    doc: DocumentCreate,
    request: Request,
    engine: KnowledgeEngine = Depends(get_engine),
) -> Document:
    """
    Ingest a single document into the knowledge base.

    The document will be:
    - Chunked into semantic segments
    - Embedded with Voyage AI
    - Stored in Qdrant (vectors) and Neo4j (graph)
    - Indexed in PostgreSQL (metadata)
    """
    return await engine.ingest_document(doc)


@router.post("/ingest/source", response_model=SourceIngestResponse)
async def ingest_source(
    req: SourceIngestRequest,
    request: Request,
    engine: KnowledgeEngine = Depends(get_engine),
) -> SourceIngestResponse:
    """
    Ingest content from a URL, file, or YouTube video.

    Automatically detects source type and extracts content:
    - URLs: Extracts article text using trafilatura
    - YouTube: Fetches transcript (manual or auto-generated)
    - Files: Reads text files, PDFs, markdown, code files

    Examples:
    - URL: "https://example.com/article"
    - YouTube: "https://youtube.com/watch?v=dQw4w9WgXcQ" or "dQw4w9WgXcQ"
    - File: "/path/to/document.pdf"
    """
    logger.info("Source ingest started: %s", req.source)
    ingestor = IngestorService()

    try:
        # Extract content from source with timeout
        logger.info("Starting content extraction...")
        async with asyncio.timeout(30):
            result = await ingestor.ingest(req.source)
        logger.info("Content extracted: %d chars", len(result.content))

        if not result.is_valid:
            raise HTTPException(
                status_code=422,
                detail="Extracted content too short or empty"
            )

        # Determine document type
        doc_type = DocumentType.TEXT
        if result.source_type == "youtube":
            doc_type = DocumentType.NOTE
        elif result.source_type == "file":
            ext = result.metadata.get("extension", "")
            if ext in [".md", ".markdown"]:
                doc_type = DocumentType.MARKDOWN
            elif ext in [".py", ".js", ".ts", ".json", ".yaml", ".yml"]:
                doc_type = DocumentType.CODE

        # Create document for ingestion
        doc = DocumentCreate(
            content=result.content,
            title=result.title,
            document_type=doc_type,
            source=result.source,
            namespace=req.namespace,
            metadata={
                **result.metadata,
                "tags": req.tags,
                "source_type": result.source_type,
            }
        )

        # Ingest into knowledge base with timeout
        logger.info("Starting engine ingestion...")
        async with asyncio.timeout(INGEST_TIMEOUT):
            document = await engine.ingest_document(doc)
        logger.info("Engine ingestion complete: %d chunks", document.chunk_count)

        return SourceIngestResponse(
            document_id=str(document.id),
            title=document.title,
            source=result.source or req.source,
            source_type=result.source_type,
            chunk_count=document.chunk_count,
            content_preview=result.content[:500] + "..." if len(result.content) > 500 else result.content,
        )

    except asyncio.TimeoutError:
        logger.error("Source ingest timed out for: %s", req.source)
        raise HTTPException(
            status_code=504,
            detail=f"Ingestion timed out after {INGEST_TIMEOUT}s. Try a smaller document."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await ingestor.close()


@router.get("/ingest/detect")
async def detect_source_type(source: str) -> dict:
    """
    Detect the type of a source without ingesting.

    Returns the detected source type (url, youtube, file) or null if unsupported.
    """
    ingestor = IngestorService()
    source_type = ingestor.detect_type(source)
    return {
        "source": source,
        "type": source_type,
        "supported": source_type is not None,
    }


@router.delete("/ingest/{document_id}")
async def delete_document(
    document_id: UUID,
    namespace: str = "default",
    request: Request = None,
    engine: KnowledgeEngine = Depends(get_engine),
) -> dict:
    """
    Delete a document from the knowledge base.

    This performs a soft delete - the document is marked as deleted
    but can be recovered if needed.
    """
    # TODO: Implement delete in engine
    raise HTTPException(status_code=501, detail="Not implemented")
