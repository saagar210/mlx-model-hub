"""Extraction service that coordinates multiple extractors."""

from __future__ import annotations

import logging
from typing import Any

from knowledge_seeder.extractors.base import BaseExtractor, ExtractionResult
from knowledge_seeder.extractors.arxiv import ArxivExtractor
from knowledge_seeder.extractors.file import FileExtractor
from knowledge_seeder.extractors.github import GitHubExtractor
from knowledge_seeder.extractors.url import URLExtractor
from knowledge_seeder.extractors.youtube import YouTubeExtractor
from knowledge_seeder.models import Source, SourceType

logger = logging.getLogger(__name__)


class ExtractorService:
    """Service that routes extraction to appropriate extractor."""

    def __init__(self) -> None:
        """Initialize extraction service."""
        self._youtube = YouTubeExtractor()
        self._github = GitHubExtractor()
        self._arxiv = ArxivExtractor()
        self._url = URLExtractor()
        self._file = FileExtractor()
        # Order matters: more specific extractors first
        self._extractors: list[BaseExtractor] = [
            self._youtube,  # YouTube videos
            self._arxiv,    # arXiv papers
            self._github,   # GitHub repos
            self._file,     # Local files
            self._url,      # Generic URLs (fallback)
        ]

    async def extract(self, source: Source) -> ExtractionResult:
        """Extract content from a source."""
        url = source.url

        # Find appropriate extractor
        extractor = self._get_extractor(url, source.source_type)

        if extractor is None:
            raise ValueError(f"No extractor available for: {url}")

        # Extract content
        result = await extractor.extract(url)

        # Add source metadata
        result.metadata["source_name"] = source.name
        result.metadata["source_tags"] = source.tags
        result.metadata["source_namespace"] = source.namespace

        return result

    async def extract_url(self, url: str) -> ExtractionResult:
        """Extract content from a URL (auto-detect type)."""
        extractor = self._get_extractor(url)

        if extractor is None:
            raise ValueError(f"No extractor available for: {url}")

        return await extractor.extract(url)

    def _get_extractor(
        self,
        url: str,
        source_type: SourceType | None = None,
    ) -> BaseExtractor | None:
        """Get the appropriate extractor for a URL."""
        # If source type is specified, use that
        if source_type == SourceType.YOUTUBE:
            return self._youtube
        if source_type == SourceType.FILE:
            return self._file
        if source_type in (SourceType.URL, SourceType.GITHUB, SourceType.ARXIV):
            return self._url

        # Auto-detect
        for extractor in self._extractors:
            if extractor.can_handle(url):
                return extractor

        return None

    def detect_type(self, url: str) -> SourceType | None:
        """Detect the type of a source URL."""
        if self._youtube.can_handle(url):
            return SourceType.YOUTUBE
        if self._file.can_handle(url):
            return SourceType.FILE
        if self._url.can_handle(url):
            return SourceType.URL
        return None

    async def check_accessible(self, source: Source) -> tuple[bool, str | None]:
        """Check if a source is accessible."""
        url = source.url
        extractor = self._get_extractor(url, source.source_type)

        if extractor is None:
            return False, "No extractor available"

        # Use extractor-specific accessibility check
        if hasattr(extractor, "check_accessible"):
            return await extractor.check_accessible(url)

        # Fallback: try to extract
        try:
            await extractor.extract(url)
            return True, None
        except Exception as e:
            return False, str(e)

    async def close(self) -> None:
        """Clean up resources."""
        await self._url.close()

    async def __aenter__(self) -> "ExtractorService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
