"""Embeddings via Ollama with Redis caching."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass

import httpx

from knowledge.config import Settings, get_settings
from knowledge.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OllamaStatus:
    """Ollama health status."""

    healthy: bool
    models_loaded: list[str]
    error: str | None = None


class EmbeddingService:
    """Service for generating embeddings via Ollama."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.settings.ollama_url,
                timeout=httpx.Timeout(self.settings.ollama_timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def check_health(self) -> OllamaStatus:
        """Check if Ollama is running and required models are loaded."""
        try:
            client = await self._get_client()

            # Check if Ollama is running
            response = await client.get("/api/tags")
            response.raise_for_status()

            data = response.json()
            models = [m["name"] for m in data.get("models", [])]

            # Check if embedding model is available
            embedding_model = self.settings.embedding_model
            model_loaded = any(
                m.startswith(embedding_model) or embedding_model in m for m in models
            )

            if not model_loaded:
                return OllamaStatus(
                    healthy=False,
                    models_loaded=models,
                    error=f"Embedding model '{embedding_model}' not found. "
                    f"Run: ollama pull {embedding_model}",
                )

            return OllamaStatus(healthy=True, models_loaded=models)

        except httpx.ConnectError:
            return OllamaStatus(
                healthy=False,
                models_loaded=[],
                error="Cannot connect to Ollama. Is it running? Start with: ollama serve",
            )
        except Exception as e:
            return OllamaStatus(
                healthy=False,
                models_loaded=[],
                error=f"Ollama health check failed: {e}",
            )

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            768-dimensional embedding vector

        Raises:
            RuntimeError: If embedding fails
        """
        client = await self._get_client()

        try:
            response = await client.post(
                "/api/embeddings",
                json={
                    "model": self.settings.embedding_model,
                    "prompt": text,
                },
            )
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding")

            if embedding is None:
                raise RuntimeError(f"No embedding returned: {data}")

            return embedding

        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Ollama API error: {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.TimeoutException as e:
            raise RuntimeError(
                f"Embedding request timed out after {self.settings.ollama_timeout}s"
            ) from e

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 10,
        max_retries: int = 3,
        max_concurrent: int | None = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batches with rate limiting.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per batch
            max_retries: Number of retries per text on failure
            max_concurrent: Maximum concurrent requests (defaults to config)

        Returns:
            List of embedding vectors (same order as input)
        """
        results: list[list[float] | None] = [None] * len(texts)

        # Use config value if not explicitly set
        concurrent = max_concurrent or self.settings.embedding_max_concurrent

        # Rate limiting semaphore
        semaphore = asyncio.Semaphore(concurrent)

        async def embed_with_retry(index: int, text: str) -> None:
            """Embed single text with retry logic and rate limiting."""
            async with semaphore:  # Limit concurrent requests
                for attempt in range(max_retries):
                    try:
                        embedding = await self.embed_text(text)
                        results[index] = embedding
                        return
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise RuntimeError(
                                f"Failed to embed text at index {index} after {max_retries} attempts: {e}"
                            ) from e
                        # Exponential backoff
                        await asyncio.sleep(2**attempt)

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            tasks = [embed_with_retry(i + j, text) for j, text in enumerate(batch)]
            await asyncio.gather(*tasks)

        # Verify all embeddings were generated
        for i, result in enumerate(results):
            if result is None:
                raise RuntimeError(f"Missing embedding for text at index {i}")

        return results  # type: ignore


# Global service instance
_embedding_service: EmbeddingService | None = None


async def get_embedding_service() -> EmbeddingService:
    """Get or create global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


async def close_embedding_service() -> None:
    """Close global embedding service instance."""
    global _embedding_service
    if _embedding_service is not None:
        await _embedding_service.close()
        _embedding_service = None


async def embed_text(text: str, use_cache: bool = True) -> list[float]:
    """
    Embed text using global service with optional Redis caching.

    Args:
        text: Text to embed
        use_cache: Whether to use Redis cache (default True)

    Returns:
        768-dimensional embedding vector
    """
    # Import here to avoid circular dependency
    from knowledge.cache import CacheType, get_cache

    cache = await get_cache()

    # Create cache key from text hash
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:32]

    # Check cache first
    if use_cache and cache.is_connected:
        cached = await cache.get(CacheType.EMBEDDING, text_hash)
        if cached is not None:
            logger.debug("embedding_cache_hit", text_preview=text[:50])
            return cached

    # Generate embedding
    service = await get_embedding_service()
    embedding = await service.embed_text(text)

    # Cache the result
    if use_cache and cache.is_connected:
        await cache.set(CacheType.EMBEDDING, embedding, text_hash)
        logger.debug("embedding_cached", text_preview=text[:50])

    return embedding


async def embed_batch(texts: list[str], batch_size: int = 10) -> list[list[float]]:
    """Convenience function to embed batch using global service."""
    service = await get_embedding_service()
    return await service.embed_batch(texts, batch_size)


async def check_ollama_health() -> OllamaStatus:
    """Convenience function to check Ollama health using global service."""
    service = await get_embedding_service()
    return await service.check_health()
