"""
Memory schemas for API requests and responses.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Episodic Memory
# ============================================================================


class EpisodicMemoryCreate(BaseModel):
    """Schema for creating an episodic memory entry."""

    execution_id: UUID = Field(description="Related execution ID")
    sequence_num: int = Field(ge=0, description="Sequence within execution")
    event_type: str = Field(min_length=1, max_length=50, description="Type of event")
    description: str = Field(min_length=1, description="Event description")
    details: dict[str, Any] = Field(default_factory=dict, description="Event details")

    # Context snapshot
    agent_state: dict[str, Any] | None = Field(default=None, description="Agent state snapshot")
    memory_state: dict[str, Any] | None = Field(default=None, description="Memory state snapshot")
    environment_state: dict[str, Any] | None = Field(default=None, description="Environment snapshot")

    # For embedding
    content_for_embedding: str | None = Field(default=None, description="Text to embed")

    # Importance
    importance_score: float = Field(default=0.5, ge=0, le=1, description="Importance score")

    # Links
    related_skill_id: UUID | None = Field(default=None, description="Related skill")
    related_fact_ids: list[UUID] = Field(default_factory=list, description="Related facts")


class EpisodicMemoryRead(BaseModel):
    """Schema for reading episodic memory."""

    id: UUID
    execution_id: UUID
    sequence_num: int
    timestamp: datetime
    event_type: str
    description: str
    details: dict[str, Any]

    agent_state: dict[str, Any] | None
    memory_state: dict[str, Any] | None
    environment_state: dict[str, Any] | None

    content_for_embedding: str | None
    embedding_model: str
    importance_score: float

    related_skill_id: UUID | None
    related_fact_ids: list[UUID]

    class Config:
        from_attributes = True


class EpisodicMemorySearch(BaseModel):
    """Schema for episodic memory search."""

    query: str = Field(min_length=1, description="Search query")
    execution_id: UUID | None = Field(default=None, description="Filter by execution")
    event_type: str | None = Field(default=None, description="Filter by event type")
    min_importance: float | None = Field(default=None, ge=0, le=1, description="Minimum importance")
    since: datetime | None = Field(default=None, description="Filter by timestamp")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")


# ============================================================================
# Semantic Memory
# ============================================================================


class SemanticMemoryCreate(BaseModel):
    """Schema for creating a semantic memory entry."""

    fact: str = Field(min_length=1, description="The fact/knowledge to store")
    fact_type: str = Field(
        min_length=1,
        max_length=50,
        description="Type of fact (rule, constraint, pattern, etc.)",
    )
    category: str | None = Field(default=None, max_length=50, description="Category")
    tags: list[str] = Field(default_factory=list, description="Tags")

    # Confidence
    confidence: float = Field(default=1.0, ge=0, le=1, description="Confidence score")
    supporting_executions: list[UUID] = Field(
        default_factory=list,
        description="Executions that support this fact",
    )

    # Source
    source: str = Field(
        default="learned",
        pattern="^(learned|configured|user_feedback|extracted)$",
        description="Source of the fact",
    )
    source_description: str | None = Field(default=None, description="Source details")

    # Validity
    valid_until: datetime | None = Field(default=None, description="Expiration timestamp")


class SemanticMemoryUpdate(BaseModel):
    """Schema for updating semantic memory."""

    fact: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    valid_until: datetime | None = None


class SemanticMemoryRead(BaseModel):
    """Schema for reading semantic memory."""

    id: UUID
    fact: str
    fact_type: str
    category: str | None
    tags: list[str]

    confidence: float
    evidence_count: int
    supporting_executions: list[UUID]
    contradicting_executions: list[UUID]

    source: str
    source_description: str | None

    embedding_model: str

    valid_from: datetime
    valid_until: datetime | None
    superseded_by: UUID | None

    access_count: int
    last_accessed: datetime | None
    usefulness_score: float

    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    class Config:
        from_attributes = True


class SemanticMemorySearch(BaseModel):
    """Schema for semantic memory search."""

    query: str = Field(min_length=1, description="Search query")
    fact_type: str | None = Field(default=None, description="Filter by fact type")
    category: str | None = Field(default=None, description="Filter by category")
    min_confidence: float | None = Field(default=None, ge=0, le=1, description="Minimum confidence")
    include_expired: bool = Field(default=False, description="Include expired facts")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")


# ============================================================================
# Unified Memory Search
# ============================================================================


class UnifiedMemorySearch(BaseModel):
    """Schema for searching across all memory types."""

    query: str = Field(min_length=1, description="Search query")
    memory_types: list[str] = Field(
        default=["episodic", "semantic", "procedural"],
        description="Memory types to search",
    )
    limit_per_type: int = Field(default=5, ge=1, le=50, description="Results per memory type")
    rerank: bool = Field(default=True, description="Apply reranking to results")


class MemorySearchResult(BaseModel):
    """Schema for a single memory search result."""

    memory_type: str = Field(description="Type of memory (episodic, semantic, procedural)")
    id: UUID
    content: str = Field(description="Main content of the memory")
    relevance_score: float = Field(description="Relevance score")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class UnifiedMemorySearchResponse(BaseModel):
    """Schema for unified memory search response."""

    query: str
    results: list[MemorySearchResult]
    total_results: int
    reranked: bool
