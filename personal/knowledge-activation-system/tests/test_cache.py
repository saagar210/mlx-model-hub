"""Tests for Redis caching layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from knowledge.cache import (
    RedisCache,
    CacheType,
    CacheStats,
    get_cache,
    close_cache,
    cached,
)


class TestCacheStats:
    """Test CacheStats dataclass."""

    def test_hit_rate_zero_total(self):
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        stats = CacheStats(hits=3, misses=7)
        assert stats.hit_rate == 0.3

    def test_hit_rate_all_hits(self):
        stats = CacheStats(hits=10, misses=0)
        assert stats.hit_rate == 1.0


class TestCacheType:
    """Test CacheType enum."""

    def test_cache_types_exist(self):
        assert CacheType.SEARCH.value == "search"
        assert CacheType.EMBEDDING.value == "embedding"
        assert CacheType.RERANK.value == "rerank"
        assert CacheType.QUERY_EXPANSION.value == "expansion"


class TestRedisCache:
    """Test RedisCache class."""

    @pytest.fixture
    def cache(self):
        """Create a RedisCache instance for testing."""
        with patch("knowledge.cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_enabled=True,
                redis_url="redis://localhost:6379/0",
                cache_ttl_search=300,
                cache_ttl_embedding=86400,
                cache_ttl_rerank=600,
            )
            return RedisCache()

    def test_initial_state(self, cache):
        """Test cache initial state."""
        assert cache._connected is False
        assert cache._client is None
        assert cache._pool is None

    def test_is_connected_false_initially(self, cache):
        """Test is_connected property."""
        assert cache.is_connected is False

    def test_make_key_consistency(self, cache):
        """Test cache key generation is consistent."""
        key1 = cache._make_key(CacheType.SEARCH, "query", 10)
        key2 = cache._make_key(CacheType.SEARCH, "query", 10)
        assert key1 == key2
        assert key1.startswith("kas:search:")

    def test_make_key_different_types(self, cache):
        """Test different cache types generate different keys."""
        search_key = cache._make_key(CacheType.SEARCH, "query")
        embed_key = cache._make_key(CacheType.EMBEDDING, "query")
        assert search_key != embed_key
        assert "search" in search_key
        assert "embedding" in embed_key

    def test_make_key_different_args(self, cache):
        """Test different arguments generate different keys."""
        key1 = cache._make_key(CacheType.SEARCH, "query1")
        key2 = cache._make_key(CacheType.SEARCH, "query2")
        assert key1 != key2

    def test_get_ttl_search(self, cache):
        """Test TTL for search cache."""
        ttl = cache._get_ttl(CacheType.SEARCH)
        assert ttl == 300

    def test_get_ttl_embedding(self, cache):
        """Test TTL for embedding cache."""
        ttl = cache._get_ttl(CacheType.EMBEDDING)
        assert ttl == 86400

    def test_get_ttl_rerank(self, cache):
        """Test TTL for rerank cache."""
        ttl = cache._get_ttl(CacheType.RERANK)
        assert ttl == 600

    def test_get_stats_initial(self, cache):
        """Test initial stats are zero."""
        stats = cache.get_stats()
        for cache_type in CacheType:
            assert stats[cache_type.value]["hits"] == 0
            assert stats[cache_type.value]["misses"] == 0
            assert stats[cache_type.value]["errors"] == 0

    async def test_get_returns_none_when_not_connected(self, cache):
        """Test get returns None when not connected."""
        result = await cache.get(CacheType.SEARCH, "query")
        assert result is None

    async def test_set_returns_false_when_not_connected(self, cache):
        """Test set returns False when not connected."""
        result = await cache.set(CacheType.SEARCH, {"data": "value"}, "query")
        assert result is False

    async def test_delete_returns_false_when_not_connected(self, cache):
        """Test delete returns False when not connected."""
        result = await cache.delete(CacheType.SEARCH, "query")
        assert result is False

    async def test_clear_returns_zero_when_not_connected(self, cache):
        """Test clear returns 0 when not connected."""
        result = await cache.clear(CacheType.SEARCH)
        assert result == 0


class TestCacheConnection:
    """Test cache connection behavior."""

    @pytest.fixture
    def disabled_cache(self):
        """Create a cache with Redis disabled."""
        with patch("knowledge.cache.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(redis_enabled=False)
            return RedisCache()

    async def test_connect_disabled(self, disabled_cache):
        """Test connect returns False when Redis is disabled."""
        result = await disabled_cache.connect()
        assert result is False
        assert disabled_cache.is_connected is False


class TestCachedDecorator:
    """Test the @cached decorator."""

    async def test_decorator_calls_function_on_miss(self):
        """Test decorator calls function when cache misses."""
        call_count = 0

        @cached(CacheType.EMBEDDING)
        async def expensive_function(text: str) -> list[float]:
            nonlocal call_count
            call_count += 1
            return [0.1, 0.2, 0.3]

        # Mock the cache to always miss
        with patch("knowledge.cache.get_cache") as mock_get_cache:
            mock_cache = AsyncMock()
            mock_cache.get.return_value = None
            mock_cache.set.return_value = True
            mock_get_cache.return_value = mock_cache

            result = await expensive_function("test")

            assert result == [0.1, 0.2, 0.3]
            assert call_count == 1
            mock_cache.get.assert_called_once()
            mock_cache.set.assert_called_once()


class TestGlobalCacheManagement:
    """Test global cache instance management."""

    async def test_get_cache_creates_instance(self):
        """Test get_cache creates a cache instance."""
        with patch("knowledge.cache._cache", None):
            with patch("knowledge.cache.RedisCache") as mock_redis_cache:
                mock_instance = MagicMock()
                mock_instance.connect = AsyncMock(return_value=False)
                mock_redis_cache.return_value = mock_instance

                cache = await get_cache()
                assert cache is mock_instance

    async def test_close_cache_cleans_up(self):
        """Test close_cache cleans up properly."""
        mock_cache = MagicMock()
        mock_cache.close = AsyncMock()

        with patch("knowledge.cache._cache", mock_cache):
            await close_cache()
            mock_cache.close.assert_called_once()
