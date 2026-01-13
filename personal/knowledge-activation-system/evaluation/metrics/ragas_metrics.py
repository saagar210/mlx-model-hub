"""
RAGAS-Style Evaluation Metrics

Implements evaluation metrics inspired by RAGAS (Retrieval Augmented Generation Assessment):
- Context Precision: Are retrieved chunks relevant to the query?
- Context Recall: Did we retrieve the necessary information?
- Answer Relevancy: Does the answer address the query?
- Faithfulness: Is the answer grounded in the retrieved context?

These implementations use heuristic methods by default but can optionally
use an LLM for more accurate evaluation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class RAGEvalInput:
    """Input data for RAG evaluation."""

    query: str
    retrieved_contexts: list[str]
    generated_answer: str | None = None
    expected_keywords: list[str] | None = None
    ground_truth: str | None = None


@dataclass
class RAGEvalResult:
    """Evaluation result with individual metric scores."""

    context_precision: float
    context_recall: float
    answer_relevancy: float
    faithfulness: float
    aggregate_score: float

    @classmethod
    def from_scores(
        cls,
        context_precision: float,
        context_recall: float,
        answer_relevancy: float,
        faithfulness: float,
        weights: dict[str, float] | None = None,
    ) -> "RAGEvalResult":
        """Create result with calculated aggregate score."""
        if weights is None:
            weights = {
                "context_precision": 0.25,
                "context_recall": 0.25,
                "answer_relevancy": 0.25,
                "faithfulness": 0.25,
            }

        aggregate = (
            context_precision * weights.get("context_precision", 0.25)
            + context_recall * weights.get("context_recall", 0.25)
            + answer_relevancy * weights.get("answer_relevancy", 0.25)
            + faithfulness * weights.get("faithfulness", 0.25)
        )

        return cls(
            context_precision=context_precision,
            context_recall=context_recall,
            answer_relevancy=answer_relevancy,
            faithfulness=faithfulness,
            aggregate_score=aggregate,
        )


# =============================================================================
# Context Precision
# =============================================================================


def context_precision(
    query: str,
    contexts: list[str],
    expected_keywords: list[str] | None = None,
) -> float:
    """
    Calculate context precision - how relevant are retrieved chunks to the query?

    Uses keyword overlap between query/expected keywords and context.
    Higher precision means retrieved chunks are more query-relevant.

    Args:
        query: The search query
        contexts: List of retrieved context strings
        expected_keywords: Optional list of expected keywords

    Returns:
        Precision score (0-1)
    """
    if not contexts:
        return 0.0

    # Extract query terms
    query_terms = set(re.findall(r"\b\w{3,}\b", query.lower()))

    # Add expected keywords if provided
    if expected_keywords:
        query_terms.update(kw.lower() for kw in expected_keywords)

    if not query_terms:
        return 0.5  # No terms to match

    # Calculate precision per context, then average
    precisions = []
    for context in contexts:
        context_lower = context.lower()
        matched = sum(1 for term in query_terms if term in context_lower)
        precisions.append(matched / len(query_terms))

    return sum(precisions) / len(precisions)


def context_precision_weighted(
    query: str,
    contexts: list[str],
    scores: list[float],
    expected_keywords: list[str] | None = None,
) -> float:
    """
    Calculate weighted context precision using retrieval scores.

    Weights each context's precision by its retrieval score.

    Args:
        query: The search query
        contexts: List of retrieved context strings
        scores: Retrieval scores for each context
        expected_keywords: Optional list of expected keywords

    Returns:
        Weighted precision score (0-1)
    """
    if not contexts or not scores:
        return 0.0

    query_terms = set(re.findall(r"\b\w{3,}\b", query.lower()))
    if expected_keywords:
        query_terms.update(kw.lower() for kw in expected_keywords)

    if not query_terms:
        return 0.5

    weighted_sum = 0.0
    total_weight = sum(scores)

    if total_weight == 0:
        return context_precision(query, contexts, expected_keywords)

    for context, score in zip(contexts, scores):
        context_lower = context.lower()
        matched = sum(1 for term in query_terms if term in context_lower)
        precision = matched / len(query_terms)
        weighted_sum += precision * score

    return weighted_sum / total_weight


# =============================================================================
# Context Recall
# =============================================================================


def context_recall(
    contexts: list[str],
    expected_keywords: list[str],
    ground_truth: str | None = None,
) -> float:
    """
    Calculate context recall - did we retrieve all necessary information?

    Measures how many expected keywords appear in retrieved contexts.

    Args:
        contexts: List of retrieved context strings
        expected_keywords: List of keywords that should appear
        ground_truth: Optional ground truth text to compare against

    Returns:
        Recall score (0-1)
    """
    if not expected_keywords:
        return 1.0 if contexts else 0.0

    if not contexts:
        return 0.0

    # Combine all contexts
    all_context = " ".join(contexts).lower()

    # Count found keywords
    found = sum(1 for kw in expected_keywords if kw.lower() in all_context)

    base_recall = found / len(expected_keywords)

    # If ground truth provided, also check against it
    if ground_truth:
        ground_truth_lower = ground_truth.lower()
        # Extract key phrases from ground truth
        gt_phrases = set(re.findall(r"\b\w{4,}\b", ground_truth_lower))

        if gt_phrases:
            gt_found = sum(1 for phrase in gt_phrases if phrase in all_context)
            gt_recall = gt_found / len(gt_phrases)
            # Average of keyword recall and ground truth recall
            return (base_recall + gt_recall) / 2

    return base_recall


# =============================================================================
# Answer Relevancy
# =============================================================================


def answer_relevancy(
    query: str,
    answer: str | None,
    expected_keywords: list[str] | None = None,
) -> float:
    """
    Calculate answer relevancy - does the answer address the query?

    Uses semantic similarity approximation via keyword overlap.

    Args:
        query: The original query
        answer: The generated answer
        expected_keywords: Optional expected keywords in good answers

    Returns:
        Relevancy score (0-1)
    """
    if not answer:
        return 0.0

    answer_lower = answer.lower()

    # Extract query terms
    query_terms = set(re.findall(r"\b\w{3,}\b", query.lower()))

    if expected_keywords:
        query_terms.update(kw.lower() for kw in expected_keywords)

    if not query_terms:
        return 0.5

    # Check query term presence in answer
    found = sum(1 for term in query_terms if term in answer_lower)
    term_coverage = found / len(query_terms)

    # Check answer length (too short = likely incomplete)
    word_count = len(answer.split())
    length_score = min(1.0, word_count / 20)  # Expect at least 20 words

    # Check for confidence indicators (hedging = lower score)
    hedging_phrases = [
        "i don't know",
        "i'm not sure",
        "unclear",
        "cannot determine",
        "no information",
    ]
    has_hedging = any(phrase in answer_lower for phrase in hedging_phrases)
    confidence_score = 0.5 if has_hedging else 1.0

    # Weighted combination
    return (term_coverage * 0.5) + (length_score * 0.3) + (confidence_score * 0.2)


# =============================================================================
# Faithfulness
# =============================================================================


def faithfulness_score(
    answer: str | None,
    contexts: list[str],
) -> float:
    """
    Calculate faithfulness - is the answer grounded in retrieved context?

    Measures how much of the answer's key content appears in the context.
    Penalizes answers that include information not found in context.

    Args:
        answer: The generated answer
        contexts: List of retrieved context strings

    Returns:
        Faithfulness score (0-1)
    """
    if not answer:
        return 0.0

    if not contexts:
        return 0.0  # No context = can't be faithful

    # Extract answer's key content words
    answer_terms = set(re.findall(r"\b\w{4,}\b", answer.lower()))

    if not answer_terms:
        return 0.5

    # Combine all contexts
    all_context = " ".join(contexts).lower()

    # Count terms that appear in context
    grounded_terms = sum(1 for term in answer_terms if term in all_context)

    # Calculate grounding ratio
    grounding_ratio = grounded_terms / len(answer_terms)

    # Also check for factual-looking statements not in context
    # (numbers, names, dates that appear in answer but not context)
    numbers_in_answer = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", answer.lower()))
    numbers_in_context = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", all_context))

    # Penalize ungrounded numbers
    if numbers_in_answer:
        ungrounded_numbers = numbers_in_answer - numbers_in_context
        number_penalty = len(ungrounded_numbers) / len(numbers_in_answer)
        grounding_ratio = grounding_ratio * (1 - number_penalty * 0.3)

    return min(1.0, grounding_ratio)


# =============================================================================
# Combined Evaluation
# =============================================================================


def evaluate_rag(
    input_data: RAGEvalInput,
    weights: dict[str, float] | None = None,
) -> RAGEvalResult:
    """
    Run full RAG evaluation on a query-answer pair.

    Args:
        input_data: RAGEvalInput with query, contexts, answer, etc.
        weights: Optional weights for aggregate score

    Returns:
        RAGEvalResult with all metric scores
    """
    cp = context_precision(
        input_data.query,
        input_data.retrieved_contexts,
        input_data.expected_keywords,
    )

    cr = context_recall(
        input_data.retrieved_contexts,
        input_data.expected_keywords or [],
        input_data.ground_truth,
    )

    ar = answer_relevancy(
        input_data.query,
        input_data.generated_answer,
        input_data.expected_keywords,
    )

    fs = faithfulness_score(
        input_data.generated_answer,
        input_data.retrieved_contexts,
    )

    return RAGEvalResult.from_scores(cp, cr, ar, fs, weights)


def evaluate_retrieval_only(
    query: str,
    contexts: list[str],
    expected_keywords: list[str] | None = None,
    scores: list[float] | None = None,
) -> dict[str, float]:
    """
    Evaluate retrieval quality only (no answer generation).

    Useful for evaluating search without the Q&A component.

    Args:
        query: Search query
        contexts: Retrieved contexts
        expected_keywords: Expected keywords
        scores: Retrieval scores

    Returns:
        Dict with context_precision and context_recall
    """
    cp = context_precision_weighted(
        query, contexts, scores or [], expected_keywords
    ) if scores else context_precision(query, contexts, expected_keywords)

    cr = context_recall(contexts, expected_keywords or [])

    return {
        "context_precision": cp,
        "context_recall": cr,
        "average": (cp + cr) / 2,
    }
