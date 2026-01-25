"""
Agent schemas for API requests and responses.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    """Base agent schema with common fields."""

    name: str = Field(min_length=1, max_length=255, description="Agent name")
    description: str | None = Field(default=None, description="Agent description")
    type: str = Field(
        default="single",
        pattern="^(single|multi|workflow|meta)$",
        description="Agent type",
    )

    # Prompts
    system_prompt: str | None = Field(default=None, description="System prompt")
    task_prompt_template: str | None = Field(default=None, description="Task prompt template")

    # Configuration
    config: dict[str, Any] = Field(default_factory=dict, description="Agent configuration")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="Execution timeout")

    # LLM preferences
    preferred_model: str = Field(default="qwen2.5:7b", description="Preferred LLM model")
    fallback_models: list[str] = Field(
        default_factory=lambda: ["openrouter/qwen", "deepseek", "claude-3-haiku"],
        description="Fallback models in order of preference",
    )
    temperature: float = Field(default=0.7, ge=0, le=2, description="LLM temperature")
    max_tokens: int = Field(default=4096, ge=1, le=32768, description="Max output tokens")


class AgentCreate(AgentBase):
    """Schema for creating a new agent."""

    version: str = Field(default="1.0.0", description="Agent version")
    code_module: str = Field(description="Python module path for agent code")
    code_snapshot: str | None = Field(default=None, description="Full source code")
    original_code: str = Field(description="Original/baseline code for rollback")


class AgentUpdate(BaseModel):
    """Schema for updating an existing agent."""

    description: str | None = None
    system_prompt: str | None = None
    task_prompt_template: str | None = None
    config: dict[str, Any] | None = None
    max_retries: int | None = Field(default=None, ge=0, le=10)
    timeout_seconds: int | None = Field(default=None, ge=1, le=3600)
    preferred_model: str | None = None
    fallback_models: list[str] | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    status: str | None = Field(default=None, pattern="^(active|testing|retired|failed)$")
    available_skills: list[UUID] | None = None


class AgentRead(AgentBase):
    """Schema for reading agent data."""

    id: UUID
    version: str
    code_module: str
    code_hash: str
    status: str
    is_baseline: bool
    parent_version_id: UUID | None

    # Performance metrics
    total_executions: int
    successful_executions: int
    success_rate: float
    avg_execution_time_ms: float
    avg_tokens_used: float

    # Skills
    available_skills: list[UUID]
    dspy_optimized_prompts: dict[str, Any]

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_execution: datetime | None
    retired_at: datetime | None

    class Config:
        from_attributes = True


class AgentList(BaseModel):
    """Simplified schema for agent listings."""

    id: UUID
    name: str
    version: str
    type: str
    status: str
    success_rate: float
    total_executions: int
    created_at: datetime

    class Config:
        from_attributes = True


class AgentStats(BaseModel):
    """Agent statistics response."""

    agent_id: UUID
    name: str
    version: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    avg_execution_time_ms: float
    avg_tokens_used: float
    total_tokens_used: int
    estimated_cost_usd: float
    last_24h_executions: int
    last_7d_executions: int
