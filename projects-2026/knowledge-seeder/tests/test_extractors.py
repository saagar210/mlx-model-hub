"""Tests for content extractors."""

from pathlib import Path

import pytest

from knowledge_seeder.extractors.url import URLExtractor
from knowledge_seeder.extractors.youtube import YouTubeExtractor
from knowledge_seeder.extractors.file import FileExtractor
from knowledge_seeder.models import SourceType


class TestURLExtractor:
    """Tests for URL extractor."""

    @pytest.fixture
    def extractor(self):
        return URLExtractor()

    @pytest.mark.parametrize("url,expected", [
        ("https://example.com", True),
        ("http://example.com/path", True),
        ("https://sub.example.com:8080/path?query=1", True),
        ("ftp://example.com", False),
        ("/local/path", False),
        ("not a url", False),
    ])
    def test_can_handle(self, extractor, url, expected):
        """Test URL validation."""
        assert extractor.can_handle(url) == expected


class TestYouTubeExtractor:
    """Tests for YouTube extractor."""

    @pytest.fixture
    def extractor(self):
        return YouTubeExtractor()

    @pytest.mark.parametrize("url,expected_id", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ])
    def test_extract_video_id(self, extractor, url, expected_id):
        """Test video ID extraction."""
        assert extractor._extract_video_id(url) == expected_id

    def test_can_handle(self, extractor):
        """Test YouTube URL detection."""
        assert extractor.can_handle("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert extractor.can_handle("https://youtu.be/dQw4w9WgXcQ")
        assert not extractor.can_handle("https://vimeo.com/123456")


class TestFileExtractor:
    """Tests for file extractor."""

    @pytest.fixture
    def extractor(self):
        return FileExtractor()

    @pytest.fixture
    def sample_file(self, tmp_path):
        """Create a sample text file."""
        content = "This is test content.\n" * 10
        path = tmp_path / "test.txt"
        path.write_text(content)
        return path

    @pytest.fixture
    def sample_code_file(self, tmp_path):
        """Create a sample Python file."""
        # Content must be at least 100 chars to be valid
        content = '''def hello():
    """Say hello to the world."""
    print("Hello, World!")

def goodbye():
    """Say goodbye to the world."""
    print("Goodbye, World!")
'''
        path = tmp_path / "test.py"
        path.write_text(content)
        return path

    def test_can_handle(self, extractor):
        """Test file path detection."""
        assert extractor.can_handle("/path/to/file.txt")
        assert extractor.can_handle("./relative/path.md")
        assert extractor.can_handle("~/home/file.py")
        assert not extractor.can_handle("https://example.com")
        assert not extractor.can_handle("not a path")

    @pytest.mark.asyncio
    async def test_extract_text_file(self, extractor, sample_file):
        """Test extracting text file."""
        result = await extractor.extract(str(sample_file))

        assert result.is_valid
        assert result.source_type == SourceType.FILE
        assert result.title == "test"  # Filename without extension
        assert "test content" in result.content

    @pytest.mark.asyncio
    async def test_extract_code_file(self, extractor, sample_code_file):
        """Test extracting code file."""
        result = await extractor.extract(str(sample_code_file))

        assert result.is_valid
        assert result.source_type == SourceType.FILE
        assert result.metadata["is_code"] is True
        assert result.metadata["extension"] == ".py"

    @pytest.mark.asyncio
    async def test_file_not_found(self, extractor):
        """Test handling missing file."""
        with pytest.raises(ValueError, match="File not found"):
            await extractor.extract("/nonexistent/path.txt")

    @pytest.mark.asyncio
    async def test_unsupported_extension(self, extractor, tmp_path):
        """Test handling unsupported file type."""
        path = tmp_path / "test.xyz"
        path.write_text("content")

        with pytest.raises(ValueError, match="Unsupported file type"):
            await extractor.extract(str(path))
