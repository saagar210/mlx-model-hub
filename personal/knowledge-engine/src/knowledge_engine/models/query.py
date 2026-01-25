"""Query (RAG) request and response models."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """Confidence level for RAG responses."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Citation(BaseModel):
    """Citation for a source used in the response."""

    document_id: UUID
    chunk_id: UUID | None = None
    title: str | None = None
    content: str = Field(..., description="Cited text")
    source: str | None = Field(default=None, description="Source URL or path")
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class QueryRequest(BaseModel):
    """Request for RAG query."""

    question: str = Field(..., min_length=1, description="Question to answer")
    namespace: str = Field(default="default", description="Namespace to search")
    include_citations: bool = Field(default=True, description="Include source citations")
    max_sources: int = Field(default=5, ge=1, le=20, description="Max sources to use")
    model: str | None = Field(default=None, description="Override LLM model")
    system_prompt: str | None = Field(default=None, description="Custom system prompt")
    context: str | None = Field(default=None, description="Additional context")
    stream: bool = Field(default=False, description="Stream response")


class QueryResponse(BaseModel):
    """Response from RAG query."""

    question: str
    answer: str
    namespace: str

    # Confidence
    confidence: ConfidenceLevel
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_reason: str | None = None

    # Citations
    citations: list[Citation] = Field(default_factory=list)

    # Metadata
    model_used: str
    tokens_used: int | None = None
    search_time_ms: float
    generation_time_ms: float
    total_time_ms: float

    # Debug info
    debug: dict[str, Any] | None = None


class AgenticQueryRequest(BaseModel):
    """Request for agentic (multi-step) RAG query."""

    question: str = Field(..., min_length=1, description="Complex question to answer")
    namespace: str = Field(default="default")
    max_iterations: int = Field(default=5, ge=1, le=10, description="Max reasoning steps")
    tools: list[str] = Field(
        default_factory=lambda: ["search", "graph_query", "summarize"],
        description="Tools the agent can use",
    )


class AgenticQueryResponse(BaseModel):
    """Response from agentic RAG query."""

    question: str
    answer: str
    namespace: str

    # Reasoning trace
    reasoning_steps: list[dict[str, Any]] = Field(
        default_factory=list, description="Agent's reasoning trace"
    )
    iterations: int
    tools_used: list[str]

    # Final answer metadata
    confidence: ConfidenceLevel
    citations: list[Citation] = Field(default_factory=list)
    total_time_ms: float
