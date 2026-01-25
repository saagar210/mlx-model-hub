"""
Optimization Runner.

Orchestrates DSPy optimization runs, tracking history and deploying results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

import dspy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.models.agent import Agent
from sia.optimization.data_collector import TrainingDataCollector
from sia.optimization.metrics import METRIC_REGISTRY, get_metric
from sia.optimization.miprov2_optimizer import (
    MIPROv2Config,
    MIPROv2Optimizer,
    OptimizationResult,
)
from sia.optimization.modules import MODULE_REGISTRY, create_module
from sia.optimization.simba_optimizer import SIMBAConfig, SIMBAOptimizer, SIMBAResult


# ============================================================================
# Run Types
# ============================================================================


@dataclass
class OptimizationRun:
    """A scheduled or completed optimization run."""

    id: UUID = field(default_factory=uuid4)
    agent_id: UUID | None = None
    agent_name: str = ""
    module_name: str = ""

    # Configuration
    optimizer_type: str = "miprov2"  # 'miprov2' or 'simba'
    config: dict[str, Any] = field(default_factory=dict)

    # Data
    training_examples: int = 0
    validation_examples: int = 0

    # Results
    baseline_score: float = 0.0
    optimized_score: float = 0.0
    improvement: float = 0.0
    improvement_pct: float = 0.0

    # Status
    status: str = "pending"  # pending, running, completed, failed, deployed
    error: str | None = None

    # Artifacts
    optimized_module_path: str | None = None
    result_path: str | None = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    deployed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "agent_id": str(self.agent_id) if self.agent_id else None,
            "agent_name": self.agent_name,
            "module_name": self.module_name,
            "optimizer_type": self.optimizer_type,
            "config": self.config,
            "training_examples": self.training_examples,
            "validation_examples": self.validation_examples,
            "baseline_score": self.baseline_score,
            "optimized_score": self.optimized_score,
            "improvement": self.improvement,
            "improvement_pct": self.improvement_pct,
            "status": self.status,
            "error": self.error,
            "optimized_module_path": self.optimized_module_path,
            "result_path": self.result_path,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OptimizationRun":
        """Create from dictionary."""
        run = cls(
            id=UUID(data["id"]),
            agent_id=UUID(data["agent_id"]) if data.get("agent_id") else None,
            agent_name=data.get("agent_name", ""),
            module_name=data.get("module_name", ""),
            optimizer_type=data.get("optimizer_type", "miprov2"),
            config=data.get("config", {}),
            training_examples=data.get("training_examples", 0),
            validation_examples=data.get("validation_examples", 0),
            baseline_score=data.get("baseline_score", 0.0),
            optimized_score=data.get("optimized_score", 0.0),
            improvement=data.get("improvement", 0.0),
            improvement_pct=data.get("improvement_pct", 0.0),
            status=data.get("status", "pending"),
            error=data.get("error"),
            optimized_module_path=data.get("optimized_module_path"),
            result_path=data.get("result_path"),
        )

        if data.get("created_at"):
            run.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            run.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            run.completed_at = datetime.fromisoformat(data["completed_at"])
        if data.get("deployed_at"):
            run.deployed_at = datetime.fromisoformat(data["deployed_at"])

        return run


# ============================================================================
# Optimization Runner
# ============================================================================


class OptimizationRunner:
    """
    Orchestrates optimization runs.

    Handles:
    - Collecting training data
    - Running optimizers
    - Saving results
    - Deploying optimized modules
    """

    def __init__(
        self,
        session: AsyncSession,
        artifacts_path: str | Path = "optimization_artifacts",
        history_path: str | Path = "optimization_history.json",
    ):
        """
        Initialize optimization runner.

        Args:
            session: Database session
            artifacts_path: Path to save optimized modules
            history_path: Path to save run history
        """
        self.session = session
        self.artifacts_path = Path(artifacts_path)
        self.history_path = Path(history_path)
        self.runs: list[OptimizationRun] = []

        # Load existing history
        self._load_history()

    def _load_history(self) -> None:
        """Load run history from disk."""
        if self.history_path.exists():
            with open(self.history_path) as f:
                data = json.load(f)
                self.runs = [OptimizationRun.from_dict(r) for r in data]

    def _save_history(self) -> None:
        """Save run history to disk."""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_path, "w") as f:
            json.dump([r.to_dict() for r in self.runs], f, indent=2)

    async def run_optimization(
        self,
        agent_name: str,
        optimizer_type: str = "miprov2",
        min_examples: int = 20,
        train_ratio: float = 0.7,
        metric_name: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> OptimizationRun:
        """
        Run optimization for an agent.

        Args:
            agent_name: Name of the agent to optimize
            optimizer_type: 'miprov2' or 'simba'
            min_examples: Minimum training examples required
            train_ratio: Ratio of data for training
            metric_name: Name of metric to use (auto-detected if None)
            config: Optimizer configuration overrides

        Returns:
            OptimizationRun with results
        """
        # Create run record
        run = OptimizationRun(
            agent_name=agent_name,
            optimizer_type=optimizer_type,
            config=config or {},
        )
        self.runs.append(run)

        try:
            # Get agent from database
            query = select(Agent).where(Agent.name == agent_name)
            result = await self.session.execute(query)
            agent = result.scalar_one_or_none()

            if agent:
                run.agent_id = agent.id

            # Determine module and metric
            module_name = self._get_module_for_agent(agent_name)
            run.module_name = module_name

            metric = self._get_metric_for_module(module_name, metric_name)

            # Collect training data
            collector = TrainingDataCollector(self.session)
            task_type = self._get_task_type_for_module(module_name)
            examples = await collector.collect_for_task_type(
                task_type=task_type,
                limit=200,
                agent_id=run.agent_id,
            )

            if len(examples) < min_examples:
                run.status = "failed"
                run.error = f"Insufficient training data: {len(examples)} < {min_examples}"
                self._save_history()
                return run

            # Split dataset
            split = collector.split_dataset(examples, train_ratio=train_ratio)
            trainset = split.train_examples
            valset = split.validation_examples

            run.training_examples = len(trainset)
            run.validation_examples = len(valset)
            run.started_at = datetime.now()
            run.status = "running"
            self._save_history()

            # Create module
            module = create_module(module_name)

            # Run optimizer
            if optimizer_type == "miprov2":
                opt_config = MIPROv2Config(**(config or {}))
                optimizer = MIPROv2Optimizer(config=opt_config, metric=metric)
                optimized_module, opt_result = optimizer.optimize(
                    module, trainset, valset, metric
                )
                run.baseline_score = opt_result.baseline_score
                run.optimized_score = opt_result.optimized_score
                run.improvement = opt_result.improvement
                run.improvement_pct = opt_result.improvement_pct

            elif optimizer_type == "simba":
                opt_config = SIMBAConfig(**(config or {}))
                optimizer = SIMBAOptimizer(config=opt_config, metric=metric)
                optimized_module, opt_result = optimizer.optimize(
                    module, trainset, valset, metric
                )
                run.baseline_score = opt_result.baseline_score
                run.optimized_score = opt_result.final_score
                run.improvement = opt_result.improvement
                run.improvement_pct = opt_result.improvement_pct

            else:
                raise ValueError(f"Unknown optimizer type: {optimizer_type}")

            # Save artifacts
            run_path = self.artifacts_path / str(run.id)
            run_path.mkdir(parents=True, exist_ok=True)

            module_path = run_path / "module.json"
            optimized_module.save(str(module_path))
            run.optimized_module_path = str(module_path)

            result_path = run_path / "result.json"
            with open(result_path, "w") as f:
                if isinstance(opt_result, OptimizationResult):
                    json.dump(opt_result.to_dict(), f, indent=2)
                elif isinstance(opt_result, SIMBAResult):
                    json.dump(opt_result.to_dict(), f, indent=2)
            run.result_path = str(result_path)

            run.status = "completed"
            run.completed_at = datetime.now()

        except Exception as e:
            run.status = "failed"
            run.error = str(e)

        self._save_history()
        return run

    def _get_module_for_agent(self, agent_name: str) -> str:
        """Map agent name to module name."""
        name_lower = agent_name.lower()

        if "decompos" in name_lower:
            return "decomposer"
        elif "cod" in name_lower:
            return "coder"
        elif "research" in name_lower:
            return "researcher"
        elif "review" in name_lower:
            return "reviewer"
        elif "synth" in name_lower:
            return "synthesizer"
        elif "skill" in name_lower:
            return "skill_extractor"
        elif "decision" in name_lower:
            return "decision_maker"
        elif "error" in name_lower:
            return "error_analyzer"

        # Default
        return "decomposer"

    def _get_metric_for_module(
        self,
        module_name: str,
        metric_name: str | None = None,
    ) -> Callable:
        """Get appropriate metric for module."""
        if metric_name:
            return get_metric(metric_name)

        # Auto-detect based on module
        mapping = {
            "decomposer": "decomposition_quality",
            "coder": "code_correctness",
            "researcher": "research_relevance",
            "reviewer": "review_thoroughness",
            "synthesizer": "synthesis_coherence",
            "skill_extractor": "skill_extraction_quality",
            "decision_maker": "decision_quality",
            "error_analyzer": "error_analysis_quality",
        }

        metric_name = mapping.get(module_name, "decomposition_quality")
        return get_metric(metric_name)

    def _get_task_type_for_module(self, module_name: str) -> str:
        """Map module name to task type."""
        mapping = {
            "decomposer": "decomposition",
            "coder": "code_generation",
            "researcher": "research",
            "reviewer": "code_review",
            "synthesizer": "synthesis",
            "skill_extractor": "skill_extraction",
            "decision_maker": "decision",
            "error_analyzer": "error_analysis",
        }
        return mapping.get(module_name, "decomposition")

    async def deploy_optimization(
        self,
        run_id: UUID,
    ) -> bool:
        """
        Deploy an optimized module.

        Updates the agent's DSPy prompts with optimized versions.

        Args:
            run_id: ID of the optimization run to deploy

        Returns:
            True if deployed successfully
        """
        # Find run
        run = next((r for r in self.runs if r.id == run_id), None)
        if not run:
            return False

        if run.status != "completed":
            return False

        if not run.optimized_module_path or not run.agent_id:
            return False

        try:
            # Load optimized module
            module_class = MODULE_REGISTRY.get(run.module_name)
            if not module_class:
                return False

            module = module_class()
            module.load(run.optimized_module_path)

            # Extract optimized prompts
            optimized_prompts = {}
            for name, predictor in module.named_predictors():
                if hasattr(predictor, "signature"):
                    sig = predictor.signature
                    if hasattr(sig, "instructions"):
                        optimized_prompts[name] = {
                            "instructions": sig.instructions,
                        }
                if hasattr(predictor, "demos"):
                    if name not in optimized_prompts:
                        optimized_prompts[name] = {}
                    optimized_prompts[name]["demos"] = [
                        demo.toDict() if hasattr(demo, "toDict") else dict(demo)
                        for demo in predictor.demos
                    ]

            # Update agent in database
            query = select(Agent).where(Agent.id == run.agent_id)
            result = await self.session.execute(query)
            agent = result.scalar_one_or_none()

            if agent:
                agent.dspy_optimized_prompts = optimized_prompts
                await self.session.commit()

            run.status = "deployed"
            run.deployed_at = datetime.now()
            self._save_history()

            return True

        except Exception:
            return False

    def get_run(self, run_id: UUID) -> OptimizationRun | None:
        """Get a specific run by ID."""
        return next((r for r in self.runs if r.id == run_id), None)

    def get_runs_for_agent(
        self,
        agent_name: str,
        status: str | None = None,
    ) -> list[OptimizationRun]:
        """Get all runs for an agent."""
        runs = [r for r in self.runs if r.agent_name == agent_name]
        if status:
            runs = [r for r in runs if r.status == status]
        return runs

    def get_recent_runs(
        self,
        limit: int = 10,
        status: str | None = None,
    ) -> list[OptimizationRun]:
        """Get recent optimization runs."""
        runs = sorted(self.runs, key=lambda r: r.created_at, reverse=True)
        if status:
            runs = [r for r in runs if r.status == status]
        return runs[:limit]

    def compare_runs(
        self,
        run_id_1: UUID,
        run_id_2: UUID,
    ) -> dict[str, Any]:
        """Compare two optimization runs."""
        run1 = self.get_run(run_id_1)
        run2 = self.get_run(run_id_2)

        if not run1 or not run2:
            return {"error": "One or both runs not found"}

        return {
            "run_1": {
                "id": str(run1.id),
                "baseline_score": run1.baseline_score,
                "optimized_score": run1.optimized_score,
                "improvement": run1.improvement,
                "improvement_pct": run1.improvement_pct,
            },
            "run_2": {
                "id": str(run2.id),
                "baseline_score": run2.baseline_score,
                "optimized_score": run2.optimized_score,
                "improvement": run2.improvement,
                "improvement_pct": run2.improvement_pct,
            },
            "comparison": {
                "score_difference": run2.optimized_score - run1.optimized_score,
                "improvement_difference": run2.improvement - run1.improvement,
                "better_run": str(run1.id)
                if run1.optimized_score > run2.optimized_score
                else str(run2.id),
            },
        }


# ============================================================================
# Scheduled Optimization
# ============================================================================


class ScheduledOptimizer:
    """
    Run optimizations on a schedule.

    Periodically checks for agents that need optimization.
    """

    def __init__(
        self,
        runner: OptimizationRunner,
        check_interval_hours: int = 24,
        min_new_examples: int = 50,
    ):
        """
        Initialize scheduled optimizer.

        Args:
            runner: Optimization runner to use
            check_interval_hours: Hours between checks
            min_new_examples: Minimum new examples before re-optimization
        """
        self.runner = runner
        self.check_interval_hours = check_interval_hours
        self.min_new_examples = min_new_examples

    async def check_and_optimize(
        self,
        agent_names: list[str] | None = None,
    ) -> list[OptimizationRun]:
        """
        Check agents and run optimization if needed.

        Args:
            agent_names: Specific agents to check (or all if None)

        Returns:
            List of optimization runs started
        """
        runs = []

        if agent_names is None:
            # Get all active agents
            query = select(Agent).where(Agent.status == "active")
            result = await self.runner.session.execute(query)
            agents = result.scalars().all()
            agent_names = [a.name for a in agents]

        for agent_name in agent_names:
            if self._should_optimize(agent_name):
                run = await self.runner.run_optimization(agent_name)
                runs.append(run)

        return runs

    def _should_optimize(self, agent_name: str) -> bool:
        """Check if agent should be optimized."""
        # Get last successful run
        agent_runs = self.runner.get_runs_for_agent(agent_name, status="completed")
        if not agent_runs:
            return True  # Never optimized

        latest = max(agent_runs, key=lambda r: r.completed_at or r.created_at)

        # Check if enough time has passed
        if latest.completed_at:
            hours_since = (datetime.now() - latest.completed_at).total_seconds() / 3600
            if hours_since < self.check_interval_hours:
                return False

        return True
