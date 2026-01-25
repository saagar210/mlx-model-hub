"""Ingestor service for coordinating content ingestion."""

from __future__ import annotations

import logging
from typing import Any

from knowledge_engine.ingestors.base import BaseIngestor, IngestResult
from knowledge_engine.ingestors.url import URLIngestor
from knowledge_engine.ingestors.file import FileIngestor
from knowledge_engine.ingestors.youtube import YouTubeIngestor

logger = logging.getLogger(__name__)


class IngestorService:
    """
    Coordinates content ingestion from various sources.

    Automatically detects source type and routes to appropriate ingestor.
    """

    def __init__(self) -> None:
        self._ingestors: list[BaseIngestor] = [
            YouTubeIngestor(),  # Check YouTube first (before general URL)
            URLIngestor(),
            FileIngestor(),
        ]

    async def ingest(self, source: str) -> IngestResult:
        """
        Ingest content from any supported source.

        Automatically detects the source type and uses appropriate ingestor.

        Args:
            source: Source identifier (URL, file path, video ID)

        Returns:
            IngestResult with extracted content

        Raises:
            ValueError: If source type is not supported
        """
        for ingestor in self._ingestors:
            if ingestor.can_handle(source):
                logger.info(
                    "Using %s for source: %s",
                    ingestor.__class__.__name__,
                    source[:100]
                )
                return await ingestor.ingest(source)

        raise ValueError(
            f"Unsupported source type: {source}. "
            "Supported: URLs, YouTube videos, local files (txt, md, pdf, etc.)"
        )

    def detect_type(self, source: str) -> str | None:
        """
        Detect the source type without ingesting.

        Returns:
            Source type name or None if not supported
        """
        for ingestor in self._ingestors:
            if ingestor.can_handle(source):
                return ingestor.__class__.__name__.replace("Ingestor", "").lower()
        return None

    async def ingest_batch(
        self,
        sources: list[str],
        skip_errors: bool = True,
    ) -> list[tuple[str, IngestResult | Exception]]:
        """
        Ingest multiple sources.

        Args:
            sources: List of source identifiers
            skip_errors: If True, continue on errors; if False, raise on first error

        Returns:
            List of (source, result/exception) tuples
        """
        results = []

        for source in sources:
            try:
                result = await self.ingest(source)
                results.append((source, result))
            except Exception as e:
                logger.error("Failed to ingest %s: %s", source, e)
                if skip_errors:
                    results.append((source, e))
                else:
                    raise

        return results

    async def close(self) -> None:
        """Close all ingestor resources."""
        for ingestor in self._ingestors:
            if hasattr(ingestor, "close"):
                await ingestor.close()
