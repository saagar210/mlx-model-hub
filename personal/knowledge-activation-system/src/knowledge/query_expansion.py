"""
Query expansion for improved search recall.

Expands user queries with:
- Synonyms and related terms
- Acronym expansions
- Common variations
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from knowledge.cache import CacheType, get_cache
from knowledge.config import get_settings

logger = logging.getLogger(__name__)


# =============================================================================
# Technical Synonym Dictionary
# =============================================================================

SYNONYMS: dict[str, list[str]] = {
    # Programming Languages
    "python": ["py", "python3"],
    "javascript": ["js", "ecmascript", "es6", "es2015"],
    "typescript": ["ts"],
    "golang": ["go"],
    "rust": ["rustlang"],

    # Frameworks - Python
    "fastapi": ["fast api", "starlette"],
    "django": [],
    "flask": [],
    "pydantic": [],
    "sqlalchemy": ["sql alchemy"],
    "langchain": ["lang chain"],
    "llamaindex": ["llama index", "llama-index"],

    # Frameworks - JavaScript
    "nextjs": ["next.js", "next js", "next"],
    "react": ["reactjs", "react.js"],
    "vue": ["vuejs", "vue.js"],
    "angular": ["angularjs"],
    "svelte": ["sveltekit"],
    "nodejs": ["node.js", "node"],

    # Databases
    "postgresql": ["postgres", "psql", "pg"],
    "mongodb": ["mongo"],
    "redis": [],
    "elasticsearch": ["elastic", "es"],
    "sqlite": ["sqlite3"],
    "mysql": ["mariadb"],

    # AI/ML
    "llm": ["large language model", "language model"],
    "rag": ["retrieval augmented generation", "retrieval-augmented"],
    "embedding": ["embeddings", "vector embedding", "text embedding"],
    "vector": ["vectors", "vector search", "similarity search"],
    "semantic": ["semantic search", "meaning-based"],
    "transformer": ["transformers", "attention"],
    "fine-tuning": ["finetuning", "fine tuning"],
    "prompt": ["prompting", "prompt engineering"],

    # Claude/Anthropic
    "claude": ["anthropic", "claude ai"],
    "mcp": ["model context protocol", "context protocol"],
    "tool use": ["function calling", "tool calling", "tools"],

    # DevOps
    "docker": ["container", "containerization"],
    "kubernetes": ["k8s", "kube"],
    "ci/cd": ["cicd", "ci cd", "continuous integration", "continuous deployment"],
    "github actions": ["gh actions", "gha"],

    # Concepts
    "api": ["rest api", "restful", "endpoint"],
    "authentication": ["auth", "authn", "login"],
    "authorization": ["authz", "permissions", "access control"],
    "dependency injection": ["di", "ioc", "inversion of control"],
    "async": ["asynchronous", "await", "asyncio"],
    "orm": ["object relational mapping"],
    "crud": ["create read update delete"],
    "cache": ["caching", "cached"],
    "queue": ["message queue", "task queue", "job queue"],

    # Patterns
    "repository pattern": ["repo pattern"],
    "factory pattern": ["factory"],
    "singleton": ["singleton pattern"],
    "observer": ["observer pattern", "pub sub", "pubsub"],
    "middleware": [],

    # Testing
    "unit test": ["unittest", "unit testing"],
    "integration test": ["integration testing"],
    "e2e": ["end to end", "end-to-end", "e2e test"],
    "pytest": [],
    "jest": [],

    # Common abbreviations
    "config": ["configuration", "settings"],
    "env": ["environment", "environment variables"],
    "db": ["database"],
    "repo": ["repository"],
    "func": ["function"],
    "arg": ["argument", "parameter"],
    "var": ["variable"],
    "const": ["constant"],
    "impl": ["implementation"],
    "init": ["initialize", "initialization"],
    "msg": ["message"],
    "req": ["request"],
    "res": ["response"],
    "err": ["error"],
    "exc": ["exception"],
}

# Build reverse lookup for efficient expansion
_REVERSE_SYNONYMS: dict[str, str] = {}
for primary, synonyms in SYNONYMS.items():
    for syn in synonyms:
        _REVERSE_SYNONYMS[syn.lower()] = primary


# =============================================================================
# Query Expansion
# =============================================================================


@dataclass
class ExpandedQuery:
    """Result of query expansion."""
    original: str
    expanded: str
    terms_added: list[str]
    expansion_applied: bool


def _normalize_term(term: str) -> str:
    """Normalize a term for lookup."""
    return term.lower().strip()


def _extract_terms(query: str) -> list[str]:
    """Extract searchable terms from query."""
    # Split on whitespace and common delimiters
    terms = re.split(r'[\s,;:]+', query)
    # Also try to find multi-word phrases
    words = query.lower().split()

    # Check for 2-word and 3-word phrases
    phrases = []
    for i in range(len(words)):
        if i + 1 < len(words):
            phrases.append(" ".join(words[i:i+2]))
        if i + 2 < len(words):
            phrases.append(" ".join(words[i:i+3]))

    return [t for t in terms + phrases if t]


def expand_term(term: str) -> list[str]:
    """
    Expand a single term to include synonyms.

    Returns list of related terms (not including original).
    """
    normalized = _normalize_term(term)
    expansions = []

    # Direct lookup
    if normalized in SYNONYMS:
        expansions.extend(SYNONYMS[normalized])

    # Reverse lookup (synonym -> primary)
    if normalized in _REVERSE_SYNONYMS:
        primary = _REVERSE_SYNONYMS[normalized]
        if primary != normalized:
            expansions.append(primary)
        # Also add other synonyms of the primary
        expansions.extend(s for s in SYNONYMS.get(primary, []) if s != normalized)

    return list(set(expansions))


async def expand_query(query: str) -> ExpandedQuery:
    """
    Expand a search query with synonyms and related terms.

    Args:
        query: Original search query

    Returns:
        ExpandedQuery with original and expanded versions
    """
    settings = get_settings()

    if not settings.search_enable_query_expansion:
        return ExpandedQuery(
            original=query,
            expanded=query,
            terms_added=[],
            expansion_applied=False,
        )

    # Check cache first
    cache = await get_cache()
    cached_result = await cache.get(CacheType.QUERY_EXPANSION, query)
    if cached_result:
        return ExpandedQuery(**cached_result)

    # Extract and expand terms
    terms = _extract_terms(query)
    all_expansions: set[str] = set()

    for term in terms:
        expansions = expand_term(term)
        all_expansions.update(expansions)

    # Remove terms that are already in the query
    query_lower = query.lower()
    new_terms = [t for t in all_expansions if t.lower() not in query_lower]

    # Build expanded query
    if new_terms:
        # Add expansions with OR semantics for search
        expansion_str = " ".join(new_terms[:5])  # Limit to 5 expansions
        expanded = f"{query} {expansion_str}"
    else:
        expanded = query

    result = ExpandedQuery(
        original=query,
        expanded=expanded,
        terms_added=new_terms[:5],
        expansion_applied=bool(new_terms),
    )

    # Cache the result
    await cache.set(
        CacheType.QUERY_EXPANSION,
        {
            "original": result.original,
            "expanded": result.expanded,
            "terms_added": result.terms_added,
            "expansion_applied": result.expansion_applied,
        },
        query,
    )

    if result.expansion_applied:
        logger.debug(
            "query_expanded",
            extra={
                "original": query,
                "terms_added": result.terms_added,
            }
        )

    return result


def get_all_synonyms() -> dict[str, list[str]]:
    """Get the full synonym dictionary (for admin/debugging)."""
    return SYNONYMS.copy()


def add_synonym(primary: str, synonyms: list[str]) -> None:
    """
    Add synonyms at runtime.

    Note: These are not persisted. For permanent additions,
    update the SYNONYMS dictionary in this module.
    """
    primary = _normalize_term(primary)

    normalized_synonyms = [_normalize_term(s) for s in synonyms]

    if primary in SYNONYMS:
        existing = set(SYNONYMS[primary])
        existing.update(normalized_synonyms)
        SYNONYMS[primary] = list(existing)
    else:
        SYNONYMS[primary] = normalized_synonyms

    # Update reverse lookup
    for syn in normalized_synonyms:
        _REVERSE_SYNONYMS[syn] = primary

    logger.info("synonyms_added", primary=primary, count=len(synonyms))  # type: ignore[call-arg]
