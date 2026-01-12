"""Tests for content chunking."""

import pytest

from knowledge.chunking import (
    Chunk,
    ChunkingConfig,
    ChunkingStrategy,
    chunk_by_pages,
    chunk_content,
    chunk_recursive,
    chunk_semantic,
    chunk_youtube_transcript,
    get_strategy_for_content_type,
    merge_small_chunks,
)


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_chunk_creation(self):
        """Test creating a chunk."""
        chunk = Chunk(
            text="Sample text",
            index=0,
            source_ref="timestamp:0:00",
            start_char=0,
            end_char=11,
        )

        assert chunk.text == "Sample text"
        assert chunk.index == 0
        assert chunk.source_ref == "timestamp:0:00"

    def test_word_count(self):
        """Test word count property."""
        chunk = Chunk(text="This is a sample text with seven words", index=0)
        assert chunk.word_count == 8


class TestChunkingConfig:
    """Tests for ChunkingConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ChunkingConfig()

        assert config.chunk_size == 400
        assert config.chunk_overlap == 60
        assert config.min_chunk_size == 50


class TestChunkYoutubeTranscript:
    """Tests for YouTube transcript chunking."""

    def test_basic_transcript_chunking(self):
        """Test chunking a transcript with timestamps."""
        transcript = """[0:00] Hello and welcome to this video.
[0:15] Today we'll be discussing machine learning.
[3:00] Let's start with the basics of neural networks.
[6:30] Now we'll cover deep learning concepts."""

        config = ChunkingConfig(min_chunk_size=10)
        chunks = chunk_youtube_transcript(transcript, config)

        assert len(chunks) > 0
        assert all(chunk.source_ref.startswith("timestamp:") for chunk in chunks)

    def test_no_timestamps_fallback(self):
        """Test fallback when no timestamps present."""
        transcript = "This is a transcript without any timestamps. " * 20

        config = ChunkingConfig()
        chunks = chunk_youtube_transcript(transcript, config)

        assert len(chunks) > 0
        # Should fall back to recursive, no timestamp refs
        assert chunks[0].source_ref is None

    def test_chunk_source_refs(self):
        """Test that source refs contain correct timestamps."""
        transcript = "[0:00] First segment.\n[5:30] Second segment."

        config = ChunkingConfig(min_chunk_size=5)
        chunks = chunk_youtube_transcript(transcript, config)

        source_refs = [c.source_ref for c in chunks]
        assert any("0:00" in ref for ref in source_refs)


class TestChunkSemantic:
    """Tests for semantic chunking."""

    def test_paragraph_chunking(self):
        """Test chunking by paragraphs."""
        content = """First paragraph with some content.

Second paragraph with more content.

Third paragraph to round things out."""

        config = ChunkingConfig(chunk_size=500, min_chunk_size=10)
        chunks = chunk_semantic(content, config)

        assert len(chunks) > 0
        # Check that paragraphs are preserved
        assert any("First paragraph" in c.text for c in chunks)

    def test_long_paragraph_splitting(self):
        """Test that long paragraphs are split."""
        long_para = "This is a very long paragraph. " * 100

        config = ChunkingConfig(chunk_size=100, min_chunk_size=10)
        chunks = chunk_semantic(long_para, config)

        assert len(chunks) > 1


class TestChunkByPages:
    """Tests for page-based chunking."""

    def test_page_chunking(self):
        """Test chunking by page separators."""
        content = """Page one content here.
---PAGE BREAK---
Page two content here.
---PAGE BREAK---
Page three content here."""

        config = ChunkingConfig(min_chunk_size=10)
        chunks = chunk_by_pages(content, config)

        assert len(chunks) == 3
        assert chunks[0].source_ref == "page:1"
        assert chunks[1].source_ref == "page:2"
        assert chunks[2].source_ref == "page:3"

    def test_long_page_splitting(self):
        """Test that long pages are split."""
        long_page = "Content " * 500
        content = f"{long_page}---PAGE BREAK---Short page."

        config = ChunkingConfig(chunk_size=100, min_chunk_size=10)
        chunks = chunk_by_pages(content, config)

        # First page should be split into multiple chunks
        page1_chunks = [c for c in chunks if c.source_ref == "page:1"]
        assert len(page1_chunks) > 1


class TestChunkRecursive:
    """Tests for recursive chunking."""

    def test_basic_recursive_chunking(self):
        """Test basic recursive chunking."""
        content = "This is a test. " * 100

        config = ChunkingConfig(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
        chunks = chunk_recursive(content, config)

        assert len(chunks) > 1

    def test_preserves_sentences(self):
        """Test that sentences are preserved when possible."""
        content = "First sentence. Second sentence. Third sentence. Fourth sentence."

        config = ChunkingConfig(chunk_size=100, chunk_overlap=10, min_chunk_size=10)
        chunks = chunk_recursive(content, config)

        # Check that chunks end at sentence boundaries when possible
        for chunk in chunks:
            # Most chunks should end with a period or be at the end
            text = chunk.text.strip()
            assert text.endswith(".") or chunk == chunks[-1]


class TestMergeSmallChunks:
    """Tests for small chunk merging."""

    def test_merge_small_chunks(self):
        """Test that small chunks are merged."""
        chunks = [
            Chunk(text="A", index=0),
            Chunk(text="B", index=1),
            Chunk(text="This is a longer chunk that should not trigger merge", index=2),
        ]

        merged = merge_small_chunks(chunks, min_size=10)

        # First two should be merged
        assert len(merged) < len(chunks)

    def test_no_merge_needed(self):
        """Test when no merging is needed."""
        chunks = [
            Chunk(text="This is chunk one with enough text", index=0),
            Chunk(text="This is chunk two with enough text", index=1),
        ]

        merged = merge_small_chunks(chunks, min_size=10)

        assert len(merged) == 2

    def test_reindexing(self):
        """Test that chunks are re-indexed after merge."""
        chunks = [
            Chunk(text="A", index=0),
            Chunk(text="B", index=1),
            Chunk(text="C", index=2),
        ]

        merged = merge_small_chunks(chunks, min_size=10)

        # Check indices are sequential
        for i, chunk in enumerate(merged):
            assert chunk.index == i


class TestGetStrategyForContentType:
    """Tests for strategy selection."""

    def test_youtube_strategy(self):
        """Test YouTube content type."""
        strategy = get_strategy_for_content_type("youtube")
        assert strategy == ChunkingStrategy.YOUTUBE

    def test_bookmark_strategy(self):
        """Test bookmark content type."""
        strategy = get_strategy_for_content_type("bookmark")
        assert strategy == ChunkingStrategy.SEMANTIC

    def test_pdf_strategy(self):
        """Test PDF content type."""
        strategy = get_strategy_for_content_type("pdf")
        assert strategy == ChunkingStrategy.PAGE

    def test_file_strategy(self):
        """Test file content type."""
        strategy = get_strategy_for_content_type("file")
        assert strategy == ChunkingStrategy.RECURSIVE

    def test_unknown_strategy(self):
        """Test unknown content type defaults to recursive."""
        strategy = get_strategy_for_content_type("unknown")
        assert strategy == ChunkingStrategy.RECURSIVE


class TestChunkContent:
    """Tests for main chunk_content function."""

    def test_with_youtube_strategy(self):
        """Test chunking with YouTube strategy."""
        transcript = "[0:00] Hello world. [1:00] More content here."

        chunks = chunk_content(transcript, strategy=ChunkingStrategy.YOUTUBE)

        assert len(chunks) > 0

    def test_with_semantic_strategy(self):
        """Test chunking with semantic strategy."""
        content = "Paragraph one.\n\nParagraph two.\n\nParagraph three."

        chunks = chunk_content(content, strategy=ChunkingStrategy.SEMANTIC)

        assert len(chunks) > 0

    def test_with_custom_config(self):
        """Test chunking with custom configuration."""
        content = "Test content " * 50

        custom_config = ChunkingConfig(chunk_size=100, chunk_overlap=10, min_chunk_size=5)
        chunks = chunk_content(content, config=custom_config)

        assert len(chunks) > 1
