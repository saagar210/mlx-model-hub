"""File ingestion (PDF, TXT, MD).

Supports secure ingestion of local files with:
- Path traversal protection
- File type validation
- Content validation
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from knowledge.autotag import extract_tags
from knowledge.chunking import ChunkingStrategy, chunk_content
from knowledge.config import Settings, get_settings
from knowledge.db import get_db
from knowledge.embeddings import embed_batch
from knowledge.entity_extraction import extract_entities
from knowledge.ingest import IngestResult
from knowledge.logging import get_logger
from knowledge.obsidian import create_note, get_relative_path
from knowledge.security import is_safe_filename
from knowledge.validation import extract_frontmatter_fields, extract_title_from_content, validate_content

logger = get_logger(__name__)

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
    auto_extract_entities: bool = True,
    auto_tag: bool = False,
) -> IngestResult:
    """
    Ingest a local file (PDF, TXT, MD).

    1. Read file content
    2. Validate content
    3. Auto-tag content using LLM (optional)
    4. Chunk appropriately (page-based for PDF, recursive for others)
    5. Generate embeddings
    6. Create Obsidian note (reference only - doesn't copy file)
    7. Store in database
    8. Extract entities (optional, default True)

    Args:
        path: Path to file
        title: Optional title override
        tags: Optional tags
        settings: Optional settings override
        auto_extract_entities: Auto-extract entities after ingest (default True)
        auto_tag: Auto-generate tags using LLM (default False - can be slow)

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

        # Extract frontmatter fields (title, namespace, tags)
        frontmatter_fields = extract_frontmatter_fields(content)
        if frontmatter_fields.get("namespace"):
            metadata["namespace"] = frontmatter_fields["namespace"]

        # Merge tags from frontmatter with provided tags
        final_tags = list(tags) if tags else []
        if frontmatter_fields.get("tags"):
            frontmatter_tags = frontmatter_fields["tags"]
            if isinstance(frontmatter_tags, list):
                final_tags.extend(frontmatter_tags)

        # Auto-tag if enabled and we don't have many tags already
        if auto_tag and len(final_tags) < 3:
            try:
                # Use filename as preliminary title for tagging
                preliminary_title = title or path.stem
                auto_tags = await extract_tags(preliminary_title, validation.content)
                if auto_tags:
                    final_tags.extend(auto_tags)
                    logger.debug(
                        "auto_tags_generated",
                        path=str(path),
                        tags=auto_tags,
                    )
            except Exception as e:
                # Don't fail ingestion if auto-tagging fails
                logger.warning(
                    "auto_tagging_failed",
                    path=str(path),
                    error=str(e),
                )

        final_tags = list(dict.fromkeys(final_tags))  # Dedupe preserving order

        # Determine title (extract from ORIGINAL content to get YAML frontmatter)
        final_title = title
        if not final_title:
            # Try to extract from frontmatter first
            final_title = frontmatter_fields.get("title") if isinstance(frontmatter_fields.get("title"), str) else None
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
            tags=final_tags if final_tags else None,
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
            tags=final_tags if final_tags else None,
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

        # Extract entities if enabled
        entities_extracted = 0
        if auto_extract_entities:
            try:
                extraction_result = await extract_entities(
                    title=final_title,
                    content=validation.content,
                )
                if extraction_result.success and extraction_result.entities:
                    # Store entities in database
                    entity_records = [
                        {
                            "name": e.name,
                            "entity_type": e.entity_type,
                            "confidence": e.confidence,
                        }
                        for e in extraction_result.entities
                    ]
                    entity_ids = await db.insert_entities_batch(content_id, entity_records)
                    entities_extracted = len(entity_ids)

                    # Store relationships
                    if extraction_result.relationships:
                        # Build name to ID mapping
                        name_to_id = {}
                        for eid, entity in zip(entity_ids, extraction_result.entities):
                            name_to_id[entity.name.lower()] = eid

                        for rel in extraction_result.relationships:
                            from_id = name_to_id.get(rel.from_entity.lower())
                            to_id = name_to_id.get(rel.to_entity.lower())
                            if from_id and to_id:
                                await db.insert_relationship(
                                    from_entity_id=from_id,
                                    to_entity_id=to_id,
                                    relation_type=rel.relation_type,
                                    confidence=rel.confidence,
                                )

                    logger.debug(
                        "entities_auto_extracted",
                        content_id=str(content_id),
                        entity_count=entities_extracted,
                    )
            except Exception as e:
                # Don't fail ingestion if entity extraction fails
                logger.warning(
                    "entity_extraction_failed",
                    content_id=str(content_id),
                    error=str(e),
                )

        return IngestResult(
            success=True,
            content_id=content_id,
            filepath=note_path,
            title=final_title,
            chunks_created=len(chunks),
            entities_extracted=entities_extracted,
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
    auto_tag: bool = False,
) -> list[IngestResult]:
    """
    Ingest multiple files.

    Args:
        paths: List of file paths
        tags: Optional tags to apply to all
        settings: Optional settings override
        auto_tag: Auto-generate tags using LLM (default False)

    Returns:
        List of IngestResult for each file
    """
    results = []
    for path in paths:
        result = await ingest_file(path, tags=tags, settings=settings, auto_tag=auto_tag)
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
