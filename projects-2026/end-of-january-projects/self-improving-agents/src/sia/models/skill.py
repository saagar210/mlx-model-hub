"""
Skill model - Reusable skills discovered from successful executions.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from sia.models.base import Base, TimestampMixin


class Skill(Base, TimestampMixin):
    """
    Skill model representing a reusable capability.

    Skills are discovered from successful executions or manually defined,
    and can be composed to create more complex skills.
    """

    __tablename__ = "skills"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Identity
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(50))
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        server_default="{}",
    )

    # Implementation
    code: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Dependencies
    python_dependencies: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        server_default="{}",
    )
    skill_dependencies: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )

    # Discovery metadata
    discovered_from: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("executions.id"),
    )
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50))
    human_curated: Mapped[bool] = mapped_column(Boolean, default=False)

    # Composition
    is_composite: Mapped[bool] = mapped_column(Boolean, default=False)
    component_skills: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )
    composition_logic: Mapped[Optional[str]] = mapped_column(Text)

    # Performance
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_execution_time_ms: Mapped[Optional[float]] = mapped_column(Float)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_success: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_failure: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failure_count: Mapped[int] = mapped_column(Integer, default=0)

    # Embeddings
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(768))
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        default="nomic-embed-text-v1.5",
    )

    # Example usage
    example_inputs: Mapped[list[dict[str, Any]]] = mapped_column(
        ARRAY(JSONB),
        default=list,
        server_default="{}",
    )
    example_outputs: Mapped[list[dict[str, Any]]] = mapped_column(
        ARRAY(JSONB),
        default=list,
        server_default="{}",
    )
    documentation: Mapped[Optional[str]] = mapped_column(Text)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="experimental")

    # Additional timestamps
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deprecated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('experimental', 'active', 'deprecated', 'broken')",
            name="ck_skill_status",
        ),
    )

    @property
    def is_active(self) -> bool:
        """Check if skill is active."""
        return self.status == "active"

    @property
    def reliability(self) -> float:
        """Calculate reliability score based on success/failure ratio."""
        total = self.usage_count
        if total == 0:
            return 0.0
        return (total - self.failure_count) / total

    def __repr__(self) -> str:
        return f"<Skill(name='{self.name}', category='{self.category}', status='{self.status}')>"
