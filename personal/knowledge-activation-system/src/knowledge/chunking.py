"""Adaptive content chunking strategies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from langchain_text_splitters import RecursiveCharacterTextSplitter


class ChunkingStrategy(Enum):
    """Chunking strategy types."""

    YOUTUBE = "youtube"  # Timestamp-based (~3 min segments)
    SEMANTIC = "semantic"  # Paragraph-based (for articles/bookmarks)
    PAGE = "page"  # Page-level (for PDFs)
    RECURSIVE = "recursive"  # General fallback


@dataclass
class Chunk:
    """A chunk of content with metadata."""

    text: str
    index: int
    source_ref: str | None = None  # e.g., "timestamp:3:45" or "page:12"
    start_char: int | None = None
    end_char: int | None = None

    @property
    def word_count(self) -> int:
        """Word count of chunk."""
        return len(self.text.split())


@dataclass
class ChunkingConfig:
    """Configuration for chunking."""

    chunk_size: int = 400  # tokens (approximate chars / 4)
    chunk_overlap: int = 60  # 15% overlap
    min_chunk_size: int = 50  # minimum chunk size


# Default configs by content type
DEFAULT_CONFIGS = {
    ChunkingStrategy.YOUTUBE: ChunkingConfig(
        chunk_size=500,  # ~3 minutes of speech
        chunk_overlap=50,
        min_chunk_size=100,
    ),
    ChunkingStrategy.SEMANTIC: ChunkingConfig(
        chunk_size=512,
        chunk_overlap=77,  # ~15%
        min_chunk_size=100,
    ),
    ChunkingStrategy.PAGE: ChunkingConfig(
        chunk_size=1000,  # Larger for page content
        chunk_overlap=100,
        min_chunk_size=200,
    ),
    ChunkingStrategy.RECURSIVE: ChunkingConfig(
        chunk_size=400,
        chunk_overlap=60,
        min_chunk_size=50,
    ),
}


def chunk_content(
    content: str,
    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
    config: ChunkingConfig | None = None,
) -> list[Chunk]:
    """
    Chunk content using the specified strategy.

    Args:
        content: Content text to chunk
        strategy: Chunking strategy to use
        config: Optional custom configuration

    Returns:
        List of Chunk objects
    """
    config = config or DEFAULT_CONFIGS.get(strategy, DEFAULT_CONFIGS[ChunkingStrategy.RECURSIVE])

    if strategy == ChunkingStrategy.YOUTUBE:
        return chunk_youtube_transcript(content, config)
    elif strategy == ChunkingStrategy.SEMANTIC:
        return chunk_semantic(content, config)
    elif strategy == ChunkingStrategy.PAGE:
        return chunk_by_pages(content, config)
    else:
        return chunk_recursive(content, config)


def chunk_youtube_transcript(
    content: str,
    config: ChunkingConfig,
) -> list[Chunk]:
    """
    Chunk YouTube transcript by timestamps.

    Expects content in format:
    [00:00] Text here
    [03:45] More text
    Or just plain text (falls back to recursive)

    Args:
        content: Transcript content
        config: Chunking configuration

    Returns:
        List of chunks with timestamp source refs
    """
    # Parse timestamps
    timestamp_pattern = r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*"
    segments = re.split(timestamp_pattern, content)

    # If no timestamps found, fall back to recursive
    if len(segments) <= 1:
        return chunk_recursive(content, config)

    chunks: list[Chunk] = []
    current_text = ""
    current_timestamp = "0:00"
    char_pos = 0

    # segments alternates: [text_before, timestamp1, text1, timestamp2, text2, ...]
    i = 0
    while i < len(segments):
        segment = segments[i].strip()

        if re.match(r"^\d{1,2}:\d{2}(?::\d{2})?$", segment):
            # This is a timestamp
            if current_text.strip():
                # Save accumulated text
                start_char = char_pos - len(current_text)
                chunks.append(
                    Chunk(
                        text=current_text.strip(),
                        index=len(chunks),
                        source_ref=f"timestamp:{current_timestamp}",
                        start_char=max(0, start_char),
                        end_char=char_pos,
                    )
                )
                current_text = ""

            current_timestamp = segment
        else:
            current_text += segment + " "
            char_pos += len(segment) + 1

        i += 1

    # Don't forget the last segment
    if current_text.strip():
        chunks.append(
            Chunk(
                text=current_text.strip(),
                index=len(chunks),
                source_ref=f"timestamp:{current_timestamp}",
                start_char=max(0, char_pos - len(current_text)),
                end_char=char_pos,
            )
        )

    # Merge small chunks
    return merge_small_chunks(chunks, config.min_chunk_size)


def chunk_semantic(
    content: str,
    config: ChunkingConfig,
) -> list[Chunk]:
    """
    Chunk content semantically by paragraphs.

    Tries to keep paragraphs together, splitting only when necessary.

    Args:
        content: Content text
        config: Chunking configuration

    Returns:
        List of chunks
    """
    # Split by double newlines (paragraphs)
    paragraphs = re.split(r"\n\s*\n", content)

    chunks: list[Chunk] = []
    current_chunk = ""
    current_start = 0
    char_pos = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If paragraph alone is too big, use recursive split
        if len(para) > config.chunk_size * 4:  # Approximate tokens to chars
            # Split this paragraph
            sub_chunks = chunk_recursive(para, config)
            for sub in sub_chunks:
                sub.start_char = char_pos + (sub.start_char or 0)
                sub.end_char = char_pos + (sub.end_char or len(sub.text))
                sub.index = len(chunks)
                chunks.append(sub)
            char_pos += len(para) + 2
            continue

        # Check if adding this paragraph exceeds chunk size
        test_chunk = current_chunk + "\n\n" + para if current_chunk else para
        if len(test_chunk) > config.chunk_size * 4:
            # Save current chunk and start new one
            if current_chunk:
                chunks.append(
                    Chunk(
                        text=current_chunk,
                        index=len(chunks),
                        start_char=current_start,
                        end_char=char_pos,
                    )
                )
            current_chunk = para
            current_start = char_pos
        else:
            current_chunk = test_chunk

        char_pos += len(para) + 2

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(
            Chunk(
                text=current_chunk,
                index=len(chunks),
                start_char=current_start,
                end_char=char_pos,
            )
        )

    return merge_small_chunks(chunks, config.min_chunk_size)


def chunk_by_pages(
    content: str,
    config: ChunkingConfig,
    page_separator: str = "\n---PAGE BREAK---\n",
) -> list[Chunk]:
    """
    Chunk content by pages.

    Used for PDFs where page structure should be preserved.

    Args:
        content: Content with page separators
        config: Chunking configuration
        page_separator: String that separates pages

    Returns:
        List of chunks with page source refs
    """
    pages = content.split(page_separator)

    chunks: list[Chunk] = []
    char_pos = 0

    for page_num, page_content in enumerate(pages, start=1):
        page_content = page_content.strip()
        if not page_content:
            continue

        # If page is too large, split it
        if len(page_content) > config.chunk_size * 4:
            sub_chunks = chunk_recursive(page_content, config)
            for sub in sub_chunks:
                sub.source_ref = f"page:{page_num}"
                sub.start_char = char_pos + (sub.start_char or 0)
                sub.end_char = char_pos + (sub.end_char or len(sub.text))
                sub.index = len(chunks)
                chunks.append(sub)
        else:
            chunks.append(
                Chunk(
                    text=page_content,
                    index=len(chunks),
                    source_ref=f"page:{page_num}",
                    start_char=char_pos,
                    end_char=char_pos + len(page_content),
                )
            )

        char_pos += len(page_content) + len(page_separator)

    return chunks


def chunk_recursive(
    content: str,
    config: ChunkingConfig,
) -> list[Chunk]:
    """
    Chunk content using recursive character text splitter.

    General-purpose chunking that respects sentence/paragraph boundaries.

    Args:
        content: Content text
        config: Chunking configuration

    Returns:
        List of chunks
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size * 4,  # Approximate tokens to chars
        chunk_overlap=config.chunk_overlap * 4,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True,
    )

    texts = splitter.split_text(content)

    chunks: list[Chunk] = []
    char_pos = 0

    for i, text in enumerate(texts):
        # Find actual position in content
        try:
            start = content.index(text, char_pos)
        except ValueError:
            start = char_pos

        chunks.append(
            Chunk(
                text=text,
                index=i,
                start_char=start,
                end_char=start + len(text),
            )
        )
        char_pos = start + len(text) - (config.chunk_overlap * 4)

    return chunks


def merge_small_chunks(chunks: list[Chunk], min_size: int) -> list[Chunk]:
    """
    Merge chunks that are too small.

    Args:
        chunks: List of chunks
        min_size: Minimum chunk size in characters

    Returns:
        List of merged chunks
    """
    if not chunks:
        return []

    merged: list[Chunk] = []
    current = chunks[0]

    for next_chunk in chunks[1:]:
        if len(current.text) < min_size:
            # Merge with next
            current = Chunk(
                text=current.text + "\n\n" + next_chunk.text,
                index=current.index,
                source_ref=current.source_ref,  # Keep first source ref
                start_char=current.start_char,
                end_char=next_chunk.end_char,
            )
        else:
            merged.append(current)
            current = next_chunk

    merged.append(current)

    # Re-index
    for i, chunk in enumerate(merged):
        chunk.index = i

    return merged


def get_strategy_for_content_type(content_type: str) -> ChunkingStrategy:
    """
    Get the appropriate chunking strategy for a content type.

    Args:
        content_type: Content type (youtube, bookmark, file, note)

    Returns:
        Appropriate chunking strategy
    """
    strategies = {
        "youtube": ChunkingStrategy.YOUTUBE,
        "bookmark": ChunkingStrategy.SEMANTIC,
        "pdf": ChunkingStrategy.PAGE,
        "file": ChunkingStrategy.RECURSIVE,
        "note": ChunkingStrategy.SEMANTIC,
    }
    return strategies.get(content_type, ChunkingStrategy.RECURSIVE)
