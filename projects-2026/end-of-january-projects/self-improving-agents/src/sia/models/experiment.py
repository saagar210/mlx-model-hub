"""
Experiment models - Track improvement attempts, DSPy optimizations, and code evolutions.
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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sia.models.base import Base

if TYPE_CHECKING:
    from sia.models.agent import Agent


class ImprovementExperiment(Base):
    """
    Track all attempts to improve agents.

    Records the hypothesis, baseline metrics, proposed changes,
    evaluation results, and deployment status.
    """

    __tablename__ = "improvement_experiments"

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

    # Experiment type
    improvement_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Hypothesis
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    expected_improvement: Mapped[Optional[str]] = mapped_column(Text)

    # Baseline
    baseline_agent_version: Mapped[Optional[str]] = mapped_column(String(50))
    baseline_code_hash: Mapped[Optional[str]] = mapped_column(String(64))
    baseline_prompts: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    baseline_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Proposed change
    proposed_code: Mapped[Optional[str]] = mapped_column(Text)
    proposed_code_hash: Mapped[Optional[str]] = mapped_column(String(64))
    proposed_prompts: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    proposed_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    change_description: Mapped[str] = mapped_column(Text, nullable=False)
    change_diff: Mapped[Optional[str]] = mapped_column(Text)

    # DSPy-specific
    dspy_optimizer: Mapped[Optional[str]] = mapped_column(String(50))
    dspy_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    dspy_training_examples: Mapped[Optional[int]] = mapped_column(Integer)
    dspy_trials: Mapped[Optional[int]] = mapped_column(Integer)

    # Evaluation
    evaluation_metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    improvement_delta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    # Statistical significance
    sample_size: Mapped[Optional[int]] = mapped_column(Integer)
    confidence_interval: Mapped[Optional[float]] = mapped_column(Float)
    p_value: Mapped[Optional[float]] = mapped_column(Float)
    is_statistically_significant: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Safety checks
    sandbox_test_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    regression_tests_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    security_check_passed: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Decision
    status: Mapped[str] = mapped_column(String(30), default="proposed")
    decision_reason: Mapped[Optional[str]] = mapped_column(Text)
    decided_by: Mapped[Optional[str]] = mapped_column(String(100))

    # A/B testing
    test_execution_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )
    control_execution_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        default=list,
        server_default="{}",
    )
    test_traffic_percentage: Mapped[Optional[float]] = mapped_column(Float)

    # Deployment
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    new_agent_version_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id"),
    )
    rollback_reason: Mapped[Optional[str]] = mapped_column(Text)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    testing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    testing_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="experiments", foreign_keys=[agent_id])

    __table_args__ = (
        CheckConstraint(
            "improvement_type IN ('prompt_optimization', 'code_mutation', 'skill_learning', "
            "'skill_composition', 'config_tuning', 'architecture_change')",
            name="ck_experiment_type",
        ),
        CheckConstraint(
            "status IN ('proposed', 'approved_for_testing', 'testing', 'evaluated', "
            "'approved', 'rejected', 'deployed', 'rolled_back')",
            name="ck_experiment_status",
        ),
    )

    @property
    def is_approved(self) -> bool:
        """Check if experiment is approved."""
        return self.status in ("approved", "deployed")

    @property
    def is_deployed(self) -> bool:
        """Check if experiment is deployed."""
        return self.status == "deployed" and self.deployed_at is not None

    def __repr__(self) -> str:
        return f"<ImprovementExperiment(id='{self.id}', type='{self.improvement_type}', status='{self.status}')>"


class DSPyOptimization(Base):
    """
    Track DSPy prompt optimization runs.

    Records optimizer configuration, training data, results,
    and optimized artifacts.
    """

    __tablename__ = "dspy_optimizations"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    experiment_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("improvement_experiments.id"),
    )

    # Optimizer config
    optimizer_type: Mapped[str] = mapped_column(String(50), nullable=False)
    optimizer_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Training data
    training_examples_count: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_examples_count: Mapped[Optional[int]] = mapped_column(Integer)
    training_data_source: Mapped[Optional[str]] = mapped_column(String(50))

    # Signatures optimized
    signatures_optimized: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )

    # Results
    baseline_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    optimized_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    improvement_pct: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    overall_improvement_pct: Mapped[Optional[float]] = mapped_column(Float)

    # Optimized artifacts
    optimized_instructions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    optimized_demos: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    bootstrapped_demos: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    # Process details
    num_trials: Mapped[Optional[int]] = mapped_column(Integer)
    best_trial_num: Mapped[Optional[int]] = mapped_column(Integer)
    trial_history: Mapped[list[dict[str, Any]]] = mapped_column(
        ARRAY(JSONB),
        default=list,
        server_default="{}",
    )

    # State
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'applied')",
            name="ck_dspy_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<DSPyOptimization(id='{self.id}', optimizer='{self.optimizer_type}', status='{self.status}')>"


class CodeEvolution(Base):
    """
    Track code mutations (Gödel Agent style).

    Records mutation details, sandbox testing results,
    and security checks.
    """

    __tablename__ = "code_evolutions"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Foreign keys
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    experiment_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("improvement_experiments.id"),
    )

    # Evolution type
    evolution_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Mutation details
    mutation_target: Mapped[Optional[str]] = mapped_column(String(255))
    mutation_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Code
    original_code: Mapped[str] = mapped_column(Text, nullable=False)
    mutated_code: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[str] = mapped_column(Text, nullable=False)

    # LLM guidance (if llm_guided)
    llm_prompt: Mapped[Optional[str]] = mapped_column(Text)
    llm_response: Mapped[Optional[str]] = mapped_column(Text)
    llm_model_used: Mapped[Optional[str]] = mapped_column(String(100))

    # Sandbox testing
    sandbox_id: Mapped[Optional[str]] = mapped_column(String(100))
    sandbox_tests_run: Mapped[Optional[int]] = mapped_column(Integer)
    sandbox_tests_passed: Mapped[Optional[int]] = mapped_column(Integer)
    sandbox_runtime_ms: Mapped[Optional[int]] = mapped_column(Integer)
    sandbox_memory_mb: Mapped[Optional[int]] = mapped_column(Integer)
    sandbox_logs: Mapped[Optional[str]] = mapped_column(Text)

    # Security checks
    static_analysis_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    no_dangerous_calls: Mapped[Optional[bool]] = mapped_column(Boolean)
    no_network_in_sandbox: Mapped[Optional[bool]] = mapped_column(Boolean)
    code_signed: Mapped[Optional[bool]] = mapped_column(Boolean)

    # State
    status: Mapped[str] = mapped_column(String(30), default="proposed")
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    sandbox_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sandbox_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "evolution_type IN ('random_mutation', 'llm_guided', 'crossover', "
            "'simplification', 'refactoring', 'bug_fix')",
            name="ck_evolution_type",
        ),
        CheckConstraint(
            "status IN ('proposed', 'sandbox_testing', 'sandbox_passed', 'sandbox_failed', "
            "'approved', 'rejected', 'deployed', 'rolled_back')",
            name="ck_evolution_status",
        ),
    )

    @property
    def sandbox_success_rate(self) -> Optional[float]:
        """Calculate sandbox test success rate."""
        if self.sandbox_tests_run and self.sandbox_tests_run > 0:
            return (self.sandbox_tests_passed or 0) / self.sandbox_tests_run
        return None

    @property
    def all_security_checks_passed(self) -> bool:
        """Check if all security checks passed."""
        return all([
            self.static_analysis_passed,
            self.no_dangerous_calls,
            self.no_network_in_sandbox,
        ])

    def __repr__(self) -> str:
        return f"<CodeEvolution(id='{self.id}', type='{self.evolution_type}', status='{self.status}')>"
