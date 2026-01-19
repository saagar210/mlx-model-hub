"""Multi-hop reasoning for complex queries."""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.ai import AIProvider, AIResponse
from knowledge.logging import get_logger
from knowledge.search import SearchResult, hybrid_search

logger = get_logger(__name__)


DECOMPOSE_PROMPT = """Break this complex question into 2-3 simpler sub-questions that can be answered independently.
Each sub-question should focus on a single concept or entity.

Guidelines:
- Keep sub-questions concise and searchable
- Focus on key entities or concepts
- Avoid yes/no questions
- Each sub-question should contribute to answering the main question

Question: {query}

Return ONLY the sub-questions, one per line (no numbering, no extra text):"""


@dataclass
class MultiHopResult:
    """Result of multi-hop search."""

    query: str
    sub_queries: list[str]
    results: list[SearchResult]
    deduplicated: bool = True


async def decompose_query(
    query: str,
    ai: AIProvider | None = None,
) -> list[str]:
    """Decompose complex query into sub-questions.

    Args:
        query: Complex user query
        ai: Optional AI provider instance

    Returns:
        List of simpler sub-questions (max 3)
    """
    if ai is None:
        ai = AIProvider()
        should_close = True
    else:
        should_close = False

    try:
        response: AIResponse = await ai.generate(
            prompt=DECOMPOSE_PROMPT.format(query=query),
            temperature=0.3,  # Low temperature for consistent decomposition
            max_tokens=200,
        )

        if not response.success:
            logger.warning(
                "query_decomposition_failed",
                query=query[:50],
                error=response.error,
            )
            return [query]  # Fall back to original query

        # Parse response into sub-questions
        lines = response.content.strip().split("\n")
        sub_queries = []

        for line in lines:
            # Clean up the line
            clean = line.strip()
            # Remove common prefixes like "1.", "- ", "* ", etc.
            if clean and len(clean) > 5:
                # Remove leading numbers/bullets
                for prefix in ["1.", "2.", "3.", "-", "*", "•"]:
                    if clean.startswith(prefix):
                        clean = clean[len(prefix):].strip()
                        break
                if clean:
                    sub_queries.append(clean)

        # Limit to 3 sub-queries
        sub_queries = sub_queries[:3]

        if not sub_queries:
            logger.debug("no_sub_queries_generated", query=query[:50])
            return [query]

        logger.debug(
            "query_decomposed",
            original=query[:50],
            sub_query_count=len(sub_queries),
        )

        return sub_queries

    finally:
        if should_close:
            await ai.close()


async def multihop_search(
    query: str,
    limit: int = 10,
    ai: AIProvider | None = None,
    namespace: str | None = None,
) -> MultiHopResult:
    """Execute multi-hop search for complex queries.

    Decomposes the query into sub-questions, searches each,
    and combines/deduplicates results.

    Args:
        query: Complex user query
        limit: Maximum results to return
        ai: Optional AI provider instance
        namespace: Optional namespace filter

    Returns:
        MultiHopResult with combined results
    """
    # Decompose query
    sub_queries = await decompose_query(query, ai)

    # Search each sub-query
    all_results: list[SearchResult] = []
    seen_ids: set[str] = set()

    for sq in sub_queries:
        # Search with smaller limit per sub-query
        per_query_limit = max(5, limit // len(sub_queries))

        results = await hybrid_search(
            query=sq,
            limit=per_query_limit,
            namespace=namespace,
        )

        # Add unique results
        for result in results:
            content_id = str(result.content_id)
            if content_id not in seen_ids:
                seen_ids.add(content_id)
                all_results.append(result)

    # Sort by score and limit
    all_results.sort(key=lambda r: r.score, reverse=True)
    final_results = all_results[:limit]

    logger.debug(
        "multihop_search_complete",
        query=query[:50],
        sub_query_count=len(sub_queries),
        total_results=len(all_results),
        returned_results=len(final_results),
    )

    return MultiHopResult(
        query=query,
        sub_queries=sub_queries,
        results=final_results,
        deduplicated=True,
    )


async def search_with_routing(
    query: str,
    limit: int = 10,
    namespace: str | None = None,
    force_rerank: bool | None = None,
) -> list[SearchResult]:
    """Search with automatic query routing.

    Analyzes the query, determines optimal search strategy,
    and executes appropriate search method.

    Args:
        query: User search query
        limit: Maximum results
        namespace: Optional namespace filter
        force_rerank: Override auto-rerank decision

    Returns:
        List of search results
    """
    from knowledge.query_router import QueryType, analyze_query

    query_type, params = analyze_query(query)

    # Use multi-hop for complex/comparison queries
    if params.multi_hop and query_type in (QueryType.COMPLEX, QueryType.COMPARISON):
        result = await multihop_search(
            query=query,
            limit=params.limit if limit == 10 else limit,  # Use default unless overridden
            namespace=namespace,
        )
        results = result.results
    else:
        # Standard hybrid search
        results = await hybrid_search(
            query=query,
            limit=params.limit if limit == 10 else limit,
            namespace=namespace,
        )

    # Apply reranking if configured
    if (force_rerank is True) or (force_rerank is None and params.rerank):
        from knowledge.reranker import rerank_results

        results = await rerank_results(query, results)

    return results[:limit]
