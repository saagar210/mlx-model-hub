"""Ollama embedding client for Universal Context Engine."""

import httpx

from .config import settings


class OllamaEmbeddingClient:
    """Client for generating embeddings using Ollama."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_embed_model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        client = await self._get_client()
        response = await client.post(
            "/api/embeddings",
            json={
                "model": self.model,
                "prompt": text,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        # Ollama doesn't have native batch support, so we process sequentially
        embeddings = []
        for text in texts:
            embedding = await self.embed(text)
            embeddings.append(embedding)
        return embeddings

    async def health_check(self) -> bool:
        """Check if Ollama is healthy and the model is available."""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            if response.status_code != 200:
                return False

            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            # Check if our model is available (handle both full and short names)
            return any(self.model in m or m in self.model for m in models)
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class OllamaGenerateClient:
    """Client for text generation using Ollama."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_chat_model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The prompt to generate from.
            system: Optional system prompt.

        Returns:
            Generated text response.
        """
        client = await self._get_client()

        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        response = await client.post("/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["response"]

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Default clients
embedding_client = OllamaEmbeddingClient()
generate_client = OllamaGenerateClient()
