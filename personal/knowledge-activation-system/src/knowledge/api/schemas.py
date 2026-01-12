"""API schemas using Pydantic."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# Search Schemas
# =============================================================================


class SearchMode(str, Enum):
    """Search modes."""

    HYBRID = "hybrid"
    BM25 = "bm25"
    VECTOR = "vector"


class SearchRequest(BaseModel):
    """Search request."""

    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(10, ge=1, le=100, description="Number of results")
    mode: SearchMode = Field(SearchMode.HYBRID, description="Search mode")


class SearchResultItem(BaseModel):
    """Individual search result."""

    content_id: UUID
    title: str
    content_type: str
    score: float
    chunk_text: str | None = None
    source_ref: str | None = None
    bm25_rank: int | None = None
    vector_rank: int | None = None


class SearchResponse(BaseModel):
    """Search response."""

    query: str
    results: list[SearchResultItem]
    total: int
    mode: str


# =============================================================================
# Q&A Schemas
# =============================================================================


class ConfidenceLevel(str, Enum):
    """Confidence levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AskRequest(BaseModel):
    """Q&A request."""

    query: str = Field(..., min_length=1, description="Question to answer")
    limit: int = Field(10, ge=1, le=50, description="Search results to consider")


class CitationItem(BaseModel):
    """Citation in Q&A response."""

    index: int
    title: str
    content_type: str
    chunk_text: str | None = None


class AskResponse(BaseModel):
    """Q&A response."""

    query: str
    answer: str
    confidence: ConfidenceLevel
    confidence_score: float
    citations: list[CitationItem]
    warning: str | None = None
    error: str | None = None


# =============================================================================
# Content Schemas
# =============================================================================


class ContentItem(BaseModel):
    """Content item."""

    id: UUID
    filepath: str
    content_type: str
    title: str
    summary: str | None = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime


class ContentListResponse(BaseModel):
    """Content list response."""

    items: list[ContentItem]
    total: int
    page: int
    page_size: int


class ContentDetailResponse(BaseModel):
    """Content detail response."""

    id: UUID
    filepath: str
    content_type: str
    title: str
    summary: str | None = None
    tags: list[str] = []
    metadata: dict = {}
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0


# =============================================================================
# Stats Schemas
# =============================================================================


class StatsResponse(BaseModel):
    """Database statistics."""

    total_content: int
    total_chunks: int
    content_by_type: dict[str, int]
    review_active: int
    review_due: int


# =============================================================================
# Health Schemas
# =============================================================================


class ServiceHealth(BaseModel):
    """Individual service health."""

    name: str
    status: str
    details: dict = {}


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    services: list[ServiceHealth]


# =============================================================================
# Review Schemas
# =============================================================================


class ReviewRatingValue(str, Enum):
    """Review rating values."""

    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


class ReviewQueueItem(BaseModel):
    """Item in the review queue."""

    content_id: UUID
    title: str
    content_type: str
    preview_text: str
    state: str
    due: datetime
    stability: float | None = None
    difficulty: float | None = None
    is_new: bool
    is_learning: bool
    is_review: bool
    last_review: datetime | None = None


class ReviewDueResponse(BaseModel):
    """Response for due review items."""

    items: list[ReviewQueueItem]
    total: int


class ReviewStatsResponse(BaseModel):
    """Review queue statistics."""

    total_active: int
    due_now: int
    new: int
    learning: int
    review: int


class SubmitReviewRequest(BaseModel):
    """Request to submit a review."""

    rating: ReviewRatingValue


class SubmitReviewResponse(BaseModel):
    """Response after submitting a review."""

    content_id: UUID
    rating: str
    old_state: str
    new_state: str
    old_due: datetime
    new_due: datetime
    review_time: datetime


class ReviewIntervalsResponse(BaseModel):
    """Preview of next intervals for each rating."""

    again: datetime
    hard: datetime
    good: datetime
    easy: datetime


class ScheduleStatusResponse(BaseModel):
    """Daily review schedule status."""

    enabled: bool
    scheduled_time: str  # "HH:MM" format
    timezone: str
    next_run: datetime | None = None
    last_run: datetime | None = None
    due_count: int
    status: str  # "running", "waiting", "disabled"
