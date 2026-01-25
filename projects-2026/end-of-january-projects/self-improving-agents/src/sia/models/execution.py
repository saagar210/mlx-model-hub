"""
Execution model - Complete history of all agent executions.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sia.models.base import Base

if TYPE_CHECKING:
    from sia.models.agent import Agent
    from sia.models.feedback import Feedback
    from sia.models.memory import EpisodicMemory


class Execution(Base):
    """
    Execution model representing a single agent task execution.

    Stores complete execution history including inputs, outputs,
    intermediate steps, and performance metrics.
    """

    __tablename__ = "executions"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign key to agent
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Task details
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    task_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )

    # Input/Output
    input_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    intermediate_steps: Mapped[list[dict[str, Any]]] = mapped_column(
        ARRAY(JSONB),
        default=list,
        server_default="{}",
    )

    # Tool/Skill usage
    tools_called: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        server_default="{}",
    )
    skills_used: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )

    # Performance
    success: Mapped[Optional[bool]] = mapped_column(Boolean)
    partial_success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_type: Mapped[Optional[str]] = mapped_column(String(50))
    error_traceback: Mapped[Optional[str]] = mapped_column(Text)

    # Metrics
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    llm_latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    tokens_input: Mapped[Optional[int]] = mapped_column(Integer)
    tokens_output: Mapped[Optional[int]] = mapped_column(Integer)
    tokens_total: Mapped[Optional[int]] = mapped_column(Integer)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6))

    # Context used
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    agent_version: Mapped[Optional[str]] = mapped_column(String(50))
    code_hash: Mapped[Optional[str]] = mapped_column(String(64))
    prompts_version: Mapped[Optional[str]] = mapped_column(String(50))

    # Memory references
    episodic_memory_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )
    context_retrieved: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )

    # Reproducibility
    random_seed: Mapped[Optional[int]] = mapped_column(Integer)
    temperature_used: Mapped[Optional[float]] = mapped_column(Float)

    # Timing
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Request metadata
    request_id: Mapped[Optional[str]] = mapped_column(String(100))
    parent_execution_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("executions.id"),
    )
    root_execution_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("executions.id"),
    )

    # Feedback (populated later)
    human_rating: Mapped[Optional[float]] = mapped_column(Float)
    automated_rating: Mapped[Optional[float]] = mapped_column(Float)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="executions")
    parent_execution: Mapped[Optional["Execution"]] = relationship(
        "Execution",
        remote_side=[id],
        foreign_keys=[parent_execution_id],
        backref="child_executions",
    )
    root_execution: Mapped[Optional["Execution"]] = relationship(
        "Execution",
        remote_side=[id],
        foreign_keys=[root_execution_id],
    )
    episodic_memories: Mapped[list["EpisodicMemory"]] = relationship(
        "EpisodicMemory",
        back_populates="execution",
        cascade="all, delete-orphan",
    )
    feedback: Mapped[list["Feedback"]] = relationship(
        "Feedback",
        back_populates="execution",
        cascade="all, delete-orphan",
    )

    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate execution duration."""
        if self.completed_at and self.started_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None

    @property
    def is_complete(self) -> bool:
        """Check if execution has completed."""
        return self.completed_at is not None

    def __repr__(self) -> str:
        status = "success" if self.success else "failed" if self.success is False else "pending"
        return f"<Execution(id='{self.id}', task_type='{self.task_type}', status='{status}')>"
