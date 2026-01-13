"""
Information Retrieval Evaluation Metrics

Standard metrics for evaluating search/retrieval quality:
- MRR (Mean Reciprocal Rank)
- NDCG (Normalized Discounted Cumulative Gain)
- Precision@K
- Recall@K
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass
class RetrievalResult:
    """A single retrieval result with relevance information."""

    doc_id: str
    score: float
    is_relevant: bool
    relevance_grade: int = 1  # For graded relevance (0=irrelevant, 1=relevant, 2=highly relevant)


def reciprocal_rank(results: Sequence[RetrievalResult]) -> float:
    """
    Calculate Reciprocal Rank (RR) for a single query.

    RR = 1 / rank_of_first_relevant_result

    Args:
        results: Ordered list of retrieval results

    Returns:
        Reciprocal rank (0 if no relevant results found)
    """
    for i, result in enumerate(results, start=1):
        if result.is_relevant:
            return 1.0 / i
    return 0.0


def mrr(query_results: Sequence[Sequence[RetrievalResult]]) -> float:
    """
    Calculate Mean Reciprocal Rank (MRR) across multiple queries.

    MRR = (1/|Q|) * sum(1/rank_i) for all queries

    Args:
        query_results: List of result lists, one per query

    Returns:
        Mean reciprocal rank across all queries
    """
    if not query_results:
        return 0.0

    total_rr = sum(reciprocal_rank(results) for results in query_results)
    return total_rr / len(query_results)


def precision_at_k(results: Sequence[RetrievalResult], k: int) -> float:
    """
    Calculate Precision@K - proportion of relevant docs in top K results.

    P@K = |relevant docs in top K| / K

    Args:
        results: Ordered list of retrieval results
        k: Number of top results to consider

    Returns:
        Precision at K
    """
    if k <= 0:
        return 0.0

    top_k = list(results)[:k]
    if not top_k:
        return 0.0

    relevant_count = sum(1 for r in top_k if r.is_relevant)
    return relevant_count / k


def recall_at_k(
    results: Sequence[RetrievalResult],
    k: int,
    total_relevant: int | None = None,
) -> float:
    """
    Calculate Recall@K - proportion of relevant docs found in top K.

    R@K = |relevant docs in top K| / |total relevant docs|

    Args:
        results: Ordered list of retrieval results
        k: Number of top results to consider
        total_relevant: Total number of relevant docs (if known)
                       If None, counts relevant in full results list

    Returns:
        Recall at K
    """
    if k <= 0:
        return 0.0

    top_k = list(results)[:k]

    # Count relevant in top K
    relevant_in_top_k = sum(1 for r in top_k if r.is_relevant)

    # Determine total relevant
    if total_relevant is None:
        total_relevant = sum(1 for r in results if r.is_relevant)

    if total_relevant == 0:
        return 0.0

    return relevant_in_top_k / total_relevant


def dcg(results: Sequence[RetrievalResult], k: int | None = None) -> float:
    """
    Calculate Discounted Cumulative Gain.

    DCG = sum((2^rel_i - 1) / log2(i + 1)) for i in 1..k

    Uses the log base 2 formulation common in industry.

    Args:
        results: Ordered list of retrieval results with relevance grades
        k: Number of results to consider (None = all)

    Returns:
        DCG score
    """
    if k is not None:
        results = list(results)[:k]

    dcg_score = 0.0
    for i, result in enumerate(results, start=1):
        # Use 2^rel - 1 formulation (standard for graded relevance)
        gain = (2 ** result.relevance_grade) - 1
        discount = math.log2(i + 1)
        dcg_score += gain / discount

    return dcg_score


def ideal_dcg(results: Sequence[RetrievalResult], k: int | None = None) -> float:
    """
    Calculate Ideal DCG (best possible DCG for these results).

    IDCG is calculated by sorting results by relevance grade descending.

    Args:
        results: List of retrieval results with relevance grades
        k: Number of results to consider (None = all)

    Returns:
        Ideal DCG score
    """
    # Sort by relevance grade descending
    sorted_results = sorted(results, key=lambda r: r.relevance_grade, reverse=True)
    return dcg(sorted_results, k)


def ndcg(results: Sequence[RetrievalResult], k: int | None = None) -> float:
    """
    Calculate Normalized Discounted Cumulative Gain.

    NDCG = DCG / IDCG

    NDCG ranges from 0 to 1, where 1 means perfect ranking.

    Args:
        results: Ordered list of retrieval results with relevance grades
        k: Number of results to consider (None = all)

    Returns:
        NDCG score (0-1)
    """
    idcg_score = ideal_dcg(results, k)

    if idcg_score == 0:
        return 0.0

    dcg_score = dcg(results, k)
    return dcg_score / idcg_score


def average_precision(results: Sequence[RetrievalResult]) -> float:
    """
    Calculate Average Precision (AP) for a single query.

    AP = (1/|R|) * sum(P@k * rel_k) for all k

    Args:
        results: Ordered list of retrieval results

    Returns:
        Average precision score
    """
    relevant_count = sum(1 for r in results if r.is_relevant)
    if relevant_count == 0:
        return 0.0

    ap_sum = 0.0
    relevant_so_far = 0

    for i, result in enumerate(results, start=1):
        if result.is_relevant:
            relevant_so_far += 1
            precision = relevant_so_far / i
            ap_sum += precision

    return ap_sum / relevant_count


def mean_average_precision(query_results: Sequence[Sequence[RetrievalResult]]) -> float:
    """
    Calculate Mean Average Precision (MAP) across multiple queries.

    MAP = (1/|Q|) * sum(AP_q) for all queries q

    Args:
        query_results: List of result lists, one per query

    Returns:
        Mean average precision
    """
    if not query_results:
        return 0.0

    total_ap = sum(average_precision(results) for results in query_results)
    return total_ap / len(query_results)


# =============================================================================
# Helper functions for creating RetrievalResult from KAS search results
# =============================================================================


def create_retrieval_results(
    search_results: list[dict],
    relevance_fn: callable | None = None,
) -> list[RetrievalResult]:
    """
    Convert KAS search results to RetrievalResult objects.

    Args:
        search_results: List of search result dicts from KAS API
        relevance_fn: Optional function to determine relevance
                     Takes a result dict, returns (is_relevant, grade)

    Returns:
        List of RetrievalResult objects
    """
    results = []

    for result in search_results:
        if relevance_fn:
            is_relevant, grade = relevance_fn(result)
        else:
            # Default: use score threshold
            score = result.get("score", 0)
            is_relevant = score > 0.3
            grade = 2 if score > 0.7 else 1 if score > 0.3 else 0

        results.append(
            RetrievalResult(
                doc_id=result.get("content_id", ""),
                score=result.get("score", 0),
                is_relevant=is_relevant,
                relevance_grade=grade,
            )
        )

    return results


def relevance_from_keywords(
    expected_keywords: list[str],
    min_overlap: float = 0.3,
) -> callable:
    """
    Create a relevance function based on keyword matching.

    Args:
        expected_keywords: List of expected keywords
        min_overlap: Minimum keyword overlap for relevance

    Returns:
        Relevance function (result_dict) -> (is_relevant, grade)
    """

    def check_relevance(result: dict) -> tuple[bool, int]:
        if not expected_keywords:
            return False, 0

        content = (result.get("chunk_text") or "").lower()
        content += " " + (result.get("title") or "").lower()

        found = sum(1 for kw in expected_keywords if kw.lower() in content)
        overlap = found / len(expected_keywords)

        if overlap >= 0.7:
            return True, 2  # Highly relevant
        elif overlap >= min_overlap:
            return True, 1  # Relevant
        else:
            return False, 0  # Not relevant

    return check_relevance
