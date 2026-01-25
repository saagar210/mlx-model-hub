"""Data models for context items and sources."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ContextSource(str, Enum):
    """Available context sources."""

    OBSIDIAN = "obsidian"
    GIT = "git"
    KAS = "kas"


class ContextItem(BaseModel):
    """Unified context item from any source."""

    id: str = Field(description="Unique identifier")
    source: ContextSource = Field(description="Source system")
    title: str = Field(description="Display title")
    content: str = Field(description="Main content")
    path: str | None = Field(default=None, description="File path if applicable")
    url: str | None = Field(default=None, description="URL if applicable")
    timestamp: datetime = Field(default_factory=datetime.now, description="Item timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Source-specific metadata")
    relevance_score: float = Field(default=0.0, description="Relevance score (0-1)")

    def to_display(self) -> str:
        """Format for display in tool results."""
        source_icon = {
            ContextSource.OBSIDIAN: "📝",
            ContextSource.GIT: "🔀",
            ContextSource.KAS: "📚",
        }.get(self.source, "📄")

        location = self.path or self.url or ""
        return f"{source_icon} [{self.source.value}] {self.title}\n   {location}\n   {self.content[:200]}..."


class NoteResult(BaseModel):
    """Result from Obsidian note operations."""

    path: str = Field(description="Relative path within vault")
    title: str = Field(description="Note title (from frontmatter or filename)")
    content: str = Field(description="Full note content")
    frontmatter: dict[str, Any] = Field(default_factory=dict, description="YAML frontmatter")
    modified: datetime = Field(description="Last modified time")
    backlinks: list[str] = Field(default_factory=list, description="Notes linking to this one")


class SearchResult(BaseModel):
    """Search result with relevance information."""

    items: list[ContextItem] = Field(default_factory=list)
    total_count: int = Field(default=0)
    query: str = Field(default="")
    sources_searched: list[str] = Field(default_factory=list)
