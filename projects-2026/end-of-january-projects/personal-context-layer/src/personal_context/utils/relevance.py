"""Relevance scoring utilities for context items."""

import math
from datetime import datetime

from personal_context.schema import ContextItem, ContextSource


# Default source weights (can be overridden)
DEFAULT_SOURCE_WEIGHTS = {
    ContextSource.OBSIDIAN: 0.9,  # Personal notes are highly relevant
    ContextSource.GIT: 0.7,  # Code commits useful but less immediate
    ContextSource.KAS: 0.8,  # Knowledge base is authoritative
}


def compute_relevance_score(
    item: ContextItem,
    query: str | None = None,
    source_weights: dict[ContextSource, float] | None = None,
    recency_half_life_hours: float = 168.0,  # 1 week
) -> float:
    """
    Compute comprehensive relevance score for a context item.

    Combines:
    - Base relevance score from search
    - Source weight
    - Recency decay
    - Query match boost

    Args:
        item: Context item to score
        query: Optional query for keyword matching
        source_weights: Source-specific weight multipliers
        recency_half_life_hours: Hours until score decays by half

    Returns:
        Final relevance score (0-1 range, can exceed 1 with boosts)
    """
    weights = source_weights or DEFAULT_SOURCE_WEIGHTS

    # Start with base relevance score
    score = item.relevance_score if item.relevance_score > 0 else 0.5

    # Apply source weight
    source_weight = weights.get(item.source, 1.0)
    score *= source_weight

    # Apply recency decay
    age_hours = (datetime.now() - item.timestamp).total_seconds() / 3600
    decay = math.exp(-age_hours / recency_half_life_hours * math.log(2))
    score *= decay

    # Query match boost
    if query:
        boost = compute_query_boost(item, query)
        score *= (1 + boost)

    return score


def compute_query_boost(item: ContextItem, query: str) -> float:
    """
    Compute boost factor based on query match quality.

    Returns boost multiplier (0 = no boost, 1 = 100% boost).
    """
    boost = 0.0
    query_lower = query.lower()
    query_terms = query_lower.split()

    # Title match (highest value)
    title_lower = item.title.lower()
    if query_lower in title_lower:
        boost += 0.5
    elif any(term in title_lower for term in query_terms):
        boost += 0.2

    # Exact phrase in content
    content_lower = item.content.lower()
    if query_lower in content_lower:
        boost += 0.3

    # Term frequency in content
    term_matches = sum(1 for term in query_terms if term in content_lower)
    boost += term_matches * 0.05

    return min(boost, 1.0)  # Cap at 100% boost


def rerank_by_relevance(
    items: list[ContextItem],
    query: str | None = None,
    limit: int | None = None,
) -> list[ContextItem]:
    """
    Rerank items by computed relevance score.

    Updates each item's relevance_score and returns sorted list.
    """
    for item in items:
        item.relevance_score = compute_relevance_score(item, query)

    items.sort(key=lambda x: x.relevance_score, reverse=True)

    if limit:
        items = items[:limit]

    return items


def group_by_source(items: list[ContextItem]) -> dict[ContextSource, list[ContextItem]]:
    """Group items by their source."""
    groups: dict[ContextSource, list[ContextItem]] = {}

    for item in items:
        if item.source not in groups:
            groups[item.source] = []
        groups[item.source].append(item)

    return groups


def interleave_sources(
    items: list[ContextItem],
    max_per_source: int = 3,
) -> list[ContextItem]:
    """
    Interleave items from different sources for diversity.

    Ensures representation from multiple sources in top results.
    """
    groups = group_by_source(items)
    result: list[ContextItem] = []
    source_counts: dict[ContextSource, int] = {}

    # Sort each group by relevance
    for source in groups:
        groups[source].sort(key=lambda x: x.relevance_score, reverse=True)
        source_counts[source] = 0

    # Interleave while respecting max_per_source
    while True:
        added = False
        for source, source_items in groups.items():
            if source_counts[source] < min(max_per_source, len(source_items)):
                item = source_items[source_counts[source]]
                result.append(item)
                source_counts[source] += 1
                added = True

        if not added:
            break

    return result
