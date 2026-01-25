"""
SIMBA Optimizer for DSPy.

Implements Sample-efficient Iterative Multi-stage Bootstrap Annotation.
Focuses on hard cases and iterative improvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

import dspy


# ============================================================================
# SIMBA Configuration
# ============================================================================


@dataclass
class SIMBAConfig:
    """Configuration for SIMBA optimization."""

    # Number of optimization iterations
    num_iterations: int = 5

    # Batch size for mini-batch processing
    batch_size: int = 16

    # Focus on hard cases (low scoring examples)
    hard_case_ratio: float = 0.5

    # Maximum demos per signature
    max_demos: int = 4

    # Minimum improvement per iteration
    min_iteration_improvement: float = 0.01

    # Early stopping patience
    patience: int = 2

    # Temperature for demo selection
    temperature: float = 0.7

    # Verbose output
    verbose: bool = True

    # Seed for reproducibility
    seed: int | None = None


@dataclass
class SIMBAResult:
    """Result of a SIMBA optimization run."""

    id: UUID = field(default_factory=uuid4)
    module_name: str = ""

    # Scores per iteration
    iteration_scores: list[float] = field(default_factory=list)
    baseline_score: float = 0.0
    final_score: float = 0.0
    improvement: float = 0.0
    improvement_pct: float = 0.0

    # Convergence info
    converged_at_iteration: int | None = None
    early_stopped: bool = False

    # Hard case analysis
    hard_cases_improved: int = 0
    total_hard_cases: int = 0

    # Optimized artifacts
    optimized_instructions: dict[str, str] = field(default_factory=dict)
    optimized_demos: dict[str, list] = field(default_factory=dict)

    # Metadata
    config: SIMBAConfig | None = None
    training_examples: int = 0
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
            "iteration_scores": self.iteration_scores,
            "baseline_score": self.baseline_score,
            "final_score": self.final_score,
            "improvement": self.improvement,
            "improvement_pct": self.improvement_pct,
            "converged_at_iteration": self.converged_at_iteration,
            "early_stopped": self.early_stopped,
            "hard_cases_improved": self.hard_cases_improved,
            "total_hard_cases": self.total_hard_cases,
            "optimized_instructions": self.optimized_instructions,
            "optimized_demos": self.optimized_demos,
            "training_examples": self.training_examples,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "error": self.error,
        }


# ============================================================================
# SIMBA Optimizer
# ============================================================================


class SIMBAOptimizer:
    """
    Optimizes DSPy modules using SIMBA algorithm.

    SIMBA (Sample-efficient Iterative Multi-stage Bootstrap Annotation):
    1. Evaluate current module on all examples
    2. Identify hard cases (low scoring)
    3. Focus bootstrapping on hard cases
    4. Iterate until convergence
    """

    def __init__(
        self,
        config: SIMBAConfig | None = None,
        metric: Callable | None = None,
    ):
        """
        Initialize SIMBA optimizer.

        Args:
            config: Optimization configuration
            metric: Evaluation metric function
        """
        self.config = config or SIMBAConfig()
        self.metric = metric

    def optimize(
        self,
        module: dspy.Module,
        trainset: list[dspy.Example],
        valset: list[dspy.Example] | None = None,
        metric: Callable | None = None,
    ) -> tuple[dspy.Module, SIMBAResult]:
        """
        Optimize a DSPy module using SIMBA.

        Args:
            module: Module to optimize
            trainset: Training examples
            valset: Validation examples (optional)
            metric: Override metric for this run

        Returns:
            Tuple of (optimized_module, result)
        """
        result = SIMBAResult(
            module_name=module.__class__.__name__,
            training_examples=len(trainset),
            config=self.config,
        )

        try:
            eval_metric = metric or self.metric
            if eval_metric is None:
                raise ValueError("No metric provided for optimization")

            # Calculate baseline score
            result.baseline_score = self._evaluate(module, valset or trainset, eval_metric)
            result.iteration_scores.append(result.baseline_score)

            # Current best module
            best_module = module
            best_score = result.baseline_score
            no_improvement_count = 0

            for iteration in range(self.config.num_iterations):
                if self.config.verbose:
                    print(f"SIMBA Iteration {iteration + 1}/{self.config.num_iterations}")

                # Score all training examples
                example_scores = self._score_examples(best_module, trainset, eval_metric)

                # Identify hard cases
                hard_cases = self._get_hard_cases(trainset, example_scores)
                result.total_hard_cases = len(hard_cases)

                # Create training batch (mix of hard and random)
                batch = self._create_batch(trainset, hard_cases, example_scores)

                # Bootstrap on this batch
                improved_module = self._bootstrap_iteration(best_module, batch, eval_metric)

                # Evaluate
                new_score = self._evaluate(improved_module, valset or trainset, eval_metric)
                result.iteration_scores.append(new_score)

                if self.config.verbose:
                    print(f"  Score: {new_score:.4f} (prev: {best_score:.4f})")

                # Check improvement
                if new_score > best_score + self.config.min_iteration_improvement:
                    # Count improved hard cases
                    new_hard_scores = self._score_examples(improved_module, hard_cases, eval_metric)
                    old_hard_scores = [example_scores[trainset.index(ex)] for ex in hard_cases if ex in trainset]
                    result.hard_cases_improved = sum(
                        1 for new, old in zip(new_hard_scores, old_hard_scores)
                        if new > old
                    )

                    best_module = improved_module
                    best_score = new_score
                    no_improvement_count = 0
                else:
                    no_improvement_count += 1

                # Early stopping
                if no_improvement_count >= self.config.patience:
                    result.early_stopped = True
                    result.converged_at_iteration = iteration + 1
                    if self.config.verbose:
                        print(f"  Early stopping at iteration {iteration + 1}")
                    break

            # Final results
            result.final_score = best_score
            result.improvement = result.final_score - result.baseline_score
            if result.baseline_score > 0:
                result.improvement_pct = result.improvement / result.baseline_score
            else:
                result.improvement_pct = 1.0 if result.improvement > 0 else 0.0

            # Extract optimized components
            result.optimized_instructions = self._extract_instructions(best_module)
            result.optimized_demos = self._extract_demos(best_module)

            result.success = result.improvement > 0
            result.completed_at = datetime.now()
            result.duration_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()

            return best_module, result

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
        scores = self._score_examples(module, examples, metric)
        return sum(scores) / len(scores) if scores else 0.0

    def _score_examples(
        self,
        module: dspy.Module,
        examples: list[dspy.Example],
        metric: Callable,
    ) -> list[float]:
        """Score each example individually."""
        scores = []
        for example in examples:
            try:
                inputs = {k: v for k, v in example.items() if k in example.inputs()}
                prediction = module(**inputs)
                score = metric(example, prediction)
                scores.append(score)
            except Exception:
                scores.append(0.0)
        return scores

    def _get_hard_cases(
        self,
        examples: list[dspy.Example],
        scores: list[float],
    ) -> list[dspy.Example]:
        """Identify hard cases (low scoring examples)."""
        # Sort by score (ascending)
        sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i])

        # Take bottom portion
        num_hard = max(1, int(len(examples) * self.config.hard_case_ratio))
        hard_indices = sorted_indices[:num_hard]

        return [examples[i] for i in hard_indices]

    def _create_batch(
        self,
        all_examples: list[dspy.Example],
        hard_cases: list[dspy.Example],
        scores: list[float],
    ) -> list[dspy.Example]:
        """Create training batch mixing hard cases and random examples."""
        import random

        batch_size = min(self.config.batch_size, len(all_examples))

        # Half from hard cases
        hard_count = min(len(hard_cases), batch_size // 2)
        batch = random.sample(hard_cases, hard_count) if hard_count > 0 else []

        # Rest from random (excluding hard cases)
        remaining = [ex for ex in all_examples if ex not in batch]
        random_count = batch_size - len(batch)
        if remaining and random_count > 0:
            batch.extend(random.sample(remaining, min(random_count, len(remaining))))

        return batch

    def _bootstrap_iteration(
        self,
        module: dspy.Module,
        batch: list[dspy.Example],
        metric: Callable,
    ) -> dspy.Module:
        """Run one bootstrap iteration on the batch."""
        try:
            from dspy.teleprompt import BootstrapFewShot

            optimizer = BootstrapFewShot(
                metric=metric,
                max_bootstrapped_demos=self.config.max_demos,
                max_labeled_demos=self.config.max_demos,
            )

            return optimizer.compile(module, trainset=batch)

        except Exception:
            # Return original if bootstrap fails
            return module

    def _extract_instructions(self, module: dspy.Module) -> dict[str, str]:
        """Extract instructions from module."""
        instructions = {}
        for name, predictor in module.named_predictors():
            if hasattr(predictor, "signature"):
                sig = predictor.signature
                if hasattr(sig, "instructions"):
                    instructions[name] = sig.instructions
        return instructions

    def _extract_demos(self, module: dspy.Module) -> dict[str, list]:
        """Extract demonstrations from module."""
        demos = {}
        for name, predictor in module.named_predictors():
            if hasattr(predictor, "demos"):
                demos[name] = [
                    demo.toDict() if hasattr(demo, "toDict") else dict(demo)
                    for demo in predictor.demos
                ]
        return demos


# ============================================================================
# Adaptive SIMBA
# ============================================================================


class AdaptiveSIMBAOptimizer:
    """
    SIMBA with adaptive parameters based on performance.

    Adjusts batch size and hard case ratio based on iteration results.
    """

    def __init__(
        self,
        base_config: SIMBAConfig | None = None,
        metric: Callable | None = None,
    ):
        """
        Initialize adaptive SIMBA optimizer.

        Args:
            base_config: Base configuration (will be adapted)
            metric: Evaluation metric
        """
        self.base_config = base_config or SIMBAConfig()
        self.metric = metric

    def optimize(
        self,
        module: dspy.Module,
        trainset: list[dspy.Example],
        valset: list[dspy.Example] | None = None,
        metric: Callable | None = None,
    ) -> tuple[dspy.Module, SIMBAResult]:
        """
        Optimize with adaptive parameters.

        Adjusts configuration based on performance:
        - Increases batch size if improving steadily
        - Increases hard case ratio if stuck
        - Decreases both if overfitting
        """
        eval_metric = metric or self.metric
        if eval_metric is None:
            raise ValueError("No metric provided")

        # Start with base config
        config = SIMBAConfig(
            num_iterations=self.base_config.num_iterations,
            batch_size=self.base_config.batch_size,
            hard_case_ratio=self.base_config.hard_case_ratio,
            max_demos=self.base_config.max_demos,
            min_iteration_improvement=self.base_config.min_iteration_improvement,
            patience=self.base_config.patience,
            temperature=self.base_config.temperature,
            verbose=self.base_config.verbose,
            seed=self.base_config.seed,
        )

        # Track performance
        train_scores = []
        val_scores = []
        best_module = module
        best_val_score = 0.0

        for iteration in range(config.num_iterations):
            # Run one SIMBA iteration
            inner_config = SIMBAConfig(
                num_iterations=1,
                batch_size=config.batch_size,
                hard_case_ratio=config.hard_case_ratio,
                max_demos=config.max_demos,
                verbose=False,
            )

            optimizer = SIMBAOptimizer(config=inner_config, metric=eval_metric)
            improved_module, _ = optimizer.optimize(
                best_module, trainset, None, eval_metric
            )

            # Evaluate on train and val
            train_score = self._evaluate(improved_module, trainset, eval_metric)
            val_score = self._evaluate(improved_module, valset or trainset, eval_metric)

            train_scores.append(train_score)
            val_scores.append(val_score)

            if config.verbose:
                print(
                    f"Adaptive Iteration {iteration + 1}: "
                    f"train={train_score:.4f}, val={val_score:.4f}"
                )

            # Update best
            if val_score > best_val_score:
                best_module = improved_module
                best_val_score = val_score

            # Adapt parameters
            config = self._adapt_config(config, train_scores, val_scores)

        # Create final result
        result = SIMBAResult(
            module_name=module.__class__.__name__,
            iteration_scores=val_scores,
            baseline_score=val_scores[0] if val_scores else 0.0,
            final_score=best_val_score,
            improvement=best_val_score - (val_scores[0] if val_scores else 0.0),
            training_examples=len(trainset),
            success=True,
        )

        return best_module, result

    def _evaluate(
        self,
        module: dspy.Module,
        examples: list[dspy.Example],
        metric: Callable,
    ) -> float:
        """Evaluate module."""
        if not examples:
            return 0.0

        scores = []
        for example in examples:
            try:
                inputs = {k: v for k, v in example.items() if k in example.inputs()}
                prediction = module(**inputs)
                score = metric(example, prediction)
                scores.append(score)
            except Exception:
                scores.append(0.0)

        return sum(scores) / len(scores) if scores else 0.0

    def _adapt_config(
        self,
        config: SIMBAConfig,
        train_scores: list[float],
        val_scores: list[float],
    ) -> SIMBAConfig:
        """Adapt configuration based on performance."""
        if len(train_scores) < 2:
            return config

        # Check trends
        train_improving = train_scores[-1] > train_scores[-2]
        val_improving = val_scores[-1] > val_scores[-2]
        overfitting = train_improving and not val_improving

        # Create new config
        new_config = SIMBAConfig(
            num_iterations=config.num_iterations,
            batch_size=config.batch_size,
            hard_case_ratio=config.hard_case_ratio,
            max_demos=config.max_demos,
            min_iteration_improvement=config.min_iteration_improvement,
            patience=config.patience,
            temperature=config.temperature,
            verbose=config.verbose,
            seed=config.seed,
        )

        if overfitting:
            # Reduce batch size to reduce overfitting
            new_config.batch_size = max(8, config.batch_size - 4)
            new_config.hard_case_ratio = min(0.8, config.hard_case_ratio + 0.1)
        elif train_improving and val_improving:
            # Increase batch size for faster convergence
            new_config.batch_size = min(64, config.batch_size + 4)
        elif not train_improving and not val_improving:
            # Focus more on hard cases
            new_config.hard_case_ratio = min(0.8, config.hard_case_ratio + 0.1)

        return new_config
