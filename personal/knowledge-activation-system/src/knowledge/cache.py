"""
Redis caching layer for KAS.

Provides caching for:
- Search results (short TTL)
- Embedding vectors (long TTL)
- Reranking results (medium TTL)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from knowledge.config import get_settings
from knowledge.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CacheType(Enum):
    """Cache types with different TTLs."""
    SEARCH = "search"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    QUERY_EXPANSION = "expansion"


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class RedisCache:
    """
    Async Redis cache with support for different cache types.

    Features:
    - Automatic key hashing for complex inputs
    - Type-specific TTLs
    - Graceful degradation on Redis failures
    - Cache statistics tracking
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._pool: ConnectionPool | None = None
        self._client: redis.Redis | None = None  # type: ignore[type-arg]
        self._stats: dict[CacheType, CacheStats] = {
            ct: CacheStats() for ct in CacheType
        }
        self._connected = False

    async def connect(self) -> bool:
        """Connect to Redis. Returns True if successful."""
        if not self.settings.redis_enabled:
            logger.info("Redis caching disabled by configuration")
            return False

        try:
            self._pool = ConnectionPool.from_url(
                self.settings.redis_url,
                max_connections=20,
                decode_responses=True,
            )
            self._client = redis.Redis(connection_pool=self._pool)

            # Test connection
            await self._client.ping()  # type: ignore[misc]
            self._connected = True
            logger.info("redis_connected", url=self.settings.redis_url)
            return True
        except Exception as e:
            logger.warning(
                "redis_connection_failed",
                error=str(e),
                url=self.settings.redis_url,
            )
            self._connected = False
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        self._connected = False
        logger.info("redis_disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected

    def _get_ttl(self, cache_type: CacheType) -> int:
        """Get TTL for cache type."""
        ttl_map = {
            CacheType.SEARCH: self.settings.cache_ttl_search,
            CacheType.EMBEDDING: self.settings.cache_ttl_embedding,
            CacheType.RERANK: self.settings.cache_ttl_rerank,
            CacheType.QUERY_EXPANSION: 3600,  # 1 hour for expansions
        }
        return ttl_map.get(cache_type, 300)

    def _make_key(self, cache_type: CacheType, *args: Any) -> str:
        """Generate cache key from arguments."""
        # Create deterministic hash of arguments
        key_data = json.dumps(args, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]
        return f"kas:{cache_type.value}:{key_hash}"

    async def get(
        self,
        cache_type: CacheType,
        *args: Any,
    ) -> Any | None:
        """
        Get value from cache.

        Args:
            cache_type: Type of cache (determines TTL on set)
            *args: Arguments that form the cache key

        Returns:
            Cached value or None if not found/error
        """
        if not self._connected or self._client is None:
            return None

        key = self._make_key(cache_type, *args)

        try:
            value = await self._client.get(key)
            if value is not None:
                self._stats[cache_type].hits += 1
                logger.debug("cache_hit", cache_type=cache_type.value, key=key)
                return json.loads(value)
            else:
                self._stats[cache_type].misses += 1
                return None
        except Exception as e:
            self._stats[cache_type].errors += 1
            logger.warning("cache_get_error", error=str(e), key=key)
            return None

    async def set(
        self,
        cache_type: CacheType,
        value: Any,
        *args: Any,
    ) -> bool:
        """
        Set value in cache.

        Args:
            cache_type: Type of cache
            value: Value to cache (must be JSON serializable)
            *args: Arguments that form the cache key

        Returns:
            True if successful
        """
        if not self._connected or self._client is None:
            return False

        key = self._make_key(cache_type, *args)
        ttl = self._get_ttl(cache_type)

        try:
            serialized = json.dumps(value, default=str)
            await self._client.setex(key, ttl, serialized)
            logger.debug("cache_set", cache_type=cache_type.value, key=key, ttl=ttl)
            return True
        except Exception as e:
            self._stats[cache_type].errors += 1
            logger.warning("cache_set_error", error=str(e), key=key)
            return False

    async def delete(self, cache_type: CacheType, *args: Any) -> bool:
        """Delete a specific cache entry."""
        if not self._connected or self._client is None:
            return False

        key = self._make_key(cache_type, *args)

        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.warning("cache_delete_error", error=str(e), key=key)
            return False

    async def clear(self, cache_type: CacheType | None = None) -> int:
        """
        Clear cache entries.

        Args:
            cache_type: Specific type to clear, or None for all

        Returns:
            Number of keys deleted
        """
        if not self._connected or self._client is None:
            return 0

        try:
            if cache_type:
                pattern = f"kas:{cache_type.value}:*"
            else:
                pattern = "kas:*"

            keys: list[str] = []
            async for key in self._client.scan_iter(match=pattern, count=100):
                keys.append(key)

            if keys:
                deleted = await self._client.delete(*keys)
                logger.info("cache_cleared", pattern=pattern, deleted=deleted)
                return deleted
            return 0
        except Exception as e:
            logger.warning("cache_clear_error", error=str(e))
            return 0

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """Get cache statistics."""
        return {
            ct.value: {
                "hits": stats.hits,
                "misses": stats.misses,
                "errors": stats.errors,
                "hit_rate": f"{stats.hit_rate:.2%}",
            }
            for ct, stats in self._stats.items()
        }

    async def get_info(self) -> dict[str, Any] | None:
        """Get Redis server info."""
        if not self._connected or self._client is None:
            return None

        try:
            info = await self._client.info()
            return {
                "version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "total_keys": sum(
                    info.get(f"db{i}", {}).get("keys", 0)
                    for i in range(16)
                ),
            }
        except Exception as e:
            logger.warning("cache_info_error", error=str(e))
            return None


# Global cache instance
_cache: RedisCache | None = None


async def get_cache() -> RedisCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = RedisCache()
        await _cache.connect()
    return _cache


async def close_cache() -> None:
    """Close the global cache instance."""
    global _cache
    if _cache is not None:
        await _cache.close()
        _cache = None


# Decorator for caching function results
def cached(cache_type: CacheType) -> Any:  # type: ignore[no-untyped-def]
    """
    Decorator to cache async function results.

    Usage:
        @cached(CacheType.EMBEDDING)
        async def get_embedding(text: str) -> list[float]:
            ...
    """
    def decorator(func: Any) -> Any:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = await get_cache()

            # Create cache key from function name and arguments
            cache_key_args = (func.__name__, args, tuple(sorted(kwargs.items())))

            # Try cache first
            result = await cache.get(cache_type, *cache_key_args)
            if result is not None:
                return result

            # Call function
            result = await func(*args, **kwargs)

            # Cache result
            await cache.set(cache_type, result, *cache_key_args)

            return result
        return wrapper
    return decorator
