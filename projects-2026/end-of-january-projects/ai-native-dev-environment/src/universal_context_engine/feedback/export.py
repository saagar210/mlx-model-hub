"""Export training data for DSPy optimization."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import settings
from .tracker import feedback_tracker


def export_training_data(
    tool: str | None = None,
    min_examples: int = 50,
    output_path: str | None = None,
    only_helpful: bool = True,
) -> dict[str, Any]:
    """Export interaction data for DSPy training.

    Exports input/output pairs with positive feedback for fine-tuning
    or DSPy optimization.

    Args:
        tool: Filter by specific tool, or None for all tools.
        min_examples: Minimum number of examples required.
        output_path: Path to write the export file, or None to return data.
        only_helpful: If True, only export interactions marked as helpful.

    Returns:
        Dictionary with export info and optionally the data itself.
    """
    # Get interactions with feedback
    feedback_filter = "helpful" if only_helpful else None
    interactions = feedback_tracker.get_interactions(
        tool=tool,
        feedback_filter=feedback_filter,
        limit=1000,
    )

    if len(interactions) < min_examples:
        return {
            "success": False,
            "error": f"Not enough examples. Found {len(interactions)}, need {min_examples}.",
            "available": len(interactions),
            "required": min_examples,
        }

    # Format for DSPy
    training_examples = []
    for interaction in interactions:
        # Parse the content to extract tool and params
        content = interaction.get("content", "")
        parts = content.split(": ", 1)
        tool_name = parts[0] if parts else "unknown"
        params_str = parts[1] if len(parts) > 1 else ""

        example = {
            "id": interaction.get("id"),
            "tool": interaction.get("tool", tool_name),
            "input": params_str,
            "output": interaction.get("output_preview", ""),
            "feedback": interaction.get("feedback"),
            "timestamp": interaction.get("timestamp"),
        }
        training_examples.append(example)

    export_data = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "tool_filter": tool,
        "only_helpful": only_helpful,
        "example_count": len(training_examples),
        "examples": training_examples,
    }

    # Write to file if path provided
    if output_path:
        path = Path(output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(export_data, f, indent=2)

        return {
            "success": True,
            "path": str(path),
            "example_count": len(training_examples),
            "tool_filter": tool,
        }

    return {
        "success": True,
        "example_count": len(training_examples),
        "tool_filter": tool,
        "data": export_data,
    }


def export_for_dspy(
    tool: str,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Export data in DSPy-compatible format.

    Creates a JSONL file with input/output pairs suitable for
    DSPy fine-tuning.

    Args:
        tool: The tool to export data for.
        output_dir: Directory to write the file.

    Returns:
        Export result info.
    """
    output_dir = output_dir or str(settings.uce_data_dir / "exports")
    output_path = Path(output_dir) / f"{tool}_dspy_training.jsonl"

    interactions = feedback_tracker.get_interactions(
        tool=tool,
        feedback_filter="helpful",
        limit=500,
    )

    if not interactions:
        return {
            "success": False,
            "error": f"No helpful interactions found for tool: {tool}",
        }

    # Write JSONL format
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for interaction in interactions:
            content = interaction.get("content", "")
            parts = content.split(": ", 1)
            params_str = parts[1] if len(parts) > 1 else ""

            dspy_example = {
                "input": params_str,
                "output": interaction.get("output_preview", ""),
            }
            f.write(json.dumps(dspy_example) + "\n")

    return {
        "success": True,
        "path": str(output_path),
        "example_count": len(interactions),
        "format": "jsonl",
    }
