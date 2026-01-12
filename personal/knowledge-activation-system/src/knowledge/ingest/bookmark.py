"""Bookmark/URL ingestion using trafilatura."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
import trafilatura
from trafilatura.settings import use_config

from knowledge.chunking import ChunkingStrategy, chunk_content
from knowledge.config import Settings, get_settings
from knowledge.db import get_db
from knowledge.embeddings import embed_batch
from knowledge.ingest import IngestResult
from knowledge.obsidian import create_note, get_relative_path
from knowledge.validation import validate_content

# Configure trafilatura for better extraction
TRAFILATURA_CONFIG = use_config()
TRAFILATURA_CONFIG.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")
TRAFILATURA_CONFIG.set("DEFAULT", "MIN_OUTPUT_SIZE", "100")


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc or url


async def fetch_url(url: str, timeout: float = 30.0) -> str:
    """
    Fetch URL content.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Raw HTML content

    Raises:
        ValueError: If fetch fails
    """
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        },
    ) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            raise ValueError(f"HTTP error {e.response.status_code}: {url}") from e
        except httpx.TimeoutException as e:
            raise ValueError(f"Request timed out: {url}") from e
        except httpx.RequestError as e:
            raise ValueError(f"Request failed: {e}") from e


def extract_content(html: str, url: str) -> tuple[str, str | None]:
    """
    Extract main content from HTML using trafilatura.

    Args:
        html: Raw HTML content
        url: Source URL (for reference extraction)

    Returns:
        Tuple of (extracted_text, title)
    """
    # Extract with trafilatura
    result = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        include_links=False,
        output_format="txt",
        config=TRAFILATURA_CONFIG,
    )

    if not result:
        # Fallback: try with different settings
        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            favor_precision=False,
            favor_recall=True,
            config=TRAFILATURA_CONFIG,
        )

    # Extract metadata for title
    metadata = trafilatura.extract_metadata(html)
    title = metadata.title if metadata else None

    return result or "", title


async def ingest_bookmark(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    settings: Settings | None = None,
) -> IngestResult:
    """
    Ingest a bookmark/URL.

    1. Fetch URL content
    2. Extract main text with trafilatura
    3. Validate content
    4. Chunk semantically
    5. Generate embeddings
    6. Create Obsidian note
    7. Store in database

    Args:
        url: URL to ingest
        title: Optional title override
        tags: Optional tags
        settings: Optional settings override

    Returns:
        IngestResult with success/failure info
    """
    settings = settings or get_settings()

    try:
        # Fetch HTML
        html = await fetch_url(url)

        # Extract content
        content, extracted_title = extract_content(html, url)

        # Use provided title, extracted title, or domain as fallback
        final_title = title or extracted_title or extract_domain(url)

        # Validate content
        validation = validate_content(content, min_length=100, url=url)
        if not validation.valid:
            error_msg = validation.error.value if validation.error else "Unknown validation error"
            return IngestResult(
                success=False,
                error=f"Content validation failed: {error_msg}",
            )

        # Chunk content
        chunks = chunk_content(validation.content, strategy=ChunkingStrategy.SEMANTIC)

        if not chunks:
            return IngestResult(
                success=False,
                error="No chunks generated from content",
            )

        # Generate embeddings
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = await embed_batch(chunk_texts)

        # Create Obsidian note
        metadata = {
            "domain": extract_domain(url),
            "word_count": len(validation.content.split()),
        }

        note_path = create_note(
            content_type="bookmark",
            title=final_title,
            content=validation.content,
            url=url,
            tags=tags,
            metadata=metadata,
            settings=settings,
        )

        # Store in database
        db = await get_db()
        relative_path = get_relative_path(note_path, settings)

        # Check if already exists
        if await db.content_exists(relative_path):
            return IngestResult(
                success=False,
                error=f"Content already exists: {relative_path}",
            )

        # Insert content
        content_id = await db.insert_content(
            filepath=relative_path,
            content_type="bookmark",
            title=final_title,
            content_for_hash=validation.content,
            url=url,
            tags=tags,
            metadata=metadata,
        )

        # Insert chunks with embeddings
        chunk_records = [
            {
                "chunk_index": chunk.index,
                "chunk_text": chunk.text,
                "embedding": embeddings[i],
                "source_ref": chunk.source_ref,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            }
            for i, chunk in enumerate(chunks)
        ]
        await db.insert_chunks(content_id, chunk_records)

        result = IngestResult(
            success=True,
            content_id=content_id,
            filepath=note_path,
            title=final_title,
            chunks_created=len(chunks),
        )

        # Add warning if validation had a warning
        if validation.warning:
            result.error = f"Warning: {validation.warning}"

        return result

    except ValueError as e:
        return IngestResult(
            success=False,
            error=str(e),
        )
    except Exception as e:
        return IngestResult(
            success=False,
            error=f"Unexpected error: {e}",
        )


async def ingest_bookmarks_batch(
    urls: list[str],
    tags: list[str] | None = None,
    settings: Settings | None = None,
) -> list[IngestResult]:
    """
    Ingest multiple bookmarks.

    Args:
        urls: List of URLs to ingest
        tags: Optional tags to apply to all
        settings: Optional settings override

    Returns:
        List of IngestResult for each URL
    """
    results = []
    for url in urls:
        result = await ingest_bookmark(url, tags=tags, settings=settings)
        results.append(result)
    return results
