"""
Embedding Service - Generate embeddings via Ollama.

Uses Nomic Embed Text v1.5 by default for 768-dimensional embeddings.
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Any

import httpx

from sia.config import SIAConfig, get_config


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    embedding: list[float]
    model: str
    dimensions: int
    latency_ms: int
    cached: bool = False


class EmbeddingService:
    """
    Generate embeddings using Ollama.

    Usage:
        service = EmbeddingService()
        result = await service.embed("Hello world")
        print(result.embedding)  # 768-dimensional vector
    """

    def __init__(self, config: SIAConfig | None = None):
        self.config = config or get_config()
        self._cache: dict[str, list[float]] = {}
        self._client = httpx.AsyncClient(
            base_url=self.config.ollama.base_url,
            timeout=60.0,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()

    async def embed(
        self,
        text: str,
        model: str | None = None,
        use_cache: bool = True,
    ) -> EmbeddingResult:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            model: Model to use (default: nomic-embed-text:v1.5)
            use_cache: Whether to use/update cache

        Returns:
            EmbeddingResult with embedding vector
        """
        model = model or self.config.embedding.model
        cache_key = self._cache_key(text)

        # Check cache
        if use_cache and cache_key in self._cache:
            return EmbeddingResult(
                embedding=self._cache[cache_key],
                model=model,
                dimensions=len(self._cache[cache_key]),
                latency_ms=0,
                cached=True,
            )

        start_time = time.time()

        response = await self._client.post(
            "/api/embeddings",
            json={
                "model": model,
                "prompt": text,
            },
        )
        response.raise_for_status()

        data = response.json()
        embedding = data["embedding"]
        latency_ms = int((time.time() - start_time) * 1000)

        # Update cache
        if use_cache:
            self._cache[cache_key] = embedding

        return EmbeddingResult(
            embedding=embedding,
            model=model,
            dimensions=len(embedding),
            latency_ms=latency_ms,
            cached=False,
        )

    async def embed_batch(
        self,
        texts: list[str],
        model: str | None = None,
        use_cache: bool = True,
    ) -> list[EmbeddingResult]:
        """
        Generate embeddings for multiple texts.

        Note: Ollama doesn't support batch embeddings natively,
        so this makes sequential calls (with caching).

        Args:
            texts: List of texts to embed
            model: Model to use
            use_cache: Whether to use/update cache

        Returns:
            List of EmbeddingResults
        """
        results = []
        for text in texts:
            result = await self.embed(text, model=model, use_cache=use_cache)
            results.append(result)
        return results

    async def embed_documents(
        self,
        documents: list[dict[str, Any]],
        text_field: str = "content",
        model: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Add embeddings to a list of documents.

        Args:
            documents: List of documents (dicts)
            text_field: Field name containing text to embed
            model: Model to use

        Returns:
            Documents with 'embedding' field added
        """
        results = []
        for doc in documents:
            text = doc.get(text_field, "")
            if text:
                result = await self.embed(text, model=model)
                doc["embedding"] = result.embedding
                doc["embedding_model"] = result.model
            results.append(doc)
        return results

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    async def health_check(self) -> dict[str, Any]:
        """Check embedding service health."""
        try:
            result = await self.embed("test", use_cache=False)
            return {
                "status": "healthy",
                "model": result.model,
                "dimensions": result.dimensions,
                "latency_ms": result.latency_ms,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Convenience function
async def embed(text: str, **kwargs: Any) -> list[float]:
    """Convenience function to get embedding vector."""
    service = EmbeddingService()
    try:
        result = await service.embed(text, **kwargs)
        return result.embedding
    finally:
        await service.close()
