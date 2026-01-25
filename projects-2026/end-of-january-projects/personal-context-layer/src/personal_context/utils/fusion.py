"""Result fusion utilities for combining results from multiple sources."""

from collections import defaultdict

from personal_context.schema import ContextItem


def reciprocal_rank_fusion(
    results_lists: list[list[ContextItem]],
    k: int = 60,
) -> list[ContextItem]:
    """
    Fuse multiple ranked result lists using Reciprocal Rank Fusion (RRF).

    RRF assigns scores based on rank position: score = 1 / (k + rank)
    This is robust to different score scales across sources.

    Args:
        results_lists: List of result lists from different sources
        k: Constant to prevent high scores for top results (default 60)

    Returns:
        Fused and re-ranked list of ContextItems
    """
    scores: dict[str, float] = defaultdict(float)
    items: dict[str, ContextItem] = {}

    for results in results_lists:
        for rank, item in enumerate(results):
            # RRF score formula
            scores[item.id] += 1.0 / (k + rank + 1)  # +1 for 0-indexed ranks

            # Keep the item (first occurrence wins)
            if item.id not in items:
                items[item.id] = item

    # Sort by fused score
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    # Update relevance scores
    result = []
    for item_id in sorted_ids:
        item = items[item_id]
        item.relevance_score = scores[item_id]
        result.append(item)

    return result


def time_decay_score(
    item: ContextItem,
    base_score: float,
    half_life_hours: float = 168,  # 1 week
) -> float:
    """
    Apply time decay to a relevance score.

    Uses exponential decay: score * exp(-age_hours / half_life)

    Args:
        item: Context item with timestamp
        base_score: Original relevance score
        half_life_hours: Hours until score is halved (default 1 week)

    Returns:
        Time-decayed score
    """
    from datetime import datetime
    import math

    age_hours = (datetime.now() - item.timestamp).total_seconds() / 3600
    decay_factor = math.exp(-age_hours / half_life_hours * math.log(2))

    return base_score * decay_factor


def apply_source_weights(
    items: list[ContextItem],
    weights: dict[str, float] | None = None,
) -> list[ContextItem]:
    """
    Apply source-specific weights to relevance scores.

    Args:
        items: List of context items
        weights: Dict mapping source name to weight multiplier

    Returns:
        Items with adjusted relevance scores
    """
    default_weights = {
        "obsidian": 0.9,
        "git": 0.7,
        "kas": 0.8,
    }
    weights = weights or default_weights

    for item in items:
        source_weight = weights.get(item.source.value, 1.0)
        item.relevance_score *= source_weight

    return items


def deduplicate_by_content(
    items: list[ContextItem],
    similarity_threshold: float = 0.9,
) -> list[ContextItem]:
    """
    Remove near-duplicate items based on content similarity.

    Uses simple Jaccard similarity on word sets for speed.

    Args:
        items: List of context items
        similarity_threshold: Minimum similarity to consider duplicate

    Returns:
        Deduplicated list
    """
    if not items:
        return []

    def get_words(text: str) -> set[str]:
        return set(text.lower().split())

    result: list[ContextItem] = []
    seen_words: list[set[str]] = []

    for item in items:
        item_words = get_words(item.content)

        is_duplicate = False
        for seen in seen_words:
            if not item_words or not seen:
                continue
            intersection = len(item_words & seen)
            union = len(item_words | seen)
            similarity = intersection / union if union > 0 else 0

            if similarity >= similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            result.append(item)
            seen_words.append(item_words)

    return result
