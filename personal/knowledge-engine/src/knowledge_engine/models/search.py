"""Search request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from knowledge_engine.models.documents import DocumentType


class SearchFilters(BaseModel):
    """Filters for search queries."""

    document_types: list[DocumentType] | None = Field(
        default=None, description="Filter by document types"
    )
    tags: list[str] | None = Field(default=None, description="Filter by tags (OR)")
    date_from: datetime | None = Field(default=None, description="Filter by date range start")
    date_to: datetime | None = Field(default=None, description="Filter by date range end")
    metadata: dict[str, Any] | None = Field(default=None, description="Custom metadata filters")


class VectorSearchRequest(BaseModel):
    """Request for vector-only search."""

    query: str = Field(..., min_length=1, description="Search query")
    namespace: str = Field(default="default", description="Namespace to search")
    limit: int = Field(default=10, ge=1, le=100, description="Number of results")
    filters: SearchFilters | None = Field(default=None, description="Search filters")
    score_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Minimum similarity score"
    )


class GraphSearchRequest(BaseModel):
    """Request for graph traversal search."""

    query: str = Field(..., min_length=1, description="Search query or entity name")
    namespace: str = Field(default="default", description="Namespace to search")
    limit: int = Field(default=10, ge=1, le=100, description="Number of results")
    hops: int = Field(default=2, ge=1, le=5, description="Graph traversal depth")
    relation_types: list[str] | None = Field(
        default=None, description="Filter by relation types"
    )


class HybridSearchRequest(BaseModel):
    """Request for hybrid search (vector + graph + BM25)."""

    query: str = Field(..., min_length=1, description="Search query")
    namespace: str = Field(default="default", description="Namespace to search")
    limit: int = Field(default=10, ge=1, le=100, description="Number of results")
    filters: SearchFilters | None = Field(default=None, description="Search filters")
    rerank: bool = Field(default=True, description="Apply Cohere reranking")
    include_graph: bool = Field(default=True, description="Include graph traversal")
    graph_hops: int = Field(default=2, ge=1, le=5, description="Graph traversal depth")


class SearchResultItem(BaseModel):
    """Single search result item."""

    document_id: UUID
    chunk_id: UUID | None = None
    title: str | None = None
    content: str = Field(..., description="Relevant text chunk")
    document_type: DocumentType
    namespace: str

    # Scoring
    score: float = Field(..., description="Combined relevance score")
    vector_score: float | None = Field(default=None, description="Vector similarity score")
    graph_score: float | None = Field(default=None, description="Graph relevance score")
    bm25_score: float | None = Field(default=None, description="BM25 keyword score")
    rerank_score: float | None = Field(default=None, description="Cohere rerank score")

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    created_at: datetime | None = None

    # Graph context
    related_entities: list[str] = Field(default_factory=list)
    relation_path: list[str] | None = Field(default=None, description="Path from query entity")


class SearchResult(BaseModel):
    """Search response with results and metadata."""

    query: str
    namespace: str
    total_results: int
    items: list[SearchResultItem]

    # Performance metrics
    search_time_ms: float
    vector_search_time_ms: float | None = None
    graph_search_time_ms: float | None = None
    rerank_time_ms: float | None = None

    # Debug info (only in development)
    debug: dict[str, Any] | None = None
