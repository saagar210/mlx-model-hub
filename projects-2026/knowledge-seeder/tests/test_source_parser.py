"""Tests for source parser."""

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from knowledge_seeder.source_parser import SourceParser
from knowledge_seeder.models import SourceType, SourcePriority


@pytest.fixture
def parser():
    """Create parser instance."""
    return SourceParser()


@pytest.fixture
def sample_yaml(tmp_path):
    """Create a sample YAML file."""
    content = dedent("""
        namespace: test
        refresh_interval: 7d
        priority: P1

        sources:
          - name: test-url
            url: https://example.com/docs
            tags: [test, docs]

          - name: test-youtube
            url: https://www.youtube.com/watch?v=dQw4w9WgXcQ
            type: youtube
            tags: [video, tutorial]

          - name: test-github
            url: https://github.com/owner/repo
            type: github
            tags: [code, example]
    """)
    path = tmp_path / "test.yaml"
    path.write_text(content)
    return path


class TestSourceParser:
    """Tests for SourceParser."""

    def test_parse_file(self, parser, sample_yaml):
        """Test parsing a YAML file."""
        result = parser.parse_file(sample_yaml)

        assert result.namespace == "test"
        assert result.refresh_interval == "7d"
        assert result.priority == SourcePriority.P1
        assert len(result.sources) == 3

    def test_parse_source_types(self, parser, sample_yaml):
        """Test source type detection."""
        result = parser.parse_file(sample_yaml)

        # Find sources by name
        sources = {s.name: s for s in result.sources}

        assert sources["test-url"].source_type == SourceType.URL
        assert sources["test-youtube"].source_type == SourceType.YOUTUBE
        assert sources["test-github"].source_type == SourceType.GITHUB

    def test_auto_detect_youtube(self, parser):
        """Test automatic YouTube URL detection."""
        urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        ]
        for url in urls:
            assert parser._is_youtube(url), f"Should detect as YouTube: {url}"

    def test_auto_detect_github(self, parser):
        """Test automatic GitHub URL detection."""
        assert parser._is_github("https://github.com/owner/repo")
        assert parser._is_github("github.com/owner/repo")

    def test_auto_detect_arxiv(self, parser):
        """Test automatic arXiv URL detection."""
        assert parser._is_arxiv("https://arxiv.org/abs/2312.10997")
        assert parser._is_arxiv("arxiv.org/abs/2312.10997")

    def test_source_id_generation(self, parser, sample_yaml):
        """Test source ID generation."""
        result = parser.parse_file(sample_yaml)
        source = result.sources[0]

        assert source.source_id == "test:test-url"

    def test_validate_source(self, parser):
        """Test source validation."""
        from knowledge_seeder.models import Source

        # Valid source
        source = Source(
            name="test",
            url="https://example.com",
            tags=["test"],
        )
        result = parser.validate_source(source)
        assert result.is_valid

        # Placeholder source
        source = Source(
            name="placeholder",
            url="https://example.com",
            placeholder=True,
        )
        result = parser.validate_source(source)
        assert not result.is_valid

    def test_count_sources(self, parser, sample_yaml):
        """Test counting sources."""
        counts = parser.count_sources([sample_yaml])

        assert counts["total"] == 3
        assert counts["by_namespace"]["test"] == 3
        assert counts["placeholders"] == 0


class TestYouTubeDetection:
    """Tests for YouTube URL detection."""

    @pytest.fixture
    def parser(self):
        return SourceParser()

    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
        ("https://youtu.be/dQw4w9WgXcQ", True),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", True),
        # Note: bare video IDs require the YouTube extractor, not source_parser
        ("https://example.com", False),
        ("https://vimeo.com/123456", False),
    ])
    def test_youtube_detection(self, parser, url, expected):
        """Test YouTube URL detection."""
        assert parser._is_youtube(url) == expected
