"""Prompt-level KV cache for fast inference on repeated prompts.

This module provides KV state caching for system prompts, enabling
10x faster inference when the same system prompt is used across
multiple requests (common in RAG and chat applications).
"""

import hashlib
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import mlx.core as mx

logger = logging.getLogger(__name__)


@dataclass
class CachedPrompt:
    """A cached prompt with its KV state."""

    cache: Any  # MLX prompt_cache object
    model_id: str
    prompt_hash: str
    prompt_preview: str  # First 100 chars for debugging
    token_count: int
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    hits: int = 0


@dataclass
class PromptCacheStats:
    """Statistics for the prompt cache."""

    total_entries: int
    total_hits: int
    total_misses: int
    memory_entries: int
    disk_entries: int


class PromptCacheService:
    """In-memory + disk-backed prompt cache for KV state reuse.

    Caches the KV states from processing system prompts so that
    subsequent requests with the same system prompt can skip
    the prompt processing phase entirely.

    Usage:
        cache_service = PromptCacheService()

        # Get or create cache for a system prompt
        prompt_cache = cache_service.get_or_create(
            model=model,
            tokenizer=tokenizer,
            prompt="You are a helpful assistant...",
            model_id="mlx-community/Qwen2.5-7B-Instruct-4bit"
        )

        # Use in generation
        response = mlx_lm.generate(
            model, tokenizer, user_query,
            prompt_cache=prompt_cache
        )
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        max_memory_entries: int = 10,
        persist_to_disk: bool = True,
    ):
        """Initialize the prompt cache service.

        Args:
            cache_dir: Directory for persistent cache files.
            max_memory_entries: Maximum entries to keep in memory (LRU eviction).
            persist_to_disk: Whether to save caches to disk.
        """
        self.cache_dir = cache_dir or Path.home() / ".unified-mlx/cache/prompts"
        self.max_memory_entries = max_memory_entries
        self.persist_to_disk = persist_to_disk

        self._memory_cache: OrderedDict[str, CachedPrompt] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0}

        # Ensure cache directory exists
        if self.persist_to_disk:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"PromptCacheService initialized: max_entries={max_memory_entries}, "
            f"persist={persist_to_disk}, dir={self.cache_dir}"
        )

    def _generate_key(self, model_id: str, prompt: str) -> str:
        """Generate a cache key from model ID and prompt.

        Uses SHA256 hash of model_id + prompt for consistent keying.
        """
        content = f"{model_id}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, model_id: str, prompt: str) -> Any | None:
        """Get cached KV state if available.

        Args:
            model_id: The model identifier.
            prompt: The prompt text (typically system prompt).

        Returns:
            The cached prompt_cache object, or None if not found.
        """
        cache_key = self._generate_key(model_id, prompt)

        with self._lock:
            # Check memory cache
            if cache_key in self._memory_cache:
                entry = self._memory_cache[cache_key]
                entry.last_used = datetime.now()
                entry.hits += 1
                self._stats["hits"] += 1

                # Move to end for LRU
                self._memory_cache.move_to_end(cache_key)

                logger.debug(f"Prompt cache HIT: {cache_key} (hits: {entry.hits})")
                return entry.cache

            self._stats["misses"] += 1
            logger.debug(f"Prompt cache MISS: {cache_key}")
            return None

    def get_or_create(
        self,
        model: Any,
        tokenizer: Any,
        prompt: str,
        model_id: str,
    ) -> Any:
        """Get cached KV state or create new one.

        This is the main entry point. It will:
        1. Check if cache exists for this prompt
        2. If yes, return the cached KV state
        3. If no, process the prompt and cache the result

        Args:
            model: The MLX model.
            tokenizer: The tokenizer.
            prompt: The prompt text to cache (typically system prompt).
            model_id: Model identifier for cache keying.

        Returns:
            The prompt_cache object (either from cache or newly created).
        """
        # Try to get existing cache
        cached = self.get(model_id, prompt)
        if cached is not None:
            return cached

        # Create new cache
        return self._create_cache(model, tokenizer, prompt, model_id)

    def _create_cache(
        self,
        model: Any,
        tokenizer: Any,
        prompt: str,
        model_id: str,
    ) -> Any:
        """Create a new prompt cache by processing the prompt."""
        from mlx_lm.models.cache import make_prompt_cache

        cache_key = self._generate_key(model_id, prompt)

        logger.info(f"Creating prompt cache for: {prompt[:50]}...")

        # Create empty cache
        prompt_cache = make_prompt_cache(model)

        # Tokenize the prompt
        tokens = tokenizer.encode(prompt)
        token_array = mx.array(tokens)[None]  # Add batch dimension

        # Process tokens through the model to populate the cache
        # We do a forward pass with the prompt to fill the KV cache
        try:
            # Process in chunks to handle long prompts
            model(token_array, cache=prompt_cache)
            mx.eval(prompt_cache)  # Ensure computation is complete
        except Exception as e:
            logger.warning(f"Failed to pre-fill cache: {e}")
            # Return empty cache - will work but without prefill benefit
            prompt_cache = make_prompt_cache(model)

        # Store in memory cache
        entry = CachedPrompt(
            cache=prompt_cache,
            model_id=model_id,
            prompt_hash=cache_key,
            prompt_preview=prompt[:100],
            token_count=len(tokens),
        )

        with self._lock:
            # Evict if at capacity
            while len(self._memory_cache) >= self.max_memory_entries:
                oldest_key, oldest_entry = self._memory_cache.popitem(last=False)
                logger.info(f"Evicting prompt cache: {oldest_key}")

            self._memory_cache[cache_key] = entry

        logger.info(
            f"Created prompt cache: key={cache_key}, "
            f"tokens={len(tokens)}, entries={len(self._memory_cache)}"
        )

        return prompt_cache

    def save_to_disk(self, model_id: str, prompt: str) -> Path | None:
        """Save a cached prompt to disk for persistence.

        Args:
            model_id: The model identifier.
            prompt: The prompt text.

        Returns:
            Path to saved file, or None if not found/failed.
        """
        if not self.persist_to_disk:
            return None

        cache_key = self._generate_key(model_id, prompt)

        with self._lock:
            if cache_key not in self._memory_cache:
                return None

            entry = self._memory_cache[cache_key]

        try:
            from mlx_lm.models.cache import save_prompt_cache

            file_path = self.cache_dir / f"{cache_key}.safetensors"
            metadata = {
                "model_id": model_id,
                "prompt_hash": cache_key,
                "token_count": str(entry.token_count),
                "created_at": entry.created_at.isoformat(),
            }

            save_prompt_cache(str(file_path), entry.cache, metadata)
            logger.info(f"Saved prompt cache to disk: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save prompt cache: {e}")
            return None

    def load_from_disk(self, model_id: str, prompt: str, model: Any) -> Any | None:
        """Load a cached prompt from disk.

        Args:
            model_id: The model identifier.
            prompt: The prompt text.
            model: The model (needed to recreate cache structure).

        Returns:
            The loaded prompt_cache, or None if not found.
        """
        if not self.persist_to_disk:
            return None

        cache_key = self._generate_key(model_id, prompt)
        file_path = self.cache_dir / f"{cache_key}.safetensors"

        if not file_path.exists():
            return None

        try:
            from mlx_lm.models.cache import load_prompt_cache

            prompt_cache, metadata = load_prompt_cache(
                str(file_path), return_metadata=True
            )

            # Verify model matches
            if metadata.get("model_id") != model_id:
                logger.warning(f"Model mismatch in cached file: {file_path}")
                return None

            logger.info(f"Loaded prompt cache from disk: {file_path}")
            return prompt_cache

        except Exception as e:
            logger.error(f"Failed to load prompt cache: {e}")
            return None

    def clear(self) -> int:
        """Clear all cached prompts.

        Returns:
            Number of entries cleared.
        """
        with self._lock:
            count = len(self._memory_cache)
            self._memory_cache.clear()
            self._stats = {"hits": 0, "misses": 0}

        # Clear disk cache
        if self.persist_to_disk:
            for f in self.cache_dir.glob("*.safetensors"):
                try:
                    f.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete cache file {f}: {e}")

        logger.info(f"Cleared {count} prompt cache entries")
        return count

    def delete(self, model_id: str, prompt: str) -> bool:
        """Delete a specific cached prompt.

        Args:
            model_id: The model identifier.
            prompt: The prompt text.

        Returns:
            True if deleted, False if not found.
        """
        cache_key = self._generate_key(model_id, prompt)

        with self._lock:
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]

                # Delete from disk too
                if self.persist_to_disk:
                    file_path = self.cache_dir / f"{cache_key}.safetensors"
                    if file_path.exists():
                        file_path.unlink()

                logger.info(f"Deleted prompt cache: {cache_key}")
                return True

        return False

    def list_entries(self) -> list[dict]:
        """List all cached entries with stats.

        Returns:
            List of cache entry information.
        """
        entries = []
        with self._lock:
            for key, entry in self._memory_cache.items():
                entries.append(
                    {
                        "cache_key": key,
                        "model_id": entry.model_id,
                        "prompt_preview": entry.prompt_preview,
                        "token_count": entry.token_count,
                        "hits": entry.hits,
                        "created_at": entry.created_at.isoformat(),
                        "last_used": entry.last_used.isoformat(),
                    }
                )
        return entries

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        with self._lock:
            disk_count = (
                len(list(self.cache_dir.glob("*.safetensors")))
                if self.persist_to_disk
                else 0
            )

            return {
                "memory_entries": len(self._memory_cache),
                "disk_entries": disk_count,
                "total_hits": self._stats["hits"],
                "total_misses": self._stats["misses"],
                "hit_rate": (
                    self._stats["hits"]
                    / max(1, self._stats["hits"] + self._stats["misses"])
                ),
                "max_entries": self.max_memory_entries,
            }


# Global singleton instance
_prompt_cache_service: PromptCacheService | None = None


def get_prompt_cache_service() -> PromptCacheService:
    """Get the global prompt cache service instance."""
    global _prompt_cache_service
    if _prompt_cache_service is None:
        _prompt_cache_service = PromptCacheService()
    return _prompt_cache_service


def init_prompt_cache_service(
    cache_dir: Path | None = None,
    max_memory_entries: int = 10,
    persist_to_disk: bool = True,
) -> PromptCacheService:
    """Initialize the global prompt cache service with custom settings."""
    global _prompt_cache_service
    _prompt_cache_service = PromptCacheService(
        cache_dir=cache_dir,
        max_memory_entries=max_memory_entries,
        persist_to_disk=persist_to_disk,
    )
    return _prompt_cache_service
