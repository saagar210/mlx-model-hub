"""Memory models for persistent context storage."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class MemoryType(str, Enum):
    """Types of memories."""

    FACT = "fact"  # Persistent factual knowledge
    PREFERENCE = "preference"  # User preferences
    CONTEXT = "context"  # Conversation context
    PROCEDURE = "procedure"  # How-to knowledge
    ENTITY = "entity"  # Entity information
    RELATION = "relation"  # Relationship between entities


class MemoryCreate(BaseModel):
    """Request to store a new memory."""

    content: str = Field(..., min_length=1, description="Memory content")
    memory_type: MemoryType = Field(default=MemoryType.FACT)
    namespace: str = Field(default="default")
    context: str | None = Field(default=None, description="Context in which memory was created")
    source: str | None = Field(default=None, description="Source of the memory")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="Importance score")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = Field(default=None, description="Optional expiration")


class Memory(BaseModel):
    """Full memory model."""

    id: UUID = Field(default_factory=uuid4)
    content: str
    memory_type: MemoryType
    namespace: str = "default"
    context: str | None = None
    source: str | None = None
    importance: float = 0.5
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # System fields
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    accessed_at: datetime | None = None
    access_count: int = 0
    expires_at: datetime | None = None
    is_deleted: bool = False

    # Graph relations (populated on recall)
    related_memories: list[UUID] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MemoryRecallRequest(BaseModel):
    """Request to recall memories."""

    query: str = Field(..., min_length=1, description="Query to find relevant memories")
    namespace: str = Field(default="default")
    limit: int = Field(default=10, ge=1, le=100)
    memory_types: list[MemoryType] | None = Field(default=None, description="Filter by types")
    min_importance: float | None = Field(default=None, ge=0.0, le=1.0)
    include_related: bool = Field(default=True, description="Include related memories via graph")
    session_id: str | None = Field(default=None, description="Session for context scoping")


class MemoryRecallResponse(BaseModel):
    """Response from memory recall."""

    query: str
    namespace: str
    memories: list[Memory]
    total_found: int
    recall_time_ms: float
