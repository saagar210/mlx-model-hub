"""KAS (Knowledge Activation System) API adapter."""

from typing import Any

import httpx

from ..config import settings


class KASResult:
    """A search result from KAS."""

    def __init__(
        self,
        id: str,
        title: str,
        content: str,
        score: float,
        tags: list[str] | None = None,
        source: str = "kas",
    ):
        self.id = id
        self.title = title
        self.content = content
        self.score = score
        self.tags = tags or []
        self.source = source


class KASAnswer:
    """An answer from KAS Q&A."""

    def __init__(
        self,
        answer: str,
        sources: list[dict[str, Any]],
        confidence: float = 0.0,
    ):
        self.answer = answer
        self.sources = sources
        self.confidence = confidence


class KASAdapter:
    """Adapter for KAS API (localhost:8000)."""

    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        self.base_url = base_url or settings.kas_base_url
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

    async def search(self, query: str, limit: int = 5) -> list[KASResult]:
        """Search KAS knowledge base.

        Args:
            query: Search query.
            limit: Maximum number of results.

        Returns:
            List of KASResult objects.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/search",
                json={
                    "query": query,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(KASResult(
                    id=item.get("id", ""),
                    title=item.get("title", ""),
                    content=item.get("content", item.get("chunk", "")),
                    score=item.get("score", 0.0),
                    tags=item.get("tags", []),
                ))
            return results
        except Exception as e:
            # Return empty results on error
            return []

    async def ask(self, question: str) -> KASAnswer:
        """Ask a question to KAS.

        Args:
            question: The question to ask.

        Returns:
            KASAnswer with the response.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/ask",
                json={"question": question},
            )
            response.raise_for_status()
            data = response.json()

            return KASAnswer(
                answer=data.get("answer", ""),
                sources=data.get("sources", []),
                confidence=data.get("confidence", 0.0),
            )
        except Exception as e:
            return KASAnswer(
                answer=f"Error querying KAS: {e}",
                sources=[],
                confidence=0.0,
            )

    async def ingest(
        self,
        content: str,
        title: str,
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> str:
        """Ingest content into KAS.

        Args:
            content: The content to ingest.
            title: Title for the content.
            tags: Optional tags.
            source: Optional source identifier.

        Returns:
            ID of the ingested item.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/v1/ingest",
                json={
                    "content": content,
                    "title": title,
                    "tags": tags or [],
                    "source": source or "universal-context-engine",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("id", "")
        except Exception as e:
            raise RuntimeError(f"Failed to ingest to KAS: {e}") from e

    async def health(self) -> dict[str, Any]:
        """Check KAS health.

        Returns:
            Health status dictionary.
        """
        try:
            client = await self._get_client()
            response = await client.get("/health")
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "details": response.json() if response.text else {},
                }
            return {
                "status": "unhealthy",
                "error": f"HTTP {response.status_code}",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Default adapter instance
kas_adapter = KASAdapter()
