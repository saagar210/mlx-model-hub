"""
DSPy Evaluation Metrics.

Provides metrics for evaluating agent task outputs.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any, Callable

import dspy


# ============================================================================
# Metric Results
# ============================================================================


@dataclass
class MetricResult:
    """Result of evaluating a metric."""

    score: float  # 0-1
    passed: bool
    details: dict[str, Any]
    feedback: str | None = None


# ============================================================================
# Task Decomposition Metrics
# ============================================================================


def decomposition_quality(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: Any = None,
) -> float:
    """
    Evaluate the quality of task decomposition.

    Checks:
    - Subtasks are non-empty
    - Subtasks cover the original task
    - Dependencies are valid
    - Complexity estimate is reasonable
    """
    score = 0.0
    max_score = 4.0

    # Check subtasks exist and are non-empty
    subtasks = getattr(prediction, "subtasks", [])
    if subtasks and len(subtasks) > 0:
        score += 1.0

        # Check subtasks have reasonable length
        avg_len = sum(len(s) for s in subtasks) / len(subtasks)
        if avg_len >= 10:  # At least 10 chars per subtask
            score += 0.5

    # Check dependencies are valid indices
    dependencies = getattr(prediction, "dependencies", [])
    if dependencies is not None:
        valid_deps = True
        for dep in dependencies:
            if isinstance(dep, (list, tuple)) and len(dep) == 2:
                if dep[0] >= len(subtasks) or dep[1] >= len(subtasks):
                    valid_deps = False
                    break
            else:
                valid_deps = False
                break
        if valid_deps or len(dependencies) == 0:
            score += 1.0

    # Check complexity estimate
    complexity = getattr(prediction, "estimated_complexity", "")
    if complexity and complexity.lower() in ["low", "medium", "high"]:
        score += 1.0

    # Bonus: check subtasks mention key terms from original task
    task = getattr(example, "task", "")
    if task and subtasks:
        task_words = set(task.lower().split())
        subtask_words = set(" ".join(subtasks).lower().split())
        overlap = len(task_words & subtask_words)
        if overlap >= 2:
            score += 0.5

    return min(score / max_score, 1.0)


# ============================================================================
# Code Generation Metrics
# ============================================================================


def code_correctness(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: Any = None,
) -> float:
    """
    Evaluate code generation quality.

    Checks:
    - Code is valid Python syntax
    - Code includes function definitions
    - Code has docstrings
    - Code has type hints
    """
    score = 0.0
    max_score = 4.0

    code = getattr(prediction, "code", "")
    if not code:
        return 0.0

    # Check valid syntax
    try:
        tree = ast.parse(code)
        score += 1.0
    except SyntaxError:
        return 0.0  # Invalid syntax is automatic fail

    # Check for function definitions
    has_functions = any(isinstance(node, ast.FunctionDef) for node in ast.walk(tree))
    if has_functions:
        score += 1.0

    # Check for docstrings
    has_docstring = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                has_docstring = True
                break
    if has_docstring:
        score += 1.0

    # Check for type hints
    has_type_hints = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.returns or any(arg.annotation for arg in node.args.args):
                has_type_hints = True
                break
    if has_type_hints:
        score += 1.0

    return score / max_score


def code_executes(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: Any = None,
) -> float:
    """
    Check if code can be compiled without errors.

    Note: Does NOT execute the code for safety reasons.
    """
    code = getattr(prediction, "code", "")
    if not code:
        return 0.0

    try:
        compile(code, "<string>", "exec")
        return 1.0
    except Exception:
        return 0.0


# ============================================================================
# Research Metrics
# ============================================================================


def research_relevance(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: Any = None,
) -> float:
    """
    Evaluate research query relevance.

    Checks:
    - Queries are generated
    - Queries relate to the topic
    - Key concepts are identified
    - Sources are suggested
    """
    score = 0.0
    max_score = 4.0

    topic = getattr(example, "topic", "")

    # Check queries exist
    queries = getattr(prediction, "queries", [])
    if queries and len(queries) > 0:
        score += 1.0

        # Check queries contain topic-related terms
        topic_words = set(topic.lower().split())
        query_text = " ".join(queries).lower()
        overlap = sum(1 for w in topic_words if w in query_text)
        if overlap > 0:
            score += 0.5

    # Check sources
    sources = getattr(prediction, "sources_to_check", [])
    if sources and len(sources) > 0:
        score += 1.0

    # Check key concepts
    concepts = getattr(prediction, "key_concepts", [])
    if concepts and len(concepts) > 0:
        score += 1.0

        # Bonus for concept relevance
        concept_text = " ".join(concepts).lower()
        topic_words = set(topic.lower().split())
        if any(w in concept_text for w in topic_words):
            score += 0.5

    return min(score / max_score, 1.0)


# ============================================================================
# Code Review Metrics
# ============================================================================


def review_thoroughness(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: Any = None,
) -> float:
    """
    Evaluate code review thoroughness.

    Checks:
    - Issues are identified
    - Suggestions are provided
    - Quality assessment is given
    - Security concerns are noted (if applicable)
    """
    score = 0.0
    max_score = 4.0

    # Check issues identified
    issues = getattr(prediction, "issues", [])
    if issues is not None:
        if len(issues) > 0:
            score += 1.0
        elif len(issues) == 0:
            # No issues could be valid for good code
            score += 0.5

    # Check suggestions
    suggestions = getattr(prediction, "suggestions", [])
    if suggestions and len(suggestions) > 0:
        score += 1.0

    # Check quality assessment
    quality = getattr(prediction, "overall_quality", "")
    if quality and quality.lower() in ["poor", "fair", "good", "excellent"]:
        score += 1.0

    # Check security concerns noted
    security = getattr(prediction, "security_concerns", [])
    if security is not None:  # Even empty list is fine if considered
        score += 1.0

    return score / max_score


# ============================================================================
# Synthesis Metrics
# ============================================================================


def synthesis_coherence(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: Any = None,
) -> float:
    """
    Evaluate content synthesis quality.

    Checks:
    - Synthesis is generated
    - Synthesis has reasonable length
    - Sources are tracked
    - Synthesis is coherent (sentence structure)
    """
    score = 0.0
    max_score = 4.0

    synthesis = getattr(prediction, "synthesis", "")
    if not synthesis:
        return 0.0

    # Has content
    score += 1.0

    # Reasonable length (at least 50 chars)
    if len(synthesis) >= 50:
        score += 1.0

    # Sources tracked
    sources_used = getattr(prediction, "sources_used", [])
    if sources_used and len(sources_used) > 0:
        score += 1.0

    # Check coherence (has sentences ending in periods)
    sentences = [s.strip() for s in synthesis.split(".") if s.strip()]
    if len(sentences) >= 2:
        score += 1.0

    return score / max_score


# ============================================================================
# Skill Extraction Metrics
# ============================================================================


def skill_extraction_quality(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: Any = None,
) -> float:
    """
    Evaluate skill extraction quality.

    Checks:
    - Skills are extracted
    - Skills have required fields (name, description, code)
    - Patterns are identified
    """
    score = 0.0
    max_score = 3.0

    skills = getattr(prediction, "skills", [])
    if skills and len(skills) > 0:
        score += 1.0

        # Check skill structure
        valid_skills = 0
        for skill in skills:
            if isinstance(skill, dict):
                if all(k in skill for k in ["name", "description"]):
                    valid_skills += 1
        if valid_skills == len(skills):
            score += 1.0

    # Check patterns
    patterns = getattr(prediction, "patterns", [])
    if patterns and len(patterns) > 0:
        score += 1.0

    return score / max_score


# ============================================================================
# Decision Making Metrics
# ============================================================================


def decision_quality(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: Any = None,
) -> float:
    """
    Evaluate decision making quality.

    Checks:
    - Decision is made
    - Decision is from provided options
    - Reasoning is provided
    - Confidence is reasonable
    """
    score = 0.0
    max_score = 4.0

    options = getattr(example, "options", [])
    decision = getattr(prediction, "decision", "")

    # Decision made
    if decision:
        score += 1.0

        # Decision is from options
        if options and decision in options:
            score += 1.0

    # Reasoning provided
    reasoning = getattr(prediction, "reasoning", "")
    if reasoning and len(reasoning) >= 20:
        score += 1.0

    # Confidence is reasonable (0-1)
    confidence = getattr(prediction, "confidence", None)
    if confidence is not None:
        try:
            conf_val = float(confidence)
            if 0 <= conf_val <= 1:
                score += 1.0
        except (TypeError, ValueError):
            pass

    return score / max_score


# ============================================================================
# Error Analysis Metrics
# ============================================================================


def error_analysis_quality(
    example: dspy.Example,
    prediction: dspy.Prediction,
    trace: Any = None,
) -> float:
    """
    Evaluate error analysis quality.

    Checks:
    - Root cause is identified
    - Fixes are suggested
    - Prevention is recommended
    """
    score = 0.0
    max_score = 3.0

    # Root cause
    root_cause = getattr(prediction, "root_cause", "")
    if root_cause and len(root_cause) >= 10:
        score += 1.0

    # Fixes suggested
    fixes = getattr(prediction, "fixes", [])
    if fixes and len(fixes) > 0:
        score += 1.0

    # Prevention
    prevention = getattr(prediction, "prevention", "")
    if prevention and len(prevention) >= 10:
        score += 1.0

    return score / max_score


# ============================================================================
# Composite Metrics
# ============================================================================


def composite_metric(
    metrics: list[tuple[Callable, float]],
) -> Callable:
    """
    Create a composite metric from multiple metrics with weights.

    Args:
        metrics: List of (metric_function, weight) tuples

    Returns:
        A metric function that combines all metrics
    """

    def combined_metric(
        example: dspy.Example,
        prediction: dspy.Prediction,
        trace: Any = None,
    ) -> float:
        total_score = 0.0
        total_weight = 0.0

        for metric_fn, weight in metrics:
            try:
                score = metric_fn(example, prediction, trace)
                total_score += score * weight
                total_weight += weight
            except Exception:
                # Skip failed metrics
                continue

        if total_weight == 0:
            return 0.0

        return total_score / total_weight

    return combined_metric


# ============================================================================
# LLM-as-Judge Metric
# ============================================================================


class LLMJudge:
    """
    Use an LLM to evaluate outputs.

    Provides more nuanced evaluation than rule-based metrics.
    """

    JUDGE_PROMPT = """Evaluate the following AI output for quality.

Task: {task}

Output to evaluate:
{output}

Rate the output on a scale of 0-10 based on:
1. Accuracy and correctness
2. Completeness
3. Clarity and coherence
4. Usefulness

Respond with ONLY a JSON object:
{{"score": <0-10>, "reasoning": "<brief explanation>"}}
"""

    def __init__(self, lm: dspy.LM | None = None):
        """Initialize with optional language model."""
        self.lm = lm or dspy.settings.lm

    def evaluate(
        self,
        task: str,
        output: str,
    ) -> MetricResult:
        """
        Evaluate output using LLM.

        Args:
            task: The original task
            output: The output to evaluate

        Returns:
            MetricResult with score and details
        """
        import json

        prompt = self.JUDGE_PROMPT.format(task=task, output=output)

        try:
            response = self.lm(prompt)
            text = response[0] if isinstance(response, list) else str(response)

            # Extract JSON from response
            json_match = re.search(r"\{[^}]+\}", text)
            if json_match:
                result = json.loads(json_match.group())
                score = float(result.get("score", 0)) / 10.0
                return MetricResult(
                    score=score,
                    passed=score >= 0.6,
                    details=result,
                    feedback=result.get("reasoning"),
                )
        except Exception as e:
            return MetricResult(
                score=0.0,
                passed=False,
                details={"error": str(e)},
                feedback="Failed to evaluate with LLM",
            )

        return MetricResult(
            score=0.0,
            passed=False,
            details={},
            feedback="Could not parse LLM response",
        )


# ============================================================================
# Metric Registry
# ============================================================================

METRIC_REGISTRY = {
    "decomposition_quality": decomposition_quality,
    "code_correctness": code_correctness,
    "code_executes": code_executes,
    "research_relevance": research_relevance,
    "review_thoroughness": review_thoroughness,
    "synthesis_coherence": synthesis_coherence,
    "skill_extraction_quality": skill_extraction_quality,
    "decision_quality": decision_quality,
    "error_analysis_quality": error_analysis_quality,
}


def get_metric(name: str) -> Callable:
    """Get a metric function by name."""
    if name not in METRIC_REGISTRY:
        raise ValueError(f"Unknown metric: {name}. Available: {list(METRIC_REGISTRY.keys())}")
    return METRIC_REGISTRY[name]


def list_metrics() -> list[str]:
    """List all available metrics."""
    return list(METRIC_REGISTRY.keys())
