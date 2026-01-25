"""Embedding service with provider abstraction.

Supports:
- Ollama (FREE, local) - default
- Voyage AI (PAID, best quality) - upgrade path
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Literal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from knowledge_engine.config import EmbeddingProvider, Settings, get_settings

logger = logging.getLogger(__name__)


class BaseEmbeddingService(ABC):
    """Abstract base for embedding services."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Get embedding dimensions."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get model name."""
        pass


class OllamaEmbeddingService(BaseEmbeddingService):
    """Ollama embedding service - FREE, local."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.ollama_base_url,
                timeout=60.0,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding using Ollama."""
        client = await self._get_client()
        response = await client.post(
            "/api/embeddings",
            json={
                "model": self._settings.ollama_embed_model,
                "prompt": text,
            },
        )
        response.raise_for_status()
        return response.json()["embedding"]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts (sequential for Ollama)."""
        embeddings = []
        for i, text in enumerate(texts):
            embedding = await self.embed_text(text)
            embeddings.append(embedding)
            if (i + 1) % 10 == 0:
                logger.debug("Embedded %d/%d texts", i + 1, len(texts))
        return embeddings

    @property
    def dimensions(self) -> int:
        return self._settings.ollama_embed_dimensions

    @property
    def model_name(self) -> str:
        return f"ollama/{self._settings.ollama_embed_model}"


class VoyageEmbeddingService(BaseEmbeddingService):
    """Voyage AI embedding service - PAID, best quality."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import voyageai

            api_key = (
                self._settings.voyage_api_key.get_secret_value()
                if self._settings.voyage_api_key
                else None
            )
            if not api_key:
                raise ValueError("VOYAGE_API_KEY required for Voyage embeddings")
            self._client = voyageai.AsyncClient(api_key=api_key)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def embed_text(
        self,
        text: str,
        input_type: Literal["document", "query"] = "document",
    ) -> list[float]:
        """Generate embedding using Voyage AI."""
        client = await self._get_client()
        result = await client.embed(
            texts=[text],
            model=self._settings.voyage_model,
            input_type=input_type,
        )
        return result.embeddings[0]

    async def embed_texts(
        self,
        texts: list[str],
        input_type: Literal["document", "query"] = "document",
    ) -> list[list[float]]:
        """Generate embeddings with automatic batching."""
        if not texts:
            return []

        client = await self._get_client()
        batch_size = self._settings.voyage_batch_size
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            result = await client.embed(
                texts=batch,
                model=self._settings.voyage_model,
                input_type=input_type,
            )
            all_embeddings.extend(result.embeddings)
            logger.debug("Embedded batch %d-%d of %d", i, i + len(batch), len(texts))

        return all_embeddings

    @property
    def dimensions(self) -> int:
        return self._settings.voyage_dimensions

    @property
    def model_name(self) -> str:
        return f"voyage/{self._settings.voyage_model}"


class EmbeddingService:
    """
    Unified embedding service with provider abstraction.

    Default: Ollama (FREE)
    Upgrade: Set EMBEDDING_PROVIDER=voyage and VOYAGE_API_KEY
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._provider: BaseEmbeddingService | None = None

    def _get_provider(self) -> BaseEmbeddingService:
        """Get or create the embedding provider."""
        if self._provider is None:
            if self._settings.embedding_provider == EmbeddingProvider.VOYAGE:
                logger.info("Using Voyage AI embeddings (PAID)")
                self._provider = VoyageEmbeddingService(self._settings)
            else:
                logger.info("Using Ollama embeddings (FREE)")
                self._provider = OllamaEmbeddingService(self._settings)
        return self._provider

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        return await self._get_provider().embed_text(text)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return await self._get_provider().embed_texts(texts)

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding optimized for query retrieval."""
        provider = self._get_provider()
        if isinstance(provider, VoyageEmbeddingService):
            return await provider.embed_text(query, input_type="query")
        return await provider.embed_text(query)

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """Generate embeddings optimized for document storage."""
        provider = self._get_provider()
        if isinstance(provider, VoyageEmbeddingService):
            return await provider.embed_texts(documents, input_type="document")
        return await provider.embed_texts(documents)

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions."""
        return self._get_provider().dimensions

    @property
    def model_name(self) -> str:
        """Get model name."""
        return self._get_provider().model_name
