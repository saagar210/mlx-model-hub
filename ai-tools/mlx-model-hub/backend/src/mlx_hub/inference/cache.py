"""LRU model cache for inference."""

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

import psutil

from mlx_hub.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CachedModel:
    """A model stored in the cache."""

    model_id: str
    model: Any
    tokenizer: Any
    adapter_path: str | None = None
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    estimated_memory_gb: float = 0.0

    def touch(self) -> None:
        """Update last used timestamp."""
        self.last_used = time.time()


class ModelCache:
    """Thread-safe LRU cache for loaded models.

    Manages memory by evicting least recently used models
    when memory pressure is detected.
    """

    def __init__(
        self,
        max_memory_gb: float | None = None,
        max_models: int = 3,
    ):
        """Initialize the model cache.

        Args:
            max_memory_gb: Maximum memory for cached models.
                          If None, uses settings.mlx_memory_limit_gb.
            max_models: Maximum number of models to cache.
        """
        settings = get_settings()
        self.max_memory_gb = max_memory_gb or settings.mlx_memory_limit_gb
        self.max_models = max_models

        self._cache: OrderedDict[str, CachedModel] = OrderedDict()
        self._lock = threading.RLock()
        self._total_memory_gb = 0.0

    def get(self, key: str) -> CachedModel | None:
        """Get a model from cache and update LRU order.

        Args:
            key: Cache key (typically model_id or model_id:adapter_path).

        Returns:
            CachedModel if found, None otherwise.
        """
        with self._lock:
            if key not in self._cache:
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            cached = self._cache[key]
            cached.touch()

            logger.debug(f"Cache hit: {key}")
            return cached

    def put(
        self,
        key: str,
        model: Any,
        tokenizer: Any,
        adapter_path: str | None = None,
        estimated_memory_gb: float = 0.0,
    ) -> CachedModel:
        """Add a model to the cache.

        Will evict LRU models if necessary to make room.

        Args:
            key: Cache key.
            model: The loaded MLX model.
            tokenizer: The tokenizer.
            adapter_path: Path to adapter weights if any.
            estimated_memory_gb: Estimated memory usage.

        Returns:
            The cached model entry.
        """
        with self._lock:
            # Check if already cached
            if key in self._cache:
                self._cache.move_to_end(key)
                cached = self._cache[key]
                cached.touch()
                return cached

            # Evict if necessary
            self._evict_if_needed(estimated_memory_gb)

            # Create cache entry
            cached = CachedModel(
                model_id=key,
                model=model,
                tokenizer=tokenizer,
                adapter_path=adapter_path,
                estimated_memory_gb=estimated_memory_gb,
            )

            self._cache[key] = cached
            self._total_memory_gb += estimated_memory_gb

            logger.info(
                f"Cached model: {key} "
                f"(~{estimated_memory_gb:.1f}GB, "
                f"total: {self._total_memory_gb:.1f}GB)"
            )

            return cached

    def remove(self, key: str) -> bool:
        """Remove a model from the cache.

        Args:
            key: Cache key to remove.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            if key not in self._cache:
                return False

            cached = self._cache.pop(key)
            self._total_memory_gb -= cached.estimated_memory_gb

            logger.info(f"Evicted model: {key}")
            return True

    def clear(self) -> None:
        """Clear all cached models."""
        with self._lock:
            self._cache.clear()
            self._total_memory_gb = 0.0
            logger.info("Cache cleared")

    def _evict_if_needed(self, needed_memory_gb: float) -> None:
        """Evict LRU models to make room for new model.

        Args:
            needed_memory_gb: Memory needed for new model.
        """
        # Check model count limit
        while len(self._cache) >= self.max_models:
            self._evict_lru()

        # Check memory limit
        while self._total_memory_gb + needed_memory_gb > self.max_memory_gb and self._cache:
            self._evict_lru()

        # Check system memory pressure
        available_gb = psutil.virtual_memory().available / (1024**3)
        while available_gb < needed_memory_gb * 1.5 and self._cache:
            self._evict_lru()
            available_gb = psutil.virtual_memory().available / (1024**3)

    def _evict_lru(self) -> None:
        """Evict the least recently used model."""
        if not self._cache:
            return

        # OrderedDict maintains insertion order, first item is LRU
        key, cached = self._cache.popitem(last=False)
        self._total_memory_gb -= cached.estimated_memory_gb

        logger.info(f"Evicted LRU model: {key} (freed ~{cached.estimated_memory_gb:.1f}GB)")

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        with self._lock:
            return {
                "cached_models": len(self._cache),
                "max_models": self.max_models,
                "total_memory_gb": self._total_memory_gb,
                "max_memory_gb": self.max_memory_gb,
                "models": list(self._cache.keys()),
            }

    def __len__(self) -> int:
        """Return number of cached models."""
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache."""
        with self._lock:
            return key in self._cache


# Global cache instance
_model_cache: ModelCache | None = None
_cache_lock = threading.Lock()


def get_model_cache() -> ModelCache:
    """Get the global model cache instance (singleton)."""
    global _model_cache
    with _cache_lock:
        if _model_cache is None:
            _model_cache = ModelCache()
        return _model_cache


def reset_model_cache() -> None:
    """Reset the global model cache (for testing)."""
    global _model_cache
    with _cache_lock:
        if _model_cache is not None:
            _model_cache.clear()
        _model_cache = None
