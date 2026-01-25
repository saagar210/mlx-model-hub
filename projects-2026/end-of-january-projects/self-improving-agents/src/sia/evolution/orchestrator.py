"""
Evolution Orchestrator.

Coordinates the full evolution cycle:
mutation → sandbox → validate → deploy/rollback
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from uuid import UUID, uuid4

from sia.evolution.mutator import CodeMutator, Mutation, MutationResult
from sia.evolution.rollback import CodeSnapshot, RollbackManager, RollbackResult
from sia.evolution.sandbox import RestrictedSandbox, SandboxConfig, SandboxResult
from sia.evolution.strategies import (
    CrossoverStrategy,
    EvolutionaryStrategy,
    LLMGuidedStrategy,
    MutationProposal,
    MutationStrategy,
    RandomMutationStrategy,
    get_strategy,
    list_strategies,
)
from sia.evolution.validator import CodeValidator, ValidationResult

logger = logging.getLogger(__name__)


class EvolutionStatus(str, Enum):
    """Status of an evolution attempt."""

    PROPOSED = "proposed"
    TESTING = "testing"
    VALIDATING = "validating"
    PENDING_APPROVAL = "pending_approval"  # Awaiting human approval
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class EvolutionAttempt:
    """Represents a single evolution attempt."""

    id: UUID = field(default_factory=uuid4)
    agent_id: str = ""
    status: EvolutionStatus = EvolutionStatus.PROPOSED

    # Proposal
    proposal: MutationProposal | None = None
    strategy_name: str = ""

    # Code
    original_code: str = ""
    mutated_code: str = ""

    # Results
    mutation_result: MutationResult | None = None
    validation_result: ValidationResult | None = None
    sandbox_result: SandboxResult | None = None

    # Metrics
    baseline_metrics: dict[str, float] = field(default_factory=dict)
    new_metrics: dict[str, float] = field(default_factory=dict)
    improvement: dict[str, float] = field(default_factory=dict)

    # Decision
    approved: bool = False
    rejection_reason: str = ""
    decided_by: str = ""  # 'automated' or 'human:<user_id>'

    # Deployment
    deployed_at: datetime | None = None
    snapshot_id: UUID | None = None
    rolled_back: bool = False
    rollback_reason: str = ""

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None


@dataclass
class EvolutionConfig:
    """Configuration for evolution orchestration."""

    # Strategy selection
    strategies: list[str] = field(default_factory=lambda: ["llm_guided", "random"])
    strategy_weights: dict[str, float] = field(default_factory=dict)

    # Validation thresholds
    min_validation_score: float = 0.8
    require_syntax_valid: bool = True
    require_security_valid: bool = True
    enable_type_checking: bool = False

    # Improvement thresholds
    min_improvement: float = 0.05  # 5% improvement required
    max_regression: float = 0.02  # 2% regression tolerated

    # Safety
    sandbox_enabled: bool = True
    sandbox_timeout: int = 60
    max_memory_mb: int = 512

    # Deployment
    auto_deploy: bool = False
    require_human_approval: bool = True
    a_b_test_percentage: float = 0.0

    # Limits
    max_attempts_per_run: int = 10
    max_mutations_per_attempt: int = 5


class EvolutionOrchestrator:
    """
    Orchestrates the evolution of agent code.

    Coordinates:
    1. Strategy selection and mutation proposal
    2. Code mutation
    3. Sandbox testing
    4. Validation
    5. Metric comparison
    6. Approval decision
    7. Deployment or rollback
    """

    def __init__(
        self,
        config: EvolutionConfig | None = None,
        rollback_manager: RollbackManager | None = None,
        llm_client: Any = None,
    ):
        """
        Initialize evolution orchestrator.

        Args:
            config: Evolution configuration
            rollback_manager: Rollback manager instance
            llm_client: LLM client for LLM-guided strategies
        """
        self.config = config or EvolutionConfig()
        self.rollback_manager = rollback_manager or RollbackManager()
        self.llm_client = llm_client

        # Initialize components
        self.mutator = CodeMutator()
        self.validator = CodeValidator(
            enable_type_checking=self.config.enable_type_checking,
            enable_security_checking=True,
            security_level="high" if self.config.require_security_valid else "medium",
        )

        # Track attempts
        self.attempts: list[EvolutionAttempt] = []
        self.current_attempt: EvolutionAttempt | None = None

        # Callbacks
        self._on_proposal: Callable[[EvolutionAttempt], None] | None = None
        self._on_validation: Callable[[EvolutionAttempt], None] | None = None
        self._on_decision: Callable[[EvolutionAttempt], None] | None = None
        self._on_deploy: Callable[[EvolutionAttempt], None] | None = None

    def set_callback(self, event: str, callback: Callable) -> None:
        """Set callback for evolution events."""
        if event == "proposal":
            self._on_proposal = callback
        elif event == "validation":
            self._on_validation = callback
        elif event == "decision":
            self._on_decision = callback
        elif event == "deploy":
            self._on_deploy = callback

    async def evolve(
        self,
        code: str,
        agent_id: str = "",
        context: dict[str, Any] | None = None,
        fitness_fn: Callable[[str], float] | None = None,
    ) -> EvolutionAttempt:
        """
        Run a single evolution attempt.

        Args:
            code: Current agent code
            agent_id: Agent identifier
            context: Additional context for strategies
            fitness_fn: Function to evaluate code fitness

        Returns:
            EvolutionAttempt with results
        """
        attempt = EvolutionAttempt(
            agent_id=agent_id,
            original_code=code,
        )
        self.current_attempt = attempt
        self.attempts.append(attempt)

        try:
            # 1. Get mutation proposal
            proposal = await self._get_proposal(code, context)
            if not proposal:
                attempt.status = EvolutionStatus.FAILED
                attempt.rejection_reason = "No valid proposal generated"
                return attempt

            attempt.proposal = proposal
            attempt.strategy_name = proposal.strategy

            if self._on_proposal:
                self._on_proposal(attempt)

            # 2. Apply mutations
            mutation_result = self._apply_mutations(code, proposal.mutations)
            attempt.mutation_result = mutation_result

            if not mutation_result.success:
                attempt.status = EvolutionStatus.FAILED
                attempt.rejection_reason = f"Mutation failed: {mutation_result.error}"
                return attempt

            attempt.mutated_code = mutation_result.mutated_code

            # 3. Validate mutated code
            validation_result = self._validate(mutation_result.mutated_code)
            attempt.validation_result = validation_result
            attempt.status = EvolutionStatus.VALIDATING

            if self._on_validation:
                self._on_validation(attempt)

            if not self._passes_validation(validation_result):
                attempt.status = EvolutionStatus.REJECTED
                attempt.rejection_reason = self._get_validation_rejection_reason(
                    validation_result
                )
                return attempt

            # 4. Sandbox testing (if enabled)
            if self.config.sandbox_enabled:
                sandbox_result = await self._run_sandbox_tests(
                    mutation_result.mutated_code
                )
                attempt.sandbox_result = sandbox_result

                if not sandbox_result.success:
                    attempt.status = EvolutionStatus.REJECTED
                    attempt.rejection_reason = f"Sandbox tests failed: {sandbox_result.error}"
                    return attempt

            # 5. Evaluate metrics
            if fitness_fn:
                try:
                    baseline_fitness = fitness_fn(code)
                    new_fitness = fitness_fn(mutation_result.mutated_code)

                    attempt.baseline_metrics["fitness"] = baseline_fitness
                    attempt.new_metrics["fitness"] = new_fitness
                    attempt.improvement["fitness"] = new_fitness - baseline_fitness
                except Exception as e:
                    logger.warning(f"Fitness evaluation failed: {e}")

            # 6. Make decision (or wait for human approval)
            if self.config.require_human_approval:
                # Human approval required - don't auto-approve
                attempt.status = EvolutionStatus.PENDING_APPROVAL
                attempt.decided_by = ""  # Not decided yet
                logger.info(f"Evolution {attempt.id} awaiting human approval")
            else:
                # Automated decision
                decision = self._make_decision(attempt)
                attempt.approved = decision
                attempt.decided_by = "automated"
                attempt.status = (
                    EvolutionStatus.APPROVED if decision else EvolutionStatus.REJECTED
                )

                if not decision:
                    attempt.rejection_reason = self._get_rejection_reason(attempt)

            if self._on_decision:
                self._on_decision(attempt)

            # 7. Deploy if auto-deploy enabled and approved (and not requiring human approval)
            if (attempt.approved and self.config.auto_deploy
                    and not self.config.require_human_approval):
                await self.deploy(attempt)

            attempt.completed_at = datetime.now()
            return attempt

        except Exception as e:
            logger.error(f"Evolution failed: {e}")
            attempt.status = EvolutionStatus.FAILED
            attempt.rejection_reason = str(e)
            attempt.completed_at = datetime.now()
            return attempt

    async def evolve_multiple(
        self,
        code: str,
        agent_id: str = "",
        context: dict[str, Any] | None = None,
        fitness_fn: Callable[[str], float] | None = None,
        max_attempts: int | None = None,
    ) -> list[EvolutionAttempt]:
        """
        Run multiple evolution attempts and return best results.

        Args:
            code: Current agent code
            agent_id: Agent identifier
            context: Additional context
            fitness_fn: Fitness function
            max_attempts: Override config max_attempts

        Returns:
            List of evolution attempts, sorted by improvement
        """
        max_attempts = max_attempts or self.config.max_attempts_per_run
        attempts = []

        for i in range(max_attempts):
            attempt = await self.evolve(code, agent_id, context, fitness_fn)
            attempts.append(attempt)

            # If we found a good improvement, optionally stop early
            if attempt.approved and attempt.improvement.get("fitness", 0) > 0.1:
                logger.info(f"Found significant improvement on attempt {i + 1}")
                break

        # Sort by improvement
        attempts.sort(
            key=lambda a: a.improvement.get("fitness", float("-inf")),
            reverse=True,
        )

        return attempts

    async def _get_proposal(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> MutationProposal | None:
        """Get a mutation proposal using configured strategies."""
        context = context or {}

        for strategy_name in self.config.strategies:
            try:
                # Create strategy with appropriate config
                kwargs = {}
                if strategy_name in ("llm_guided", "error_fix"):
                    kwargs["llm_client"] = self.llm_client

                strategy = get_strategy(strategy_name, **kwargs)

                # Get proposals
                proposals = strategy.propose_mutations(code, context)

                if proposals:
                    # Filter by confidence
                    valid_proposals = [
                        p for p in proposals
                        if p.confidence >= 0.3  # Minimum confidence
                    ]

                    if valid_proposals:
                        # Sort by confidence and return best
                        valid_proposals.sort(key=lambda p: p.confidence, reverse=True)
                        return valid_proposals[0]

            except Exception as e:
                logger.warning(f"Strategy {strategy_name} failed: {e}")
                continue

        return None

    def _apply_mutations(
        self,
        code: str,
        mutations: list[Mutation],
    ) -> MutationResult:
        """Apply mutations to code."""
        return self.mutator.mutate(code, mutations)

    def _validate(self, code: str) -> ValidationResult:
        """Validate mutated code."""
        return self.validator.validate(code)

    def _passes_validation(self, result: ValidationResult) -> bool:
        """Check if validation result passes configured thresholds."""
        if self.config.require_syntax_valid and not result.syntax_valid:
            return False

        if self.config.require_security_valid and not result.security_valid:
            return False

        if result.overall_score < self.config.min_validation_score:
            return False

        return True

    def _get_validation_rejection_reason(self, result: ValidationResult) -> str:
        """Get human-readable rejection reason from validation."""
        reasons = []

        if not result.syntax_valid:
            reasons.append("syntax errors")

        if not result.security_valid:
            security_issues = [
                i.message for i in result.issues
                if i.category == "security" and i.severity == "error"
            ]
            reasons.append(f"security issues: {', '.join(security_issues[:3])}")

        if result.overall_score < self.config.min_validation_score:
            reasons.append(
                f"validation score {result.overall_score:.2f} below "
                f"threshold {self.config.min_validation_score}"
            )

        return "; ".join(reasons) if reasons else "validation failed"

    async def _run_sandbox_tests(self, code: str) -> SandboxResult:
        """Run code in sandbox environment using RestrictedPython."""
        config = SandboxConfig(
            timeout_seconds=self.config.sandbox_timeout,
            max_memory_mb=self.config.max_memory_mb,
            security_mode="high",
        )

        sandbox = RestrictedSandbox(config)

        # Set status to TESTING before running tests
        if self.current_attempt:
            self.current_attempt.status = EvolutionStatus.TESTING

        # Validate syntax first (fast check)
        result = await sandbox.validate_syntax(code)
        if not result.success:
            return result

        # Check imports against whitelist
        result = await sandbox.check_imports(code)
        if not result.success:
            return result

        # Execute code in restricted environment
        result = await sandbox.execute(code)
        return result

    def _make_decision(self, attempt: EvolutionAttempt) -> bool:
        """Make automated approval decision."""
        # Must pass validation
        if attempt.validation_result and not self._passes_validation(
            attempt.validation_result
        ):
            return False

        # Check improvement threshold
        fitness_improvement = attempt.improvement.get("fitness", 0)

        if fitness_improvement < -self.config.max_regression:
            # Regression too large
            return False

        if fitness_improvement >= self.config.min_improvement:
            # Good improvement
            return True

        # Marginal improvement - be conservative
        return False

    def _get_rejection_reason(self, attempt: EvolutionAttempt) -> str:
        """Get rejection reason for attempt."""
        reasons = []

        fitness_improvement = attempt.improvement.get("fitness", 0)

        if fitness_improvement < -self.config.max_regression:
            reasons.append(
                f"regression {abs(fitness_improvement):.1%} exceeds "
                f"threshold {self.config.max_regression:.1%}"
            )

        if fitness_improvement < self.config.min_improvement:
            reasons.append(
                f"improvement {fitness_improvement:.1%} below "
                f"threshold {self.config.min_improvement:.1%}"
            )

        return "; ".join(reasons) if reasons else "did not meet improvement criteria"

    async def deploy(self, attempt: EvolutionAttempt) -> bool:
        """
        Deploy an approved evolution attempt.

        Args:
            attempt: The attempt to deploy

        Returns:
            True if deployment successful
        """
        if not attempt.approved:
            logger.error("Cannot deploy unapproved attempt")
            return False

        if attempt.status == EvolutionStatus.DEPLOYED:
            logger.warning("Attempt already deployed")
            return True

        try:
            # Create snapshot before deploying
            snapshot = self.rollback_manager.create_snapshot(
                code=attempt.mutated_code,
                description=f"Evolution: {attempt.proposal.rationale if attempt.proposal else 'unknown'}",
                source="evolution",
                metrics=attempt.new_metrics,
                strategy_used=attempt.strategy_name,
                mutation_ids=[m.id for m in attempt.proposal.mutations] if attempt.proposal else [],
            )

            attempt.snapshot_id = snapshot.id
            attempt.status = EvolutionStatus.DEPLOYED
            attempt.deployed_at = datetime.now()
            attempt.decided_by = "automated"

            if self._on_deploy:
                self._on_deploy(attempt)

            logger.info(f"Deployed evolution {attempt.id} as version {snapshot.version}")
            return True

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            attempt.status = EvolutionStatus.FAILED
            return False

    async def rollback(
        self,
        attempt: EvolutionAttempt,
        reason: str = "",
    ) -> RollbackResult:
        """
        Rollback a deployed evolution attempt.

        Args:
            attempt: The attempt to rollback
            reason: Reason for rollback

        Returns:
            RollbackResult
        """
        if attempt.status != EvolutionStatus.DEPLOYED:
            return RollbackResult(
                success=False,
                previous_version="",
                rolled_back_to="",
                snapshot_id=uuid4(),
                message="Attempt was not deployed",
            )

        result = self.rollback_manager.rollback(steps=1)

        if result.success:
            attempt.status = EvolutionStatus.ROLLED_BACK
            attempt.rolled_back = True
            attempt.rollback_reason = reason
            logger.info(f"Rolled back evolution {attempt.id}: {reason}")

        return result

    def approve_manually(self, attempt_id: UUID, approver: str = "human") -> bool:
        """
        Manually approve an evolution attempt.

        Can approve attempts in PENDING_APPROVAL or VALIDATING status.
        """
        for attempt in self.attempts:
            if attempt.id == attempt_id:
                if attempt.status == EvolutionStatus.APPROVED:
                    return True

                if attempt.status not in (
                    EvolutionStatus.PENDING_APPROVAL,
                    EvolutionStatus.VALIDATING,
                ):
                    logger.warning(
                        f"Cannot approve attempt {attempt_id} in status {attempt.status}"
                    )
                    return False

                attempt.approved = True
                attempt.status = EvolutionStatus.APPROVED
                attempt.decided_by = f"human:{approver}"
                logger.info(f"Evolution {attempt_id} approved by {approver}")
                return True

        return False

    def is_pending_approval(self, attempt_id: UUID) -> bool:
        """Check if an attempt is awaiting human approval."""
        for attempt in self.attempts:
            if attempt.id == attempt_id:
                return attempt.status == EvolutionStatus.PENDING_APPROVAL
        return False

    def reject_manually(
        self,
        attempt_id: UUID,
        reason: str,
        rejector: str = "human",
    ) -> bool:
        """Manually reject an evolution attempt."""
        for attempt in self.attempts:
            if attempt.id == attempt_id:
                attempt.approved = False
                attempt.status = EvolutionStatus.REJECTED
                attempt.rejection_reason = reason
                attempt.decided_by = f"human:{rejector}"
                return True

        return False

    def get_attempt(self, attempt_id: UUID) -> EvolutionAttempt | None:
        """Get an attempt by ID."""
        for attempt in self.attempts:
            if attempt.id == attempt_id:
                return attempt
        return None

    def get_recent_attempts(
        self,
        limit: int = 10,
        status: EvolutionStatus | None = None,
    ) -> list[EvolutionAttempt]:
        """Get recent evolution attempts."""
        attempts = self.attempts

        if status:
            attempts = [a for a in attempts if a.status == status]

        # Sort by created_at descending
        attempts = sorted(attempts, key=lambda a: a.created_at, reverse=True)

        return attempts[:limit]

    def get_statistics(self) -> dict[str, Any]:
        """Get evolution statistics."""
        total = len(self.attempts)

        if total == 0:
            return {
                "total_attempts": 0,
                "approval_rate": 0,
                "deployment_rate": 0,
                "rollback_rate": 0,
            }

        approved = sum(1 for a in self.attempts if a.approved)
        deployed = sum(1 for a in self.attempts if a.status == EvolutionStatus.DEPLOYED)
        rolled_back = sum(1 for a in self.attempts if a.rolled_back)

        improvements = [
            a.improvement.get("fitness", 0)
            for a in self.attempts
            if a.improvement.get("fitness") is not None
        ]

        return {
            "total_attempts": total,
            "approved": approved,
            "deployed": deployed,
            "rolled_back": rolled_back,
            "approval_rate": approved / total,
            "deployment_rate": deployed / total,
            "rollback_rate": rolled_back / max(deployed, 1),
            "avg_improvement": sum(improvements) / len(improvements) if improvements else 0,
            "max_improvement": max(improvements) if improvements else 0,
            "strategies_used": list(set(a.strategy_name for a in self.attempts if a.strategy_name)),
        }


# Convenience function
async def evolve_code(
    code: str,
    agent_id: str = "",
    config: EvolutionConfig | None = None,
    fitness_fn: Callable[[str], float] | None = None,
) -> EvolutionAttempt:
    """
    Convenience function to evolve code.

    Args:
        code: Code to evolve
        agent_id: Agent identifier
        config: Evolution configuration
        fitness_fn: Fitness function

    Returns:
        EvolutionAttempt with results
    """
    orchestrator = EvolutionOrchestrator(config=config)
    return await orchestrator.evolve(code, agent_id, fitness_fn=fitness_fn)
