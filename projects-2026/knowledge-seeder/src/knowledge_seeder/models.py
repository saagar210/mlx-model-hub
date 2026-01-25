"""Data models for Knowledge Seeder."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class SourceType(str, Enum):
    """Type of content source."""

    URL = "url"
    YOUTUBE = "youtube"
    GITHUB = "github"
    ARXIV = "arxiv"
    FILE = "file"


class SourceStatus(str, Enum):
    """Status of a source in the state database."""

    PENDING = "pending"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    INGESTING = "ingesting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourcePriority(str, Enum):
    """Priority level for sources."""

    P0 = "P0"  # Critical - refresh weekly
    P1 = "P1"  # Important - refresh bi-weekly
    P2 = "P2"  # Standard - refresh monthly
    P3 = "P3"  # Low - refresh quarterly
    P4 = "P4"  # Evergreen - manual refresh


class SourceLifecycleStatus(str, Enum):
    """Lifecycle status of a source definition."""

    ACTIVE = "active"  # Normal, should be synced
    DEPRECATED = "deprecated"  # Docs moved/removed, skip during sync
    DISABLED = "disabled"  # Temporarily disabled


class Source(BaseModel):
    """A knowledge source to be ingested."""

    name: str = Field(..., description="Unique identifier for the source")
    url: str = Field(..., description="URL or path to the source")
    source_type: SourceType = Field(default=SourceType.URL, description="Type of source")
    tags: list[str] = Field(default_factory=list, description="Classification tags")
    namespace: str = Field(default="default", description="Target namespace")
    priority: SourcePriority = Field(default=SourcePriority.P2, description="Refresh priority")
    crawl_depth: int = Field(default=1, description="Depth for web crawling")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    placeholder: bool = Field(default=False, description="Placeholder needing real URL")

    # Lifecycle management (per KAS directive 2026-01-13)
    status: SourceLifecycleStatus = Field(default=SourceLifecycleStatus.ACTIVE, description="Lifecycle status")
    deprecated_date: str | None = Field(default=None, description="Date source was deprecated (YYYY-MM-DD)")
    replacement: str | None = Field(default=None, description="Name of replacement source")
    note: str | None = Field(default=None, description="Additional notes about the source")

    @property
    def source_id(self) -> str:
        """Generate a unique ID for this source."""
        return f"{self.namespace}:{self.name}"

    @property
    def is_active(self) -> bool:
        """Check if source should be processed during sync."""
        return self.status == SourceLifecycleStatus.ACTIVE and not self.placeholder


class SourceFile(BaseModel):
    """A YAML source file definition."""

    namespace: str = Field(..., description="Target namespace for all sources")
    refresh_interval: str = Field(default="30d", description="Refresh interval")
    priority: SourcePriority = Field(default=SourcePriority.P2, description="Default priority")
    sources: list[Source] = Field(default_factory=list, description="List of sources")
    project: str | None = Field(default=None, description="Optional project name")
    dependencies: list[str] = Field(default_factory=list, description="Namespace dependencies")


class SourceState(BaseModel):
    """State of a source in the database."""

    source_id: str = Field(..., description="Unique source identifier")
    name: str = Field(..., description="Source name")
    url: str = Field(..., description="Source URL")
    namespace: str = Field(..., description="Target namespace")
    source_type: SourceType = Field(..., description="Type of source")
    status: SourceStatus = Field(default=SourceStatus.PENDING, description="Current status")

    # Extraction state
    content_hash: str | None = Field(default=None, description="Hash of extracted content")
    content_length: int | None = Field(default=None, description="Length of extracted content")
    extracted_at: datetime | None = Field(default=None, description="When content was extracted")

    # Ingestion state
    document_id: str | None = Field(default=None, description="Knowledge Engine document ID")
    chunk_count: int | None = Field(default=None, description="Number of chunks created")
    ingested_at: datetime | None = Field(default=None, description="When ingestion completed")

    # Error tracking
    error_message: str | None = Field(default=None, description="Last error message")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    last_attempt: datetime | None = Field(default=None, description="Last attempt timestamp")

    # Timestamps
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ExtractionResult(BaseModel):
    """Result of content extraction."""

    source_id: str = Field(..., description="Source identifier")
    content: str = Field(..., description="Extracted content")
    title: str | None = Field(default=None, description="Extracted title")
    source_type: SourceType = Field(..., description="Type of source")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extraction metadata")

    @property
    def content_length(self) -> int:
        """Get content length."""
        return len(self.content)

    @property
    def is_valid(self) -> bool:
        """Check if extraction result is valid."""
        return len(self.content) >= 100


class ValidationResult(BaseModel):
    """Result of source validation."""

    source_id: str
    name: str
    url: str
    is_valid: bool = True
    is_accessible: bool | None = None  # None if not checked
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
