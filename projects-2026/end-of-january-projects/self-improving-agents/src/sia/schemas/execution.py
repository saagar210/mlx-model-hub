"""
Execution schemas for API requests and responses.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionCreate(BaseModel):
    """Schema for creating a new execution."""

    agent_id: UUID = Field(description="Agent to execute")
    task_type: str = Field(min_length=1, max_length=100, description="Type of task")
    task_description: str = Field(min_length=1, description="Task description")
    task_params: dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    input_data: dict[str, Any] = Field(description="Input data for the task")

    # Optional execution context
    parent_execution_id: UUID | None = Field(default=None, description="Parent execution for subtasks")
    request_id: str | None = Field(default=None, description="External request ID for tracing")
    random_seed: int | None = Field(default=None, description="Random seed for reproducibility")


class ExecutionUpdate(BaseModel):
    """Schema for updating an execution (typically on completion)."""

    output_data: dict[str, Any] | None = None
    intermediate_steps: list[dict[str, Any]] | None = None
    success: bool | None = None
    partial_success: bool | None = None
    error_message: str | None = None
    error_type: str | None = None
    error_traceback: str | None = None

    # Metrics
    execution_time_ms: int | None = None
    llm_latency_ms: int | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    tokens_total: int | None = None
    cost_usd: Decimal | None = None

    # Context
    model_used: str | None = None
    temperature_used: float | None = None
    tools_called: list[str] | None = None
    skills_used: list[UUID] | None = None


class ExecutionRead(BaseModel):
    """Schema for reading execution data."""

    id: UUID
    agent_id: UUID
    task_type: str
    task_description: str
    task_params: dict[str, Any]

    # Input/Output
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    intermediate_steps: list[dict[str, Any]]

    # Tool/Skill usage
    tools_called: list[str]
    skills_used: list[UUID]

    # Performance
    success: bool | None
    partial_success: bool
    error_message: str | None
    error_type: str | None

    # Metrics
    execution_time_ms: int | None
    llm_latency_ms: int | None
    tokens_input: int | None
    tokens_output: int | None
    tokens_total: int | None
    cost_usd: Decimal | None

    # Context
    model_used: str | None
    agent_version: str | None
    code_hash: str | None
    prompts_version: str | None
    temperature_used: float | None

    # Memory
    episodic_memory_ids: list[UUID]
    context_retrieved: dict[str, Any]

    # Timing
    queued_at: datetime | None
    started_at: datetime
    completed_at: datetime | None

    # Request metadata
    request_id: str | None
    parent_execution_id: UUID | None
    root_execution_id: UUID | None

    # Feedback
    human_rating: float | None
    automated_rating: float | None

    class Config:
        from_attributes = True


class ExecutionList(BaseModel):
    """Simplified schema for execution listings."""

    id: UUID
    agent_id: UUID
    task_type: str
    task_description: str
    success: bool | None
    execution_time_ms: int | None
    started_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class ExecutionSubmit(BaseModel):
    """Schema for submitting a task to an agent."""

    agent_name: str = Field(description="Name of the agent to use")
    task: str = Field(min_length=1, description="Task description")
    params: dict[str, Any] = Field(default_factory=dict, description="Additional parameters")
    wait: bool = Field(default=True, description="Wait for completion")
    timeout: int = Field(default=300, ge=1, le=3600, description="Timeout in seconds")


class ExecutionResult(BaseModel):
    """Schema for execution result."""

    execution_id: UUID
    success: bool
    output: Any | None
    error: str | None
    execution_time_ms: int | None
    tokens_used: int | None
