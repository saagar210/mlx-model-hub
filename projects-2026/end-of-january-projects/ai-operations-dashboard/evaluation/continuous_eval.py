#!/usr/bin/env python3
"""
Continuous evaluation pipeline for Langfuse traces using DeepEval.

Runs every 15 minutes via cron to evaluate recent RAG traces for:
- Faithfulness: Is the answer grounded in the retrieved context?
- Relevancy: Does the answer address the question?
- Hallucination: Does the answer contain unsupported claims?

Uses local Qwen 2.5:14b via Ollama for zero-cost evaluation.

Usage:
    python evaluation/continuous_eval.py

    # Or via cron (every 15 minutes):
    */15 * * * * /path/to/evaluation/cron_eval.sh
"""

from __future__ import annotations

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

# Configure DeepEval to use local Ollama
os.environ["DEEPEVAL_MODEL"] = "ollama/qwen2.5:14b"
os.environ["OLLAMA_HOST"] = os.getenv("OLLAMA_HOST", "http://localhost:11434")

from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    HallucinationMetric,
)
from deepeval.test_case import LLMTestCase
from langfuse import Langfuse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def get_langfuse_client() -> Optional[Langfuse]:
    """Initialize Langfuse client from environment variables."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3002")

    if not public_key or not secret_key:
        logger.error("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY required")
        return None

    try:
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    except Exception as e:
        logger.error(f"Failed to connect to Langfuse: {e}")
        return None


def has_score(trace, score_name: str) -> bool:
    """Check if a trace already has a specific score."""
    if not hasattr(trace, "scores") or not trace.scores:
        return False
    return any(s.name == score_name for s in trace.scores)


def extract_trace_data(trace) -> dict:
    """
    Extract question, answer, and context from a trace.

    Supports various trace structures:
    - input as dict with "question" key
    - input as string (treated as question)
    - metadata containing "context_docs"
    - observations containing retrieval results
    """
    data = {
        "question": "",
        "answer": "",
        "context": [],
    }

    # Extract question
    if isinstance(trace.input, dict):
        data["question"] = trace.input.get("question", str(trace.input))
    elif isinstance(trace.input, str):
        data["question"] = trace.input
    else:
        data["question"] = str(trace.input) if trace.input else ""

    # Extract answer
    if isinstance(trace.output, dict):
        data["answer"] = trace.output.get("answer", str(trace.output))
    elif isinstance(trace.output, str):
        data["answer"] = trace.output
    else:
        data["answer"] = str(trace.output) if trace.output else ""

    # Extract context from metadata
    if hasattr(trace, "metadata") and trace.metadata:
        context_docs = trace.metadata.get("context_docs", [])
        if isinstance(context_docs, list):
            data["context"] = context_docs
        elif isinstance(context_docs, str):
            data["context"] = [context_docs]

    return data


def evaluate_trace(
    trace,
    faithfulness_metric: FaithfulnessMetric,
    relevancy_metric: AnswerRelevancyMetric,
    hallucination_metric: HallucinationMetric,
    langfuse: Langfuse,
) -> dict:
    """
    Evaluate a single trace with DeepEval metrics.

    Returns:
        Dict with metric scores or error information
    """
    trace_data = extract_trace_data(trace)

    if not trace_data["question"] or not trace_data["answer"]:
        return {"status": "skipped", "reason": "missing question or answer"}

    # Create DeepEval test case
    test_case = LLMTestCase(
        input=trace_data["question"],
        actual_output=trace_data["answer"],
        retrieval_context=trace_data["context"] if trace_data["context"] else None,
    )

    results = {"status": "evaluated", "scores": {}}

    try:
        # Faithfulness (requires retrieval context)
        if trace_data["context"]:
            faithfulness_metric.measure(test_case)
            results["scores"]["faithfulness"] = faithfulness_metric.score
            langfuse.score(
                trace_id=trace.id,
                name="faithfulness",
                value=faithfulness_metric.score,
                comment=faithfulness_metric.reason[:500] if faithfulness_metric.reason else None,
            )
            logger.debug(f"Faithfulness: {faithfulness_metric.score:.2f}")
    except Exception as e:
        logger.warning(f"Faithfulness eval failed: {e}")

    try:
        # Answer Relevancy
        relevancy_metric.measure(test_case)
        results["scores"]["relevancy"] = relevancy_metric.score
        langfuse.score(
            trace_id=trace.id,
            name="relevancy",
            value=relevancy_metric.score,
            comment=relevancy_metric.reason[:500] if relevancy_metric.reason else None,
        )
        logger.debug(f"Relevancy: {relevancy_metric.score:.2f}")
    except Exception as e:
        logger.warning(f"Relevancy eval failed: {e}")

    try:
        # Hallucination (requires retrieval context)
        if trace_data["context"]:
            hallucination_metric.measure(test_case)
            results["scores"]["hallucination"] = hallucination_metric.score
            langfuse.score(
                trace_id=trace.id,
                name="hallucination",
                value=hallucination_metric.score,
                comment=hallucination_metric.reason[:500] if hallucination_metric.reason else None,
            )
            logger.debug(f"Hallucination: {hallucination_metric.score:.2f}")
    except Exception as e:
        logger.warning(f"Hallucination eval failed: {e}")

    return results


async def evaluate_recent_traces(
    minutes: int = 15,
    limit: int = 50,
    trace_filter: Optional[dict] = None,
) -> dict:
    """
    Evaluate traces from the last N minutes.

    Args:
        minutes: How far back to look for traces
        limit: Maximum number of traces to evaluate
        trace_filter: Additional filter criteria for traces

    Returns:
        Summary of evaluation results
    """
    langfuse = get_langfuse_client()
    if not langfuse:
        return {"status": "error", "message": "Failed to connect to Langfuse"}

    # Initialize metrics with local Qwen
    faithfulness = FaithfulnessMetric(
        threshold=0.7,
        model="ollama/qwen2.5:14b",
    )
    relevancy = AnswerRelevancyMetric(
        threshold=0.7,
        model="ollama/qwen2.5:14b",
    )
    hallucination = HallucinationMetric(
        threshold=0.3,  # Lower is better for hallucination
        model="ollama/qwen2.5:14b",
    )

    # Fetch recent traces
    from_timestamp = datetime.utcnow() - timedelta(minutes=minutes)

    try:
        # Build filter
        filter_params = trace_filter or {}

        traces = langfuse.get_traces(
            limit=limit,
            from_timestamp=from_timestamp,
            **filter_params,
        )
    except Exception as e:
        logger.error(f"Failed to fetch traces: {e}")
        return {"status": "error", "message": str(e)}

    logger.info(f"Found {len(traces.data) if hasattr(traces, 'data') else 0} traces to evaluate")

    summary = {
        "status": "completed",
        "total_traces": 0,
        "evaluated": 0,
        "skipped": 0,
        "already_scored": 0,
        "avg_scores": {},
    }

    trace_list = traces.data if hasattr(traces, "data") else traces
    summary["total_traces"] = len(trace_list)

    score_totals = {"faithfulness": [], "relevancy": [], "hallucination": []}

    for trace in trace_list:
        # Skip if already evaluated
        if has_score(trace, "relevancy"):
            summary["already_scored"] += 1
            continue

        logger.info(f"Evaluating trace: {trace.id}")

        result = evaluate_trace(
            trace,
            faithfulness,
            relevancy,
            hallucination,
            langfuse,
        )

        if result["status"] == "evaluated":
            summary["evaluated"] += 1
            for metric, score in result.get("scores", {}).items():
                if score is not None:
                    score_totals[metric].append(score)
        else:
            summary["skipped"] += 1

    # Calculate averages
    for metric, scores in score_totals.items():
        if scores:
            summary["avg_scores"][metric] = sum(scores) / len(scores)

    # Flush scores to Langfuse
    langfuse.flush()

    logger.info(f"Evaluation complete: {summary}")
    return summary


def main():
    """Main entry point for continuous evaluation."""
    import asyncio

    logger.info("Starting continuous evaluation pipeline")
    logger.info(f"Langfuse host: {os.getenv('LANGFUSE_HOST', 'http://localhost:3002')}")
    logger.info(f"Ollama host: {os.getenv('OLLAMA_HOST', 'http://localhost:11434')}")

    # Run evaluation
    summary = asyncio.run(evaluate_recent_traces(
        minutes=15,
        limit=50,
        trace_filter={"name": "rag_query"},  # Filter for RAG traces
    ))

    # Output summary
    print(json.dumps(summary, indent=2, default=str))

    # Exit with error if evaluation failed
    if summary.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
