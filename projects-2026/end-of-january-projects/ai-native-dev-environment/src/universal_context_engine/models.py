"""Pydantic models for Universal Context Engine."""

from datetime import UTC, datetime
from enum import Enum
from functools import partial
from typing import Any


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)

from pydantic import BaseModel, Field


class ContextType(str, Enum):
    """Types of context items that can be stored."""

    SESSION = "session"
    DECISION = "decision"
    PATTERN = "pattern"
    CONTEXT = "context"
    BLOCKER = "blocker"
    ERROR = "error"


class ContextItem(BaseModel):
    """A context item stored in ChromaDB."""

    id: str = Field(description="Unique identifier for the context item")
    content: str = Field(description="The actual content/text of the context")
    context_type: ContextType = Field(description="Type of context item")
    project: str | None = Field(default=None, description="Associated project path")
    branch: str | None = Field(default=None, description="Git branch if applicable")
    timestamp: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SearchResult(BaseModel):
    """A search result from context store."""

    item: ContextItem
    score: float = Field(description="Similarity score (0-1, higher is better)")
    distance: float = Field(description="Distance in embedding space")


class SessionCapture(BaseModel):
    """Data captured during a session."""

    session_id: str
    project_path: str | None = None
    git_branch: str | None = None
    files_modified: list[str] = Field(default_factory=list)
    conversation_excerpt: str = ""
    key_decisions: list[str] = Field(default_factory=list)
    errors_encountered: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utc_now)


class SessionSummary(BaseModel):
    """Summary of a development session."""

    session_id: str
    summary: str
    project: str | None = None
    branch: str | None = None
    files_touched: int = 0
    decisions_made: int = 0
    blockers: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utc_now)


class ServiceHealth(BaseModel):
    """Health status of a service."""

    name: str
    status: str  # "healthy", "unhealthy", "unknown"
    latency_ms: float | None = None
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
