"""Search request and response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .context_item import ContextItem, SourceType, ContentType


class SearchQuery(BaseModel):
    """Search query parameters."""

    query: str = Field(
        description="Search query text"
    )

    # Filters
    sources: list[SourceType] | None = Field(
        default=None,
        description="Filter by source types"
    )
    content_types: list[ContentType] | None = Field(
        default=None,
        description="Filter by content types"
    )
    since: datetime | None = Field(
        default=None,
        description="Only include items valid after this time"
    )
    until: datetime | None = Field(
        default=None,
        description="Only include items valid before this time"
    )
    entities: list[str] | None = Field(
        default=None,
        description="Filter by entity names"
    )
    tags: list[str] | None = Field(
        default=None,
        description="Filter by tags"
    )
    namespace: str | None = Field(
        default=None,
        description="Filter by namespace"
    )

    # Search options
    include_expired: bool = Field(
        default=False,
        description="Include expired items in results"
    )


class SearchResult(BaseModel):
    """A single search result with score and metadata."""

    item: ContextItem = Field(description="The matched context item")
    score: float = Field(description="Relevance score (0-1)")
    match_type: str = Field(
        default="hybrid",
        description="Type of match (vector, bm25, hybrid, graph)"
    )
    highlights: list[str] = Field(
        default_factory=list,
        description="Text snippets with matches highlighted"
    )


class SearchResponse(BaseModel):
    """Search response with results and metadata."""

    results: list[SearchResult] = Field(
        description="Ranked search results"
    )
    total: int = Field(
        description="Total number of matches (before limit)"
    )
    query: str = Field(
        description="Original query"
    )
    search_time_ms: float = Field(
        default=0.0,
        description="Search execution time in milliseconds"
    )

    # Debug info
    vector_candidates: int = Field(
        default=0,
        description="Number of vector search candidates"
    )
    bm25_candidates: int = Field(
        default=0,
        description="Number of BM25 search candidates"
    )


class EntitySearchResult(BaseModel):
    """Search result for entity queries."""

    entity_name: str = Field(description="Entity canonical name")
    display_name: str = Field(description="Entity display name")
    entity_type: str = Field(description="Entity type")
    mention_count: int = Field(description="Number of mentions")
    related_items: list[SearchResult] = Field(
        default_factory=list,
        description="Context items mentioning this entity"
    )


class RecentContextResponse(BaseModel):
    """Response for recent context queries."""

    items: list[ContextItem] = Field(
        description="Recent context items"
    )
    by_source: dict[str, int] = Field(
        default_factory=dict,
        description="Count of items by source"
    )
    hours: int = Field(
        description="Time window in hours"
    )


class WorkingContextResponse(BaseModel):
    """Response for current working context."""

    git_activity: list[ContextItem] = Field(
        default_factory=list,
        description="Recent git commits and changes"
    )
    browser_tabs: list[ContextItem] = Field(
        default_factory=list,
        description="Current browser tabs"
    )
    recent_documents: list[ContextItem] = Field(
        default_factory=list,
        description="Recently accessed documents"
    )
    active_entities: list[str] = Field(
        default_factory=list,
        description="Entities active in current context"
    )


__all__ = [
    "SearchQuery",
    "SearchResult",
    "SearchResponse",
    "EntitySearchResult",
    "RecentContextResponse",
    "WorkingContextResponse",
]
