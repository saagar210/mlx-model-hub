"""Multi-layer caching with TTL, invalidation, and distributed support."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheBackend(str, Enum):
    """Cache backend types."""

    MEMORY = "memory"
    REDIS = "redis"
    MULTI_TIER = "multi_tier"


@dataclass
class CacheConfig:
    """Cache configuration."""

    backend: CacheBackend = CacheBackend.MEMORY
    redis_url: str | None = None
    default_ttl: int = 3600  # seconds
    max_memory_items: int = 10000
    max_memory_size_mb: int = 100
    namespace: str = "cache"
    serializer: str = "json"  # json or pickle


@dataclass
class CacheEntry:
    """A cached value with metadata."""

    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    hits: int = 0
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def ttl_remaining(self) -> float | None:
        if self.expires_at is None:
            return None
        return max(0, self.expires_at - time.time())


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    expirations: int = 0
    evictions: int = 0
    total_items: int = 0
    memory_size_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class MemoryCache:
    """In-memory LRU cache."""

    def __init__(self, max_items: int = 10000, max_size_mb: int = 100):
        self.max_items = max_items
        self.max_size_bytes = max_size_mb * 1024 * 1024

        self._cache: dict[str, CacheEntry] = {}
        self._access_order: list[str] = []
        self._lock = asyncio.Lock()
        self._stats = CacheStats()
        self._current_size = 0

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired:
                self._stats.expirations += 1
                await self._delete_entry(key)
                return None

            entry.hits += 1
            self._stats.hits += 1

            # Update access order for LRU
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            return entry.value

    async def set(
        self, key: str, value: Any, ttl: int | None = None
    ) -> None:
        """Set value in cache."""
        async with self._lock:
            # Calculate size
            size = len(json.dumps(value, default=str).encode())

            # Evict if needed
            await self._ensure_capacity(size)

            expires_at = time.time() + ttl if ttl else None

            entry = CacheEntry(
                value=value,
                expires_at=expires_at,
                size_bytes=size,
            )

            # Update if exists
            if key in self._cache:
                self._current_size -= self._cache[key].size_bytes

            self._cache[key] = entry
            self._current_size += size
            self._stats.sets += 1
            self._stats.total_items = len(self._cache)

            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        async with self._lock:
            return await self._delete_entry(key)

    async def _delete_entry(self, key: str) -> bool:
        """Internal delete without lock."""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._current_size -= entry.size_bytes
            self._stats.deletes += 1
            self._stats.total_items = len(self._cache)

            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    async def _ensure_capacity(self, needed_size: int) -> None:
        """Ensure cache has capacity, evicting if needed."""
        # Evict by count
        while len(self._cache) >= self.max_items and self._access_order:
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                entry = self._cache.pop(oldest_key)
                self._current_size -= entry.size_bytes
                self._stats.evictions += 1

        # Evict by size
        while (
            self._current_size + needed_size > self.max_size_bytes
            and self._access_order
        ):
            oldest_key = self._access_order.pop(0)
            if oldest_key in self._cache:
                entry = self._cache.pop(oldest_key)
                self._current_size -= entry.size_bytes
                self._stats.evictions += 1

        self._stats.total_items = len(self._cache)

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._current_size = 0
            self._stats.total_items = 0

    @property
    def stats(self) -> CacheStats:
        self._stats.memory_size_bytes = self._current_size
        return self._stats


class RedisCache:
    """Redis-based cache."""

    def __init__(self, redis_url: str, namespace: str = "cache"):
        self.redis_url = redis_url
        self.namespace = namespace
        self._redis: Any = None
        self._stats = CacheStats()

    async def connect(self) -> None:
        """Connect to Redis."""
        import redis.asyncio as redis

        self._redis = await redis.from_url(self.redis_url)
        logger.info(f"Connected to Redis cache: {self.redis_url}")

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()

    def _make_key(self, key: str) -> str:
        """Create namespaced key."""
        return f"{self.namespace}:{key}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if not self._redis:
            return None

        try:
            data = await self._redis.get(self._make_key(key))
            if data is None:
                self._stats.misses += 1
                return None

            self._stats.hits += 1
            return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None

    async def set(
        self, key: str, value: Any, ttl: int | None = None
    ) -> None:
        """Set value in cache."""
        if not self._redis:
            return

        try:
            data = json.dumps(value, default=str)
            if ttl:
                await self._redis.setex(self._make_key(key), ttl, data)
            else:
                await self._redis.set(self._make_key(key), data)
            self._stats.sets += 1
        except Exception as e:
            logger.warning(f"Redis set error: {e}")

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self._redis:
            return False

        try:
            result = await self._redis.delete(self._make_key(key))
            if result:
                self._stats.deletes += 1
            return bool(result)
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")
            return False

    async def clear(self) -> None:
        """Clear all cache entries in namespace."""
        if not self._redis:
            return

        try:
            cursor = 0
            pattern = f"{self.namespace}:*"
            while True:
                cursor, keys = await self._redis.scan(cursor, match=pattern)
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"Redis clear error: {e}")

    @property
    def stats(self) -> CacheStats:
        return self._stats


class CacheLayer:
    """
    Multi-tier caching layer.

    Features:
    - L1 (memory) + L2 (Redis) caching
    - Automatic fallthrough
    - Cache invalidation
    - Function decorators
    """

    def __init__(self, config: CacheConfig | None = None):
        """Initialize cache layer."""
        self.config = config or CacheConfig()

        self._memory = MemoryCache(
            max_items=self.config.max_memory_items,
            max_size_mb=self.config.max_memory_size_mb,
        )

        self._redis: RedisCache | None = None
        if self.config.redis_url:
            self._redis = RedisCache(
                self.config.redis_url,
                self.config.namespace,
            )

    async def start(self) -> None:
        """Initialize cache connections."""
        if self._redis:
            await self._redis.connect()
        logger.info(f"Cache layer started (backend={self.config.backend.value})")

    async def close(self) -> None:
        """Close cache connections."""
        if self._redis:
            await self._redis.close()

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Checks L1 (memory) first, then L2 (Redis).
        """
        # Try memory first
        value = await self._memory.get(key)
        if value is not None:
            return value

        # Try Redis
        if self._redis:
            value = await self._redis.get(key)
            if value is not None:
                # Populate L1 cache
                await self._memory.set(
                    key, value, self.config.default_ttl
                )
                return value

        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        Set value in cache.

        Writes to both L1 (memory) and L2 (Redis).
        """
        ttl = ttl or self.config.default_ttl

        await self._memory.set(key, value, ttl)

        if self._redis:
            await self._redis.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete value from all cache tiers."""
        deleted_memory = await self._memory.delete(key)
        deleted_redis = False
        if self._redis:
            deleted_redis = await self._redis.delete(key)
        return deleted_memory or deleted_redis

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        # Note: Memory cache doesn't support pattern matching efficiently
        # This is primarily for Redis
        count = 0
        if self._redis and self._redis._redis:
            try:
                cursor = 0
                full_pattern = f"{self.config.namespace}:{pattern}"
                while True:
                    cursor, keys = await self._redis._redis.scan(
                        cursor, match=full_pattern
                    )
                    if keys:
                        await self._redis._redis.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning(f"Pattern invalidation error: {e}")

        return count

    async def clear(self) -> None:
        """Clear all cache entries."""
        await self._memory.clear()
        if self._redis:
            await self._redis.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        memory_stats = self._memory.stats
        redis_stats = self._redis.stats if self._redis else None

        return {
            "memory": {
                "hits": memory_stats.hits,
                "misses": memory_stats.misses,
                "hit_rate": memory_stats.hit_rate,
                "items": memory_stats.total_items,
                "size_mb": memory_stats.memory_size_bytes / 1024 / 1024,
                "evictions": memory_stats.evictions,
            },
            "redis": {
                "hits": redis_stats.hits if redis_stats else 0,
                "misses": redis_stats.misses if redis_stats else 0,
                "hit_rate": redis_stats.hit_rate if redis_stats else 0,
            }
            if redis_stats
            else None,
        }

    def cached(
        self,
        ttl: int | None = None,
        key_builder: Callable[..., str] | None = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """
        Decorator for caching function results.

        Args:
            ttl: Time to live in seconds
            key_builder: Custom function to build cache key
        """

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> T:
                # Build cache key
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    cache_key = self._build_key(func.__name__, args, kwargs)

                # Try cache
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Cache result
                await self.set(cache_key, result, ttl)

                return result

            return wrapper

        return decorator

    def _build_key(
        self,
        func_name: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str:
        """Build a cache key from function call."""
        key_parts = [func_name]

        for arg in args:
            key_parts.append(str(arg))

        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")

        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
