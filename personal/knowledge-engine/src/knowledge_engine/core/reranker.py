"""Reranking service with provider abstraction.

Supports:
- Ollama (FREE, local) - default
- Cohere (PAID, best quality) - upgrade path
- None (skip reranking)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from knowledge_engine.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """Result from reranking operation."""

    index: int
    relevance_score: float
    document: str


class OllamaReranker:
    """Ollama reranking service - FREE, local."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.ollama_base_url,
                timeout=120.0,  # Reranking can be slow
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        """Rerank documents using Ollama."""
        if not documents:
            return []

        client = await self._get_client()
        top_n = top_n or len(documents)

        # Use the rerank API if available (newer Ollama versions)
        # Fall back to embedding-based reranking otherwise
        try:
            response = await client.post(
                "/api/rerank",
                json={
                    "model": self._settings.ollama_rerank_model,
                    "query": query,
                    "documents": documents,
                    "top_n": top_n,
                },
            )
            response.raise_for_status()
            data = response.json()

            return [
                RerankResult(
                    index=r["index"],
                    relevance_score=r["relevance_score"],
                    document=documents[r["index"]],
                )
                for r in data["results"][:top_n]
            ]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Rerank API not available, fall back to simple scoring
                logger.warning("Ollama rerank API not available, using passthrough")
                return [
                    RerankResult(index=i, relevance_score=1.0 - (i * 0.01), document=doc)
                    for i, doc in enumerate(documents[:top_n])
                ]
            raise

    @property
    def model_name(self) -> str:
        return f"ollama/{self._settings.ollama_rerank_model}"


class CohereReranker:
    """Cohere reranking service - PAID, best quality."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import cohere

            api_key = (
                self._settings.cohere_api_key.get_secret_value()
                if self._settings.cohere_api_key
                else None
            )
            if not api_key:
                raise ValueError("COHERE_API_KEY required for Cohere reranking")
            self._client = cohere.AsyncClientV2(api_key=api_key)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        """Rerank documents using Cohere."""
        if not documents:
            return []

        client = await self._get_client()
        top_n = top_n or self._settings.cohere_rerank_top_n

        result = await client.rerank(
            model=self._settings.cohere_rerank_model,
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
            return_documents=True,
        )

        return [
            RerankResult(
                index=r.index,
                relevance_score=r.relevance_score,
                document=r.document.text if r.document else documents[r.index],
            )
            for r in result.results
        ]

    @property
    def model_name(self) -> str:
        return f"cohere/{self._settings.cohere_rerank_model}"


class RerankerService:
    """
    Unified reranking service with provider abstraction.

    Default: Ollama (FREE)
    Upgrade: Set RERANK_PROVIDER=cohere and COHERE_API_KEY
    Disable: Set RERANK_ENABLED=false
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._provider = None

    def _get_provider(self):
        """Get or create the reranking provider."""
        if self._provider is None:
            if not self._settings.rerank_enabled:
                logger.info("Reranking disabled")
                self._provider = None
            elif self._settings.rerank_provider == "cohere":
                logger.info("Using Cohere reranking (PAID)")
                self._provider = CohereReranker(self._settings)
            elif self._settings.rerank_provider == "ollama":
                logger.info("Using Ollama reranking (FREE)")
                self._provider = OllamaReranker(self._settings)
            else:
                logger.info("Reranking disabled")
                self._provider = None
        return self._provider

    @property
    def enabled(self) -> bool:
        """Check if reranking is enabled."""
        return self._settings.rerank_enabled and self._settings.rerank_provider != "none"

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to query."""
        provider = self._get_provider()
        if provider is None:
            # Return original order with decreasing scores
            return [
                RerankResult(index=i, relevance_score=1.0 - (i * 0.01), document=doc)
                for i, doc in enumerate(documents[: (top_n or len(documents))])
            ]
        return await provider.rerank(query, documents, top_n)

    async def rerank_with_metadata(
        self,
        query: str,
        items: list[dict],
        text_key: str = "content",
        top_n: int | None = None,
    ) -> list[dict]:
        """Rerank items preserving metadata."""
        if not items:
            return []

        documents = [item[text_key] for item in items]
        reranked = await self.rerank(query, documents, top_n=top_n)

        result = []
        for r in reranked:
            item = items[r.index].copy()
            item["rerank_score"] = r.relevance_score
            result.append(item)

        return result

    @property
    def model_name(self) -> str | None:
        """Get current model name."""
        provider = self._get_provider()
        return provider.model_name if provider else None
