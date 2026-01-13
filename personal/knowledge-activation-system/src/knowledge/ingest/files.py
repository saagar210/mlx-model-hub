"""File ingestion (PDF, TXT, MD).

Supports secure ingestion of local files with:
- Path traversal protection
- File type validation
- Content validation
"""

from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader

from knowledge.chunking import ChunkingStrategy, chunk_content
from knowledge.config import Settings, get_settings
from knowledge.db import get_db
from knowledge.embeddings import embed_batch
from knowledge.ingest import IngestResult
from knowledge.obsidian import create_note, get_relative_path
from knowledge.security import PathSecurityError, is_safe_filename
from knowledge.validation import extract_title_from_content, validate_content

logger = logging.getLogger(__name__)

# Page separator for PDF chunking
PAGE_SEPARATOR = "\n---PAGE BREAK---\n"


def get_file_type(path: Path) -> str | None:
    """
    Get file type from extension.

    Args:
        path: File path

    Returns:
        File type or None if unsupported
    """
    suffix = path.suffix.lower()
    types = {
        ".pdf": "pdf",
        ".txt": "txt",
        ".md": "md",
        ".markdown": "md",
        ".text": "txt",
    }
    return types.get(suffix)


def read_pdf(path: Path) -> tuple[str, dict[str, str | int]]:
    """
    Read PDF file and extract text.

    Args:
        path: Path to PDF file

    Returns:
        Tuple of (text_with_page_separators, metadata)
    """
    reader = PdfReader(path)

    # Extract metadata
    metadata: dict[str, str | int] = {}
    if reader.metadata:
        if reader.metadata.title:
            metadata["pdf_title"] = reader.metadata.title
        if reader.metadata.author:
            metadata["pdf_author"] = reader.metadata.author

    metadata["page_count"] = len(reader.pages)

    # Extract text page by page
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())

    # Join with page separators
    content = PAGE_SEPARATOR.join(pages)

    return content, metadata


def read_text_file(path: Path) -> str:
    """
    Read text or markdown file.

    Args:
        path: Path to file

    Returns:
        File content
    """
    return path.read_text(encoding="utf-8")


async def ingest_file(
    path: str | Path,
    title: str | None = None,
    tags: list[str] | None = None,
    settings: Settings | None = None,
) -> IngestResult:
    """
    Ingest a local file (PDF, TXT, MD).

    1. Read file content
    2. Validate content
    3. Chunk appropriately (page-based for PDF, recursive for others)
    4. Generate embeddings
    5. Create Obsidian note (reference only - doesn't copy file)
    6. Store in database

    Args:
        path: Path to file
        title: Optional title override
        tags: Optional tags
        settings: Optional settings override

    Returns:
        IngestResult with success/failure info
    """
    settings = settings or get_settings()
    path = Path(path).resolve()

    # Security: Validate filename
    if not is_safe_filename(path.name):
        logger.warning(f"Unsafe filename rejected: {path.name}")
        return IngestResult(
            success=False,
            error="Invalid filename",
        )

    # Check file exists
    if not path.exists():
        return IngestResult(
            success=False,
            error=f"File not found: {path}",
        )

    # Security: Ensure it's a regular file (not symlink, device, etc.)
    if not path.is_file():
        logger.warning(f"Non-regular file rejected: {path}")
        return IngestResult(
            success=False,
            error="Path is not a regular file",
        )

    # Check file type
    file_type = get_file_type(path)
    if not file_type:
        return IngestResult(
            success=False,
            error=f"Unsupported file type: {path.suffix}",
        )

    try:
        # Read file
        metadata: dict[str, str | int] = {"source_path": str(path)}

        if file_type == "pdf":
            content, pdf_meta = read_pdf(path)
            metadata.update(pdf_meta)
            strategy = ChunkingStrategy.PAGE
        else:
            content = read_text_file(path)
            metadata["file_size"] = path.stat().st_size
            strategy = ChunkingStrategy.RECURSIVE

        # Validate content
        validation = validate_content(content, min_length=50)  # Lower threshold for files
        if not validation.valid:
            error_msg = validation.error.value if validation.error else "Unknown validation error"
            return IngestResult(
                success=False,
                error=f"Content validation failed: {error_msg}",
            )

        # Determine title (extract from ORIGINAL content to get YAML frontmatter)
        final_title = title
        if not final_title:
            # Try to extract from original content (includes YAML frontmatter)
            final_title = extract_title_from_content(content)
        if not final_title:
            # Use filename without extension
            final_title = path.stem

        # Chunk content
        chunks = chunk_content(validation.content, strategy=strategy)

        if not chunks:
            return IngestResult(
                success=False,
                error="No chunks generated from content",
            )

        # Generate embeddings
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = await embed_batch(chunk_texts)

        # Create Obsidian note (reference to original file)
        note_content = f"**Source file:** `{path}`\n\n{validation.content}"

        note_path = create_note(
            content_type="file",
            title=final_title,
            content=note_content,
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
            content_type="file",
            title=final_title,
            content_for_hash=validation.content,
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

        return IngestResult(
            success=True,
            content_id=content_id,
            filepath=note_path,
            title=final_title,
            chunks_created=len(chunks),
        )

    except Exception as e:
        return IngestResult(
            success=False,
            error=f"Failed to process file: {e}",
        )


async def ingest_files_batch(
    paths: list[str | Path],
    tags: list[str] | None = None,
    settings: Settings | None = None,
) -> list[IngestResult]:
    """
    Ingest multiple files.

    Args:
        paths: List of file paths
        tags: Optional tags to apply to all
        settings: Optional settings override

    Returns:
        List of IngestResult for each file
    """
    results = []
    for path in paths:
        result = await ingest_file(path, tags=tags, settings=settings)
        results.append(result)
    return results


def scan_directory(
    directory: str | Path,
    recursive: bool = False,
) -> list[Path]:
    """
    Scan directory for supported files.

    Args:
        directory: Directory to scan
        recursive: Whether to scan subdirectories

    Returns:
        List of supported file paths
    """
    directory = Path(directory)
    if not directory.is_dir():
        return []

    supported = {".pdf", ".txt", ".md", ".markdown", ".text"}
    files: list[Path] = []

    if recursive:
        for ext in supported:
            files.extend(directory.rglob(f"*{ext}"))
    else:
        for ext in supported:
            files.extend(directory.glob(f"*{ext}"))

    return sorted(files)
