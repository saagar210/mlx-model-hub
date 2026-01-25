"""
Agent model - Central registry of all agent definitions and versions.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sia.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from sia.models.execution import Execution
    from sia.models.experiment import ImprovementExperiment


class Agent(Base, TimestampMixin):
    """
    Agent model representing an AI agent definition.

    Agents can have multiple versions, with parent-child relationships
    tracking evolution over time.
    """

    __tablename__ = "agents"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        # Constraint added via __table_args__
    )

    # Code (for self-modifying agents)
    code_module: Mapped[str] = mapped_column(String(255), nullable=False)
    code_snapshot: Mapped[Optional[str]] = mapped_column(Text)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    original_code: Mapped[str] = mapped_column(Text, nullable=False)

    # Prompts (DSPy-optimized)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)
    task_prompt_template: Mapped[Optional[str]] = mapped_column(Text)
    dspy_optimized_prompts: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )

    # Configuration
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)

    # LLM preferences
    preferred_model: Mapped[str] = mapped_column(String(100), default="qwen2.5:7b")
    fallback_models: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        server_default="{}",
    )
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)

    # Skills this agent can use
    available_skills: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )

    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_version_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id"),
    )

    # Performance tracking
    total_executions: Mapped[int] = mapped_column(Integer, default=0)
    successful_executions: Mapped[int] = mapped_column(Integer, default=0)
    # success_rate is computed by the database
    avg_execution_time_ms: Mapped[float] = mapped_column(Float, default=0)
    avg_tokens_used: Mapped[float] = mapped_column(Float, default=0)

    # Timestamps (additional to mixin)
    last_execution: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    parent_version: Mapped[Optional["Agent"]] = relationship(
        "Agent",
        remote_side=[id],
        backref="child_versions",
    )
    executions: Mapped[list["Execution"]] = relationship(
        "Execution",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    experiments: Mapped[list["ImprovementExperiment"]] = relationship(
        "ImprovementExperiment",
        back_populates="agent",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_agent_name_version"),
        CheckConstraint(
            "type IN ('single', 'multi', 'workflow', 'meta')",
            name="ck_agent_type",
        ),
        CheckConstraint(
            "status IN ('active', 'testing', 'retired', 'failed')",
            name="ck_agent_status",
        ),
    )

    @property
    def success_rate(self) -> float:
        """Calculate success rate from execution counts."""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    def __repr__(self) -> str:
        return f"<Agent(name='{self.name}', version='{self.version}', status='{self.status}')>"
