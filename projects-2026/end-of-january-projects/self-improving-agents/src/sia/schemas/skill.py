"""
Skill schemas for API requests and responses.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SkillBase(BaseModel):
    """Base skill schema with common fields."""

    name: str = Field(min_length=1, max_length=255, description="Unique skill name")
    description: str = Field(min_length=1, description="Skill description")
    category: str = Field(min_length=1, max_length=50, description="Skill category")
    subcategory: str | None = Field(default=None, max_length=50, description="Skill subcategory")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class SkillCreate(SkillBase):
    """Schema for creating a new skill."""

    code: str = Field(min_length=1, description="Python function code")
    signature: str = Field(min_length=1, description="Function signature")
    input_schema: dict[str, Any] = Field(description="JSON schema for inputs")
    output_schema: dict[str, Any] = Field(description="JSON schema for outputs")

    # Dependencies
    python_dependencies: list[str] = Field(default_factory=list, description="Required pip packages")
    skill_dependencies: list[UUID] = Field(default_factory=list, description="Required skills")

    # Discovery metadata
    discovered_from: UUID | None = Field(default=None, description="Source execution ID")
    extraction_method: str | None = Field(default=None, description="How skill was extracted")
    human_curated: bool = Field(default=False, description="Whether human-reviewed")

    # Examples
    example_inputs: list[dict[str, Any]] = Field(default_factory=list, description="Example inputs")
    example_outputs: list[dict[str, Any]] = Field(default_factory=list, description="Example outputs")
    documentation: str | None = Field(default=None, description="Additional documentation")


class SkillUpdate(BaseModel):
    """Schema for updating a skill."""

    description: str | None = None
    category: str | None = None
    subcategory: str | None = None
    tags: list[str] | None = None
    code: str | None = None
    signature: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    python_dependencies: list[str] | None = None
    skill_dependencies: list[UUID] | None = None
    documentation: str | None = None
    status: str | None = Field(default=None, pattern="^(experimental|active|deprecated|broken)$")


class SkillRead(SkillBase):
    """Schema for reading skill data."""

    id: UUID
    code: str
    signature: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    # Dependencies
    python_dependencies: list[str]
    skill_dependencies: list[UUID]

    # Discovery metadata
    discovered_from: UUID | None
    extraction_method: str | None
    human_curated: bool

    # Composition
    is_composite: bool
    component_skills: list[UUID]
    composition_logic: str | None

    # Performance
    success_rate: float
    avg_execution_time_ms: float | None
    usage_count: int
    last_success: datetime | None
    last_failure: datetime | None
    failure_count: int

    # Examples and docs
    example_inputs: list[dict[str, Any]]
    example_outputs: list[dict[str, Any]]
    documentation: str | None

    # Status
    status: str

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_used: datetime | None
    deprecated_at: datetime | None

    class Config:
        from_attributes = True


class SkillList(BaseModel):
    """Simplified schema for skill listings."""

    id: UUID
    name: str
    description: str
    category: str
    status: str
    success_rate: float
    usage_count: int

    class Config:
        from_attributes = True


class SkillSearch(BaseModel):
    """Schema for skill search request."""

    query: str = Field(min_length=1, description="Search query")
    category: str | None = Field(default=None, description="Filter by category")
    status: str | None = Field(
        default=None,
        pattern="^(experimental|active|deprecated|broken)$",
        description="Filter by status",
    )
    min_success_rate: float | None = Field(default=None, ge=0, le=1, description="Minimum success rate")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")


class SkillSearchResult(BaseModel):
    """Schema for skill search result."""

    skill: SkillList
    relevance_score: float = Field(description="Relevance score from search")
    embedding_distance: float | None = Field(default=None, description="Vector distance if applicable")
