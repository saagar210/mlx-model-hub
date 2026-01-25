"""
MIPROv2 Optimizer for DSPy.

Implements instruction and few-shot optimization using DSPy's MIPROv2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

import dspy

from sia.optimization.metrics import METRIC_REGISTRY


# ============================================================================
# Optimization Configuration
# ============================================================================


@dataclass
class MIPROv2Config:
    """Configuration for MIPROv2 optimization."""

    # Number of bootstrapped demos per signature
    num_candidates: int = 10

    # Number of instruction candidates to try
    num_instructions: int = 5

    # Maximum demos per signature
    max_demos: int = 4

    # Number of optimization trials
    num_trials: int = 20

    # Minimum improvement required to accept
    min_improvement: float = 0.05

    # Temperature for demo selection
    temperature: float = 0.7

    # Whether to use Bayesian optimization
    use_bayesian: bool = True

    # Seed for reproducibility
    seed: int | None = None

    # Verbose output
    verbose: bool = True


@dataclass
class OptimizationResult:
    """Result of an optimization run."""

    id: UUID = field(default_factory=uuid4)
    module_name: str = ""
    signature_name: str = ""

    # Scores
    baseline_score: float = 0.0
    optimized_score: float = 0.0
    improvement: float = 0.0
    improvement_pct: float = 0.0

    # Optimized artifacts
    optimized_instructions: dict[str, str] = field(default_factory=dict)
    optimized_demos: dict[str, list] = field(default_factory=dict)

    # Trial history
    trial_history: list[dict[str, Any]] = field(default_factory=list)
    best_trial: int = 0

    # Metadata
    config: MIPROv2Config | None = None
    training_examples: int = 0
    validation_examples: int = 0
    duration_seconds: float = 0.0

    # Timestamps
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    # Status
    success: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "module_name": self.module_name,
            "signature_name": self.signature_name,
            "baseline_score": self.baseline_score,
            "optimized_score": self.optimized_score,
            "improvement": self.improvement,
            "improvement_pct": self.improvement_pct,
            "optimized_instructions": self.optimized_instructions,
            "optimized_demos": self.optimized_demos,
            "trial_history": self.trial_history,
            "best_trial": self.best_trial,
            "training_examples": self.training_examples,
            "validation_examples": self.validation_examples,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "error": self.error,
        }


# ============================================================================
# MIPROv2 Optimizer
# ============================================================================


class MIPROv2Optimizer:
    """
    Optimizes DSPy modules using MIPROv2 algorithm.

    MIPROv2 (Multi-stage Instruction PRoposal and Optimization):
    1. Bootstrap demonstrations from training examples
    2. Generate instruction candidates
    3. Use Bayesian optimization to find best combo
    """

    def __init__(
        self,
        config: MIPROv2Config | None = None,
        metric: Callable | None = None,
        teacher_lm: dspy.LM | None = None,
    ):
        """
        Initialize MIPROv2 optimizer.

        Args:
            config: Optimization configuration
            metric: Evaluation metric function
            teacher_lm: Language model for generating demos
        """
        self.config = config or MIPROv2Config()
        self.metric = metric
        self.teacher_lm = teacher_lm

    def optimize(
        self,
        module: dspy.Module,
        trainset: list[dspy.Example],
        valset: list[dspy.Example] | None = None,
        metric: Callable | None = None,
    ) -> tuple[dspy.Module, OptimizationResult]:
        """
        Optimize a DSPy module.

        Args:
            module: Module to optimize
            trainset: Training examples
            valset: Validation examples (optional)
            metric: Override metric for this run

        Returns:
            Tuple of (optimized_module, result)
        """
        result = OptimizationResult(
            module_name=module.__class__.__name__,
            training_examples=len(trainset),
            validation_examples=len(valset) if valset else 0,
            config=self.config,
        )

        try:
            # Use provided metric or instance metric
            eval_metric = metric or self.metric
            if eval_metric is None:
                raise ValueError("No metric provided for optimization")

            # Calculate baseline score
            result.baseline_score = self._evaluate(module, valset or trainset, eval_metric)

            # Run MIPROv2 optimization
            try:
                from dspy.teleprompt import MIPROv2

                optimizer = MIPROv2(
                    metric=eval_metric,
                    num_candidates=self.config.num_candidates,
                    num_threads=1,  # Keep single-threaded for stability
                    verbose=self.config.verbose,
                )

                optimized = optimizer.compile(
                    module,
                    trainset=trainset,
                    num_trials=self.config.num_trials,
                    max_bootstrapped_demos=self.config.max_demos,
                    max_labeled_demos=self.config.max_demos,
                    requires_permission_to_run=False,
                )

            except ImportError:
                # Fallback to BootstrapFewShot if MIPROv2 not available
                from dspy.teleprompt import BootstrapFewShot

                optimizer = BootstrapFewShot(
                    metric=eval_metric,
                    max_bootstrapped_demos=self.config.max_demos,
                    max_labeled_demos=self.config.max_demos,
                )

                optimized = optimizer.compile(
                    module,
                    trainset=trainset,
                )

            # Calculate optimized score
            result.optimized_score = self._evaluate(
                optimized, valset or trainset, eval_metric
            )

            # Calculate improvement
            result.improvement = result.optimized_score - result.baseline_score
            if result.baseline_score > 0:
                result.improvement_pct = result.improvement / result.baseline_score
            else:
                result.improvement_pct = 1.0 if result.improvement > 0 else 0.0

            # Extract optimized components
            result.optimized_instructions = self._extract_instructions(optimized)
            result.optimized_demos = self._extract_demos(optimized)

            result.success = result.improvement >= self.config.min_improvement
            result.completed_at = datetime.now()
            result.duration_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()

            return optimized, result

        except Exception as e:
            result.error = str(e)
            result.completed_at = datetime.now()
            result.duration_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()
            return module, result

    def _evaluate(
        self,
        module: dspy.Module,
        examples: list[dspy.Example],
        metric: Callable,
    ) -> float:
        """Evaluate module on examples."""
        if not examples:
            return 0.0

        scores = []
        for example in examples:
            try:
                # Get prediction
                inputs = {k: v for k, v in example.items() if k in example.inputs()}
                prediction = module(**inputs)

                # Calculate score
                score = metric(example, prediction)
                scores.append(score)
            except Exception:
                scores.append(0.0)

        return sum(scores) / len(scores) if scores else 0.0

    def _extract_instructions(self, module: dspy.Module) -> dict[str, str]:
        """Extract optimized instructions from module."""
        instructions = {}

        for name, predictor in module.named_predictors():
            if hasattr(predictor, "signature"):
                sig = predictor.signature
                if hasattr(sig, "instructions"):
                    instructions[name] = sig.instructions

        return instructions

    def _extract_demos(self, module: dspy.Module) -> dict[str, list]:
        """Extract optimized demonstrations from module."""
        demos = {}

        for name, predictor in module.named_predictors():
            if hasattr(predictor, "demos"):
                demos[name] = [
                    demo.toDict() if hasattr(demo, "toDict") else dict(demo)
                    for demo in predictor.demos
                ]

        return demos

    def save_optimized(
        self,
        module: dspy.Module,
        result: OptimizationResult,
        path: str | Path,
    ) -> None:
        """
        Save optimized module and result.

        Args:
            module: Optimized module
            result: Optimization result
            path: Directory to save to
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save module state
        module_path = path / f"{result.module_name}_optimized.json"
        module.save(str(module_path))

        # Save result
        result_path = path / f"{result.module_name}_result.json"
        with open(result_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

    def load_optimized(
        self,
        module_class: type[dspy.Module],
        path: str | Path,
    ) -> dspy.Module:
        """
        Load an optimized module.

        Args:
            module_class: Class of the module to load
            path: Path to the saved module

        Returns:
            Loaded optimized module
        """
        module = module_class()
        module.load(str(path))
        return module


# ============================================================================
# Batch Optimizer
# ============================================================================


class BatchMIPROv2Optimizer:
    """
    Optimize multiple modules in batch.

    Useful for optimizing all agents at once.
    """

    def __init__(
        self,
        config: MIPROv2Config | None = None,
        metrics: dict[str, Callable] | None = None,
    ):
        """
        Initialize batch optimizer.

        Args:
            config: Shared optimization configuration
            metrics: Dict mapping module names to metrics
        """
        self.config = config or MIPROv2Config()
        self.metrics = metrics or {}

    def optimize_all(
        self,
        modules: dict[str, dspy.Module],
        datasets: dict[str, tuple[list, list]],
    ) -> dict[str, tuple[dspy.Module, OptimizationResult]]:
        """
        Optimize all provided modules.

        Args:
            modules: Dict mapping names to modules
            datasets: Dict mapping names to (trainset, valset) tuples

        Returns:
            Dict mapping names to (optimized_module, result) tuples
        """
        results = {}

        for name, module in modules.items():
            if name not in datasets:
                continue

            trainset, valset = datasets[name]
            metric = self.metrics.get(name)

            if metric is None:
                # Try to infer metric from module name
                metric = self._infer_metric(name)

            if metric is None:
                continue

            optimizer = MIPROv2Optimizer(
                config=self.config,
                metric=metric,
            )

            optimized, result = optimizer.optimize(
                module=module,
                trainset=trainset,
                valset=valset,
                metric=metric,
            )

            results[name] = (optimized, result)

        return results

    def _infer_metric(self, module_name: str) -> Callable | None:
        """Infer metric from module name."""
        name_lower = module_name.lower()

        if "decompos" in name_lower:
            return METRIC_REGISTRY.get("decomposition_quality")
        elif "cod" in name_lower and "gen" in name_lower:
            return METRIC_REGISTRY.get("code_correctness")
        elif "research" in name_lower:
            return METRIC_REGISTRY.get("research_relevance")
        elif "review" in name_lower:
            return METRIC_REGISTRY.get("review_thoroughness")
        elif "synth" in name_lower:
            return METRIC_REGISTRY.get("synthesis_coherence")
        elif "skill" in name_lower:
            return METRIC_REGISTRY.get("skill_extraction_quality")
        elif "decision" in name_lower:
            return METRIC_REGISTRY.get("decision_quality")
        elif "error" in name_lower:
            return METRIC_REGISTRY.get("error_analysis_quality")

        return None


# ============================================================================
# Incremental Optimizer
# ============================================================================


class IncrementalMIPROv2Optimizer:
    """
    Incrementally optimize modules as new data arrives.

    Maintains optimization state across runs.
    """

    def __init__(
        self,
        config: MIPROv2Config | None = None,
        state_path: str | Path | None = None,
    ):
        """
        Initialize incremental optimizer.

        Args:
            config: Optimization configuration
            state_path: Path to save/load state
        """
        self.config = config or MIPROv2Config()
        self.state_path = Path(state_path) if state_path else None
        self.state: dict[str, Any] = {}

        if self.state_path and self.state_path.exists():
            self._load_state()

    def _load_state(self) -> None:
        """Load optimization state from disk."""
        if self.state_path and self.state_path.exists():
            with open(self.state_path) as f:
                self.state = json.load(f)

    def _save_state(self) -> None:
        """Save optimization state to disk."""
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, "w") as f:
                json.dump(self.state, f, indent=2)

    def should_optimize(
        self,
        module_name: str,
        new_examples: int,
        threshold: int = 50,
    ) -> bool:
        """
        Check if module should be re-optimized.

        Args:
            module_name: Name of the module
            new_examples: Number of new training examples
            threshold: Minimum new examples before re-optimization

        Returns:
            True if should optimize
        """
        last_examples = self.state.get(module_name, {}).get("examples_used", 0)
        return new_examples - last_examples >= threshold

    def optimize_if_needed(
        self,
        module: dspy.Module,
        trainset: list[dspy.Example],
        valset: list[dspy.Example] | None = None,
        metric: Callable | None = None,
        force: bool = False,
    ) -> tuple[dspy.Module, OptimizationResult | None]:
        """
        Optimize module if enough new data is available.

        Args:
            module: Module to optimize
            trainset: Training examples
            valset: Validation examples
            metric: Evaluation metric
            force: Force optimization even if threshold not met

        Returns:
            Tuple of (module, result or None if not optimized)
        """
        module_name = module.__class__.__name__

        if not force and not self.should_optimize(module_name, len(trainset)):
            return module, None

        optimizer = MIPROv2Optimizer(
            config=self.config,
            metric=metric,
        )

        optimized, result = optimizer.optimize(
            module=module,
            trainset=trainset,
            valset=valset,
            metric=metric,
        )

        # Update state
        self.state[module_name] = {
            "examples_used": len(trainset),
            "last_score": result.optimized_score,
            "last_optimization": datetime.now().isoformat(),
            "result_id": str(result.id),
        }
        self._save_state()

        return optimized, result
