"""Search fusion algorithms for combining multiple search results.

Implements Reciprocal Rank Fusion (RRF) for hybrid search.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    id_key: str = "id",
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Combine multiple ranked result lists using Reciprocal Rank Fusion.

    RRF Formula: score(d) = Σ 1 / (k + rank(d))

    Args:
        result_lists: List of result lists, each sorted by relevance
        id_key: Key to use for identifying unique items
        k: Ranking constant (default 60)

    Returns:
        Combined results sorted by RRF score
    """
    if not result_lists:
        return []

    # Track RRF scores and item data
    rrf_scores: dict[str, float] = defaultdict(float)
    items: dict[str, dict[str, Any]] = {}

    for list_idx, results in enumerate(result_lists):
        for rank, item in enumerate(results, 1):
            item_id = str(item.get(id_key, f"item_{list_idx}_{rank}"))

            # Add RRF score for this ranking
            rrf_scores[item_id] += 1.0 / (k + rank)

            # Keep the item data (first occurrence wins)
            if item_id not in items:
                items[item_id] = item.copy()

    # Sort by RRF score and return
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    results = []
    for item_id in sorted_ids:
        item = items[item_id].copy()
        item["rrf_score"] = rrf_scores[item_id]
        results.append(item)

    return results


def weighted_rrf(
    result_lists: list[tuple[list[dict[str, Any]], float]],
    id_key: str = "id",
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Weighted Reciprocal Rank Fusion.

    Args:
        result_lists: List of (results, weight) tuples
        id_key: Key to use for identifying unique items
        k: Ranking constant (default 60)

    Returns:
        Combined results sorted by weighted RRF score
    """
    if not result_lists:
        return []

    rrf_scores: dict[str, float] = defaultdict(float)
    items: dict[str, dict[str, Any]] = {}

    for results, weight in result_lists:
        for rank, item in enumerate(results, 1):
            item_id = str(item.get(id_key, f"item_{rank}"))

            # Add weighted RRF score
            rrf_scores[item_id] += weight * (1.0 / (k + rank))

            if item_id not in items:
                items[item_id] = item.copy()

    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    results = []
    for item_id in sorted_ids:
        item = items[item_id].copy()
        item["rrf_score"] = rrf_scores[item_id]
        results.append(item)

    return results


def merge_scores(
    vector_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    id_key: str = "id",
) -> list[dict[str, Any]]:
    """
    Simple weighted score combination.

    Args:
        vector_results: Results from vector search (with 'score' key)
        bm25_results: Results from BM25 search (with 'score' key)
        vector_weight: Weight for vector scores
        bm25_weight: Weight for BM25 scores
        id_key: Key to identify unique items

    Returns:
        Combined results sorted by weighted score
    """
    # Normalize scores to 0-1 range
    def normalize(results: list[dict], score_key: str = "score") -> dict[str, float]:
        if not results:
            return {}
        scores = [r.get(score_key, 0) for r in results]
        min_s, max_s = min(scores), max(scores)
        range_s = max_s - min_s if max_s > min_s else 1.0
        return {
            str(r.get(id_key)): (r.get(score_key, 0) - min_s) / range_s
            for r in results
        }

    vector_scores = normalize(vector_results)
    bm25_scores = normalize(bm25_results)

    # Combine items
    items: dict[str, dict[str, Any]] = {}
    for r in vector_results + bm25_results:
        item_id = str(r.get(id_key))
        if item_id not in items:
            items[item_id] = r.copy()

    # Calculate combined scores
    all_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
    combined = []
    for item_id in all_ids:
        item = items[item_id].copy()
        v_score = vector_scores.get(item_id, 0)
        b_score = bm25_scores.get(item_id, 0)
        item["combined_score"] = vector_weight * v_score + bm25_weight * b_score
        item["vector_score_normalized"] = v_score
        item["bm25_score_normalized"] = b_score
        combined.append(item)

    return sorted(combined, key=lambda x: x["combined_score"], reverse=True)
