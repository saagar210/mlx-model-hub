"""Query routing for optimal search strategies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from knowledge.logging import get_logger

logger = get_logger(__name__)


class QueryType(Enum):
    """Types of queries for routing."""

    SIMPLE = "simple"  # Direct lookup (e.g., "What is FastAPI?")
    COMPLEX = "complex"  # Needs reasoning (e.g., "How does X work with Y?")
    COMPARISON = "comparison"  # A vs B (e.g., "PostgreSQL vs MySQL")
    HOW_TO = "how_to"  # Procedural (e.g., "How do I implement X?")
    LIST = "list"  # Enumeration (e.g., "What are the features of X?")
    DEFINITION = "definition"  # Concept definition (e.g., "What is RAG?")


@dataclass
class SearchParams:
    """Search parameters optimized for query type."""

    limit: int
    rerank: bool
    vector_weight: float  # Weight for vector search in fusion (0-1)
    include_related: bool  # Whether to include related content
    multi_hop: bool  # Whether to use multi-hop reasoning


# Query type detection patterns
# Note: "or" removed - too many false positives (vector, framework, etc.)
COMPARISON_PATTERNS = [" vs ", " versus ", "compare", "compared to", "difference between", " better than "]
HOW_TO_PATTERNS = ["how do i", "how to", "how can i", "steps to", "guide to", "tutorial", "way to", "implement"]
LIST_PATTERNS = ["what are", "list of", "types of", "examples of", "features of", "options for", "best"]
DEFINITION_PATTERNS = ["what is", "what's", "define", "explain", "meaning of", "definition of"]
COMPLEX_INDICATORS = ["why", "when should", "best practice", "trade-off", "consider", "approach"]


def classify_query(query: str) -> QueryType:
    """Classify query type for routing.

    Args:
        query: User search query

    Returns:
        QueryType enum indicating the query classification
    """
    query_lower = query.lower().strip()
    word_count = len(query_lower.split())

    # Check for comparison queries (highest priority)
    if any(pattern in query_lower for pattern in COMPARISON_PATTERNS):
        if word_count >= 3:  # Avoid false positives on short queries
            return QueryType.COMPARISON

    # Check for how-to queries
    if any(query_lower.startswith(pattern) or f" {pattern}" in query_lower for pattern in HOW_TO_PATTERNS):
        return QueryType.HOW_TO

    # Check for complex queries BEFORE list/definition
    # (so "What are the trade-offs" is COMPLEX, not LIST)
    has_question = "?" in query
    has_complex_indicator = any(ind in query_lower for ind in COMPLEX_INDICATORS)

    if has_complex_indicator:
        return QueryType.COMPLEX

    # Check for list/enumeration queries
    if any(query_lower.startswith(pattern) for pattern in LIST_PATTERNS):
        return QueryType.LIST

    # Check for definition queries
    if any(query_lower.startswith(pattern) for pattern in DEFINITION_PATTERNS):
        return QueryType.DEFINITION

    # Long questions without other indicators are likely complex
    if word_count > 10 and has_question:
        return QueryType.COMPLEX

    # Default to simple lookup
    return QueryType.SIMPLE


def get_search_params(query_type: QueryType) -> SearchParams:
    """Get optimal search parameters for query type.

    Args:
        query_type: Classified query type

    Returns:
        SearchParams optimized for the query type
    """
    params = {
        QueryType.SIMPLE: SearchParams(
            limit=5,
            rerank=False,
            vector_weight=0.5,
            include_related=False,
            multi_hop=False,
        ),
        QueryType.DEFINITION: SearchParams(
            limit=5,
            rerank=True,
            vector_weight=0.6,  # Favor semantic similarity
            include_related=False,
            multi_hop=False,
        ),
        QueryType.HOW_TO: SearchParams(
            limit=10,
            rerank=True,
            vector_weight=0.5,
            include_related=True,  # Include related guides
            multi_hop=False,
        ),
        QueryType.LIST: SearchParams(
            limit=15,
            rerank=True,
            vector_weight=0.5,
            include_related=True,
            multi_hop=False,
        ),
        QueryType.COMPARISON: SearchParams(
            limit=20,
            rerank=True,
            vector_weight=0.4,  # Favor keyword match for entity names
            include_related=True,
            multi_hop=True,  # Need info about both entities
        ),
        QueryType.COMPLEX: SearchParams(
            limit=15,
            rerank=True,
            vector_weight=0.5,
            include_related=True,
            multi_hop=True,  # Decompose complex queries
        ),
    }
    return params.get(query_type, params[QueryType.SIMPLE])


def analyze_query(query: str) -> tuple[QueryType, SearchParams]:
    """Analyze query and return type with optimized parameters.

    Args:
        query: User search query

    Returns:
        Tuple of (QueryType, SearchParams)
    """
    query_type = classify_query(query)
    params = get_search_params(query_type)

    logger.debug(
        "query_analyzed",
        query=query[:50],
        query_type=query_type.value,
        limit=params.limit,
        rerank=params.rerank,
        multi_hop=params.multi_hop,
    )

    return query_type, params
