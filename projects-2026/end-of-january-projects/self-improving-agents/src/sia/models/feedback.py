"""
Feedback model - Human and automated feedback on executions.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sia.models.base import Base

if TYPE_CHECKING:
    from sia.models.execution import Execution


class Feedback(Base):
    """
    Feedback model for human and automated ratings of executions.

    Supports various rating types, annotations, and comparison feedback
    for preference learning.
    """

    __tablename__ = "feedback"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign key to execution
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Source
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    source_details: Mapped[Optional[str]] = mapped_column(Text)

    # Rating
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    rating_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Details
    feedback_text: Mapped[Optional[str]] = mapped_column(Text)
    annotations: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )
    suggested_improvement: Mapped[Optional[str]] = mapped_column(Text)

    # For comparison feedback
    compared_to_execution_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("executions.id"),
    )
    preference: Mapped[Optional[str]] = mapped_column(String(10))

    # Impact tracking
    led_to_improvement_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("improvement_experiments.id"),
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )

    # Relationships
    execution: Mapped["Execution"] = relationship(
        "Execution",
        back_populates="feedback",
        foreign_keys=[execution_id],
    )
    compared_to_execution: Mapped[Optional["Execution"]] = relationship(
        "Execution",
        foreign_keys=[compared_to_execution_id],
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('human', 'automated', 'validation', 'comparison')",
            name="ck_feedback_source",
        ),
        CheckConstraint(
            "rating >= 0 AND rating <= 1",
            name="ck_feedback_rating_range",
        ),
        CheckConstraint(
            "preference IS NULL OR preference IN ('this', 'other', 'tie')",
            name="ck_feedback_preference",
        ),
    )

    @property
    def is_positive(self) -> bool:
        """Check if feedback is positive (rating > 0.5)."""
        return self.rating > 0.5

    @property
    def is_human(self) -> bool:
        """Check if feedback is from a human."""
        return self.source == "human"

    @property
    def is_comparison(self) -> bool:
        """Check if this is comparison feedback."""
        return self.source == "comparison" and self.compared_to_execution_id is not None

    def __repr__(self) -> str:
        return f"<Feedback(id='{self.id}', source='{self.source}', rating={self.rating:.2f})>"
