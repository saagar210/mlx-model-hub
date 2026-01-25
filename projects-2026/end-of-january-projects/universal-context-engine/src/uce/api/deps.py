"""
FastAPI dependency injection.
"""

from typing import AsyncIterator

import asyncpg

from ..core.config import settings
from ..core.database import get_db_pool
from ..search.hybrid_search import HybridSearchEngine
from ..entity_resolution.resolver import EntityResolver


# Global instances (initialized on startup)
_search_engine: HybridSearchEngine | None = None
_entity_resolver: EntityResolver | None = None


async def get_search_engine() -> HybridSearchEngine:
    """Get search engine instance."""
    global _search_engine
    if _search_engine is None:
        pool = await get_db_pool()
        _search_engine = HybridSearchEngine(
            pg_pool=pool,
            ollama_url=settings.ollama_url,
            embedding_model=settings.embedding_model,
            rrf_k=settings.search_rrf_k,
            decay_half_life_hours=settings.search_decay_half_life_hours,
        )
    return _search_engine


async def get_entity_resolver() -> EntityResolver:
    """Get entity resolver instance."""
    global _entity_resolver
    if _entity_resolver is None:
        pool = await get_db_pool()
        _entity_resolver = EntityResolver(pool)
    return _entity_resolver


async def get_db() -> AsyncIterator[asyncpg.Pool]:
    """Get database pool."""
    pool = await get_db_pool()
    yield pool


async def cleanup_deps() -> None:
    """Cleanup dependencies on shutdown."""
    global _search_engine, _entity_resolver
    _search_engine = None
    _entity_resolver = None


__all__ = [
    "get_search_engine",
    "get_entity_resolver",
    "get_db",
    "cleanup_deps",
]
