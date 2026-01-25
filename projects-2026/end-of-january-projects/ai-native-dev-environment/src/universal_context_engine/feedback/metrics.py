"""Quality metrics calculation."""

from dataclasses import dataclass
from typing import Any

from .tracker import feedback_tracker


@dataclass
class QualityMetrics:
    """Quality metrics for the system."""

    total_interactions: int = 0
    helpful_count: int = 0
    not_helpful_count: int = 0
    feedback_rate: float = 0.0
    helpful_rate: float = 0.0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    by_tool: dict[str, dict[str, Any]] | None = None


def get_metrics() -> QualityMetrics:
    """Calculate quality metrics from feedback data.

    Returns:
        QualityMetrics with calculated values.
    """
    stats = feedback_tracker.get_stats()

    if "error" in stats:
        return QualityMetrics()

    # Get detailed per-tool metrics
    all_interactions = feedback_tracker.get_interactions(limit=1000)
    tool_metrics: dict[str, dict[str, Any]] = {}

    for interaction in all_interactions:
        tool = interaction.get("tool", "unknown")
        if tool not in tool_metrics:
            tool_metrics[tool] = {
                "total": 0,
                "helpful": 0,
                "not_helpful": 0,
                "errors": 0,
                "total_latency": 0,
            }

        tool_metrics[tool]["total"] += 1
        if interaction.get("feedback") == "helpful":
            tool_metrics[tool]["helpful"] += 1
        elif interaction.get("feedback") == "not_helpful":
            tool_metrics[tool]["not_helpful"] += 1
        if interaction.get("has_error"):
            tool_metrics[tool]["errors"] += 1
        tool_metrics[tool]["total_latency"] += interaction.get("latency_ms", 0)

    # Calculate rates for each tool
    for tool, data in tool_metrics.items():
        total = data["total"]
        data["success_rate"] = (total - data["errors"]) / total if total > 0 else 0
        data["avg_latency_ms"] = data["total_latency"] / total if total > 0 else 0
        feedback_total = data["helpful"] + data["not_helpful"]
        data["feedback_rate"] = feedback_total / total if total > 0 else 0
        data["helpful_rate"] = data["helpful"] / feedback_total if feedback_total > 0 else 0
        del data["total_latency"]  # Remove intermediate value

    # Calculate error rate
    error_count = sum(1 for i in all_interactions if i.get("has_error"))
    total = stats.get("total_interactions", 0)
    error_rate = error_count / total if total > 0 else 0

    return QualityMetrics(
        total_interactions=stats.get("total_interactions", 0),
        helpful_count=stats.get("helpful", 0),
        not_helpful_count=stats.get("not_helpful", 0),
        feedback_rate=stats.get("feedback_rate", 0),
        helpful_rate=stats.get("helpful_rate", 0),
        avg_latency_ms=stats.get("avg_latency_ms", 0),
        error_rate=error_rate,
        by_tool=tool_metrics,
    )
