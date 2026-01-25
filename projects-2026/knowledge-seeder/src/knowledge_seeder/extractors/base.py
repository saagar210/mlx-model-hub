"""Base extractor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from knowledge_seeder.models import SourceType


class ExtractionResult(BaseModel):
    """Result of content extraction."""

    content: str = Field(..., description="Extracted content")
    title: str | None = Field(default=None, description="Extracted title")
    source_url: str = Field(..., description="Source URL")
    source_type: SourceType = Field(..., description="Type of source")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extraction metadata")

    @property
    def content_length(self) -> int:
        """Get content length."""
        return len(self.content)

    @property
    def is_valid(self) -> bool:
        """Check if extraction result is valid (has sufficient content)."""
        return len(self.content) >= 100

    @property
    def preview(self) -> str:
        """Get a preview of the content."""
        if len(self.content) <= 200:
            return self.content
        return self.content[:200] + "..."


class BaseExtractor(ABC):
    """Base class for content extractors."""

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Check if this extractor can handle the given URL."""
        pass

    @abstractmethod
    async def extract(self, url: str) -> ExtractionResult:
        """Extract content from the URL."""
        pass

    async def close(self) -> None:
        """Clean up resources."""
        pass

    async def __aenter__(self) -> "BaseExtractor":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
