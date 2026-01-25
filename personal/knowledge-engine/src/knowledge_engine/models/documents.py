"""Document models for ingestion and storage."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class DocumentType(str, Enum):
    """Supported document types."""

    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    CODE = "code"
    YOUTUBE = "youtube"
    BOOKMARK = "bookmark"
    NOTE = "note"
    CONVERSATION = "conversation"


class DocumentMetadata(BaseModel):
    """Document metadata for filtering and display."""

    source: str | None = Field(default=None, description="Source URL or path")
    author: str | None = Field(default=None, description="Author name")
    created_at: datetime | None = Field(default=None, description="Original creation date")
    tags: list[str] = Field(default_factory=list, description="User or auto-generated tags")
    language: str = Field(default="en", description="ISO 639-1 language code")
    custom: dict[str, Any] = Field(default_factory=dict, description="Custom metadata fields")


class DocumentCreate(BaseModel):
    """Request model for creating a new document."""

    content: str = Field(..., min_length=1, description="Document content")
    title: str | None = Field(default=None, description="Document title")
    document_type: DocumentType = Field(default=DocumentType.TEXT, description="Document type")
    namespace: str = Field(default="default", description="Namespace for multi-tenancy")
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)


class Document(BaseModel):
    """Full document model with all fields."""

    id: UUID = Field(default_factory=uuid4)
    content: str
    title: str | None = None
    document_type: DocumentType
    namespace: str = "default"
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)

    # System fields
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    chunk_count: int = 0
    embedding_model: str | None = None
    is_deleted: bool = False

    model_config = ConfigDict(from_attributes=True)
