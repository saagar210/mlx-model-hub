"""Base ingestor class and common types."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Result of content ingestion."""

    content: str
    title: str | None = None
    source: str | None = None
    source_type: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_valid(self) -> bool:
        """Check if content is valid for indexing."""
        if not self.content:
            return False
        # Skip very short content
        if len(self.content.strip()) < 50:
            return False
        return True


class BaseIngestor(ABC):
    """Abstract base class for content ingestors."""

    @abstractmethod
    async def ingest(self, source: str) -> IngestResult:
        """
        Ingest content from a source.

        Args:
            source: Source identifier (URL, file path, video ID, etc.)

        Returns:
            IngestResult with extracted content
        """
        pass

    @abstractmethod
    def can_handle(self, source: str) -> bool:
        """
        Check if this ingestor can handle the given source.

        Args:
            source: Source identifier

        Returns:
            True if this ingestor can process the source
        """
        pass
