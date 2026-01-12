"""Reranking using Ollama models."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from knowledge.config import get_settings
from knowledge.search import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class RankedResult:
    """Search result with reranking score."""

    result: SearchResult
    rerank_score: float
    original_rank: int

    @property
    def title(self) -> str:
        return self.result.title

    @property
    def content_type(self) -> str:
        return self.result.content_type

    @property
    def chunk_text(self) -> str | None:
        return self.result.chunk_text


class Reranker:
    """Reranker using Ollama embedding model for cross-encoder style scoring."""

    def __init__(
        self,
        model: str | None = None,
        ollama_url: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize reranker.

        Note: mxbai-rerank models require special handling in Ollama.
        For now, we use a simplified approach with embedding similarity.

        Args:
            model: Rerank model name
            ollama_url: Ollama API URL
            timeout: Request timeout
        """
        settings = get_settings()
        self.model = model or settings.rerank_model
        self.ollama_url = ollama_url or settings.ollama_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Get embedding for text using Ollama."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.ollama_url}/api/embed",
                json={
                    "model": "nomic-embed-text",  # Use embedding model
                    "input": text,
                },
            )

            if response.status_code != 200:
                return None

            data = response.json()
            embeddings = data.get("embeddings", [])
            if embeddings:
                return embeddings[0]
            return None

        except Exception:
            return None

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def _get_embeddings_batch(
        self,
        texts: list[str],
        max_concurrent: int = 5,
    ) -> list[list[float] | None]:
        """
        Get embeddings for multiple texts with rate limiting.

        Args:
            texts: List of texts to embed
            max_concurrent: Maximum concurrent requests

        Returns:
            List of embeddings (None for failures)
        """
        results: list[list[float] | None] = [None] * len(texts)
        semaphore = asyncio.Semaphore(max_concurrent)

        async def embed_one(index: int, text: str) -> None:
            async with semaphore:
                try:
                    embedding = await self._get_embedding(text)
                    results[index] = embedding
                except Exception as e:
                    logger.warning(f"Failed to embed text at index {index}: {e}")
                    results[index] = None

        tasks = [embed_one(i, text) for i, text in enumerate(texts)]
        await asyncio.gather(*tasks)

        return results

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int | None = None,
    ) -> list[RankedResult]:
        """
        Rerank search results based on query relevance.

        Uses batch embedding with rate limiting for efficiency.

        Args:
            query: Search query
            results: List of search results to rerank
            top_k: Number of top results to return (None for all)

        Returns:
            List of RankedResult sorted by rerank score
        """
        if not results:
            return []

        # Get query embedding
        query_embedding = await self._get_embedding(query)
        if query_embedding is None:
            logger.warning("Failed to get query embedding, falling back to original ranking")
            return [
                RankedResult(
                    result=r,
                    rerank_score=r.score,
                    original_rank=i + 1,
                )
                for i, r in enumerate(results)
            ]

        # Batch embed all result texts
        texts = [(r.chunk_text or r.title)[:1000] for r in results]
        text_embeddings = await self._get_embeddings_batch(texts)

        ranked = []
        for i, (result, text_embedding) in enumerate(zip(results, text_embeddings, strict=True)):
            if text_embedding is not None:
                score = self._cosine_similarity(query_embedding, text_embedding)
            else:
                # Use original score if embedding fails
                score = result.score

            ranked.append(
                RankedResult(
                    result=result,
                    rerank_score=score,
                    original_rank=i + 1,
                )
            )

        # Sort by rerank score descending
        ranked.sort(key=lambda x: x.rerank_score, reverse=True)

        # Apply top_k if specified
        if top_k is not None:
            ranked = ranked[:top_k]

        return ranked


# Global reranker instance
_reranker: Reranker | None = None


async def get_reranker() -> Reranker:
    """Get or create global reranker instance."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


async def close_reranker() -> None:
    """Close global reranker."""
    global _reranker
    if _reranker is not None:
        await _reranker.close()
        _reranker = None


async def rerank_results(
    query: str,
    results: list[SearchResult],
    top_k: int | None = None,
) -> list[RankedResult]:
    """
    Rerank search results.

    Args:
        query: Search query
        results: Search results to rerank
        top_k: Number of results to return

    Returns:
        Reranked results
    """
    reranker = await get_reranker()
    return await reranker.rerank(query, results, top_k)
