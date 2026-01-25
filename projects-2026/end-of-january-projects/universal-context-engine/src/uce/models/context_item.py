"""Core context item model - unified schema for all context sources."""

import hashlib
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from .temporal import BiTemporalMetadata


class RelevanceSignals(BaseModel):
    """Signals used for ranking context items in search results."""

    recency: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Recency score (0-1), based on age"
    )
    frequency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Access frequency score (0-1)"
    )
    source_quality: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Source trustworthiness (0-1)"
    )
    explicit_relevance: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="User-marked importance (0-1)"
    )

    def combined_score(self, weights: dict[str, float] | None = None) -> float:
        """Calculate combined relevance score with optional custom weights."""
        w = weights or {
            "recency": 0.3,
            "frequency": 0.2,
            "source_quality": 0.3,
            "explicit_relevance": 0.2,
        }
        return (
            self.recency * w.get("recency", 0.3)
            + self.frequency * w.get("frequency", 0.2)
            + self.source_quality * w.get("source_quality", 0.3)
            + self.explicit_relevance * w.get("explicit_relevance", 0.2)
        )


# Type aliases for source and content types
SourceType = Literal["kas", "git", "browser", "localcrew", "obsidian", "manual"]
ContentType = Literal[
    "document_chunk",
    "git_commit",
    "git_diff",
    "page_content",
    "agent_output",
    "note",
    "bookmark",
    "conversation",
]


class ContextItem(BaseModel):
    """
    Unified context item schema.

    Represents a single piece of context from any source (KAS, Git, Browser, etc.)
    with bi-temporal metadata for tracking validity and versioning.
    """

    id: UUID = Field(default_factory=uuid4)

    # Source identification
    source: SourceType = Field(description="Origin system (kas, git, browser, etc.)")
    source_id: str | None = Field(
        default=None,
        description="Original ID in source system"
    )
    source_url: str | None = Field(
        default=None,
        description="URL or path to original"
    )

    # Content
    content_type: ContentType = Field(
        description="Type of content (document_chunk, git_commit, etc.)"
    )
    title: str = Field(description="Human-readable title")
    content: str = Field(description="Main content text")
    content_hash: str | None = Field(
        default=None,
        description="SHA256 hash for deduplication"
    )

    # Embedding (populated during ingestion)
    embedding: list[float] | None = Field(
        default=None,
        description="Vector embedding (768d for nomic-embed-text)"
    )

    # Temporal metadata
    temporal: BiTemporalMetadata = Field(
        default_factory=lambda: BiTemporalMetadata(t_valid=datetime.utcnow())
    )
    expires_at: datetime | None = Field(
        default=None,
        description="When this item should be auto-expired (for ephemeral content)"
    )

    # Entity links
    entities: list[str] = Field(
        default_factory=list,
        description="Extracted entity names"
    )
    entity_ids: list[UUID] = Field(
        default_factory=list,
        description="Links to entities table"
    )

    # Classification
    tags: list[str] = Field(
        default_factory=list,
        description="Classification tags"
    )
    namespace: str = Field(
        default="default",
        description="For multi-tenant/project isolation"
    )

    # Relevance
    relevance: RelevanceSignals = Field(default_factory=RelevanceSignals)

    # Flexible metadata
    metadata: dict = Field(
        default_factory=dict,
        description="Source-specific metadata"
    )

    @computed_field
    @property
    def computed_hash(self) -> str:
        """Compute content hash for deduplication."""
        if self.content_hash:
            return self.content_hash
        return hashlib.sha256(
            f"{self.source}:{self.source_id}:{self.content}".encode()
        ).hexdigest()[:16]

    def is_expired(self) -> bool:
        """Check if item has expired."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return self.temporal.t_expired is not None

    def is_valid(self, as_of: datetime | None = None) -> bool:
        """Check if item is valid at given time."""
        if self.is_expired():
            return False
        return self.temporal.is_valid(as_of)

    def to_db_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "id": self.id,
            "source": self.source,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "content_type": self.content_type,
            "title": self.title,
            "content": self.content,
            "content_hash": self.computed_hash,
            "embedding": self.embedding,
            "t_valid": self.temporal.t_valid,
            "t_invalid": self.temporal.t_invalid,
            "t_created": self.temporal.t_created,
            "t_expired": self.temporal.t_expired,
            "expires_at": self.expires_at,
            "entities": self.entities,
            "entity_ids": [str(eid) for eid in self.entity_ids],
            "tags": self.tags,
            "namespace": self.namespace,
            "relevance": self.relevance.model_dump(),
            "metadata": self.metadata,
        }


# Re-export for convenience
__all__ = [
    "BiTemporalMetadata",
    "RelevanceSignals",
    "SourceType",
    "ContentType",
    "ContextItem",
]
