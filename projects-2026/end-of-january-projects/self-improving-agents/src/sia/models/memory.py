"""
Memory models - Episodic and Semantic memory for context retrieval.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sia.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from sia.models.execution import Execution


class EpisodicMemory(Base):
    """
    Episodic memory model - Timestamped execution events for context retrieval.

    Stores individual events that occurred during agent executions,
    with embeddings for similarity-based retrieval.
    """

    __tablename__ = "episodic_memory"

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

    # Event details
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Content
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )

    # Context snapshot
    agent_state: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    memory_state: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    environment_state: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    # Embedding for retrieval
    content_for_embedding: Mapped[Optional[str]] = mapped_column(Text)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(768))
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        default="nomic-embed-text-v1.5",
    )

    # Importance score for retrieval prioritization
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)

    # Links
    related_skill_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("skills.id"),
    )
    related_fact_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )

    # Relationships
    execution: Mapped["Execution"] = relationship(
        "Execution",
        back_populates="episodic_memories",
    )

    __table_args__ = (
        UniqueConstraint("execution_id", "sequence_num", name="uq_episodic_execution_seq"),
    )

    def __repr__(self) -> str:
        return f"<EpisodicMemory(id='{self.id}', event_type='{self.event_type}')>"


class SemanticMemory(Base, TimestampMixin):
    """
    Semantic memory model - Facts, knowledge, and learned patterns.

    Stores general knowledge and learned patterns that persist
    across executions, with confidence scores that can decay over time.
    """

    __tablename__ = "semantic_memory"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Content
    fact: Mapped[str] = mapped_column(Text, nullable=False)
    fact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        server_default="{}",
    )

    # Confidence & Evidence
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    supporting_executions: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )
    contradicting_executions: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )

    # Source
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_description: Mapped[Optional[str]] = mapped_column(Text)

    # Embedding
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(768))
    embedding_model: Mapped[str] = mapped_column(
        String(100),
        default="nomic-embed-text-v1.5",
    )

    # Validity
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    superseded_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("semantic_memory.id"),
    )

    # Access tracking
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    usefulness_score: Mapped[float] = mapped_column(Float, default=0.5)

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_semantic_confidence"),
    )

    @property
    def is_valid(self) -> bool:
        """Check if fact is currently valid."""
        now = datetime.utcnow()
        if self.deleted_at:
            return False
        if self.valid_until and self.valid_until < now:
            return False
        return True

    def reinforce(self, execution_id: UUID) -> None:
        """Reinforce this fact with supporting evidence."""
        if execution_id not in self.supporting_executions:
            self.supporting_executions = [*self.supporting_executions, execution_id]
        self.evidence_count += 1
        # Increase confidence (with diminishing returns)
        self.confidence = min(1.0, self.confidence + (1 - self.confidence) * 0.1)

    def contradict(self, execution_id: UUID) -> None:
        """Record contradicting evidence."""
        if execution_id not in self.contradicting_executions:
            self.contradicting_executions = [*self.contradicting_executions, execution_id]
        # Decrease confidence
        self.confidence = max(0.0, self.confidence * 0.9)

    def __repr__(self) -> str:
        return f"<SemanticMemory(id='{self.id}', fact_type='{self.fact_type}', confidence={self.confidence:.2f})>"
