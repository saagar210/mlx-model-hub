"""Content ingestion modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID


@dataclass
class IngestResult:
    """Result of content ingestion."""

    success: bool
    content_id: UUID | None = None
    filepath: Path | None = None
    title: str | None = None
    chunks_created: int = 0
    error: str | None = None

    @property
    def message(self) -> str:
        """Human-readable result message."""
        if self.success:
            return f"Ingested '{self.title}' with {self.chunks_created} chunks"
        return f"Failed to ingest: {self.error}"


@dataclass
class ContentMetadata:
    """Metadata for ingested content."""

    title: str
    content_type: str
    url: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    captured_at: datetime | None = None
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "title": self.title,
            "content_type": self.content_type,
            "url": self.url,
            "summary": self.summary,
            "tags": self.tags or [],
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            **(self.extra or {}),
        }
