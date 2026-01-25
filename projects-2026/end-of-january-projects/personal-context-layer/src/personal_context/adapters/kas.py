"""KAS (Knowledge Activation System) adapter for knowledge base queries."""

from datetime import datetime
from typing import Any

import httpx

from personal_context.adapters.base import AbstractContextAdapter
from personal_context.schema import ContextItem, ContextSource


class KASAdapter(AbstractContextAdapter):
    """Adapter for Knowledge Activation System HTTP API."""

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def source(self) -> ContextSource:
        return ContextSource.KAS

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def health_check(self) -> bool:
        """Check if KAS API is available."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.api_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def search(self, query: str, limit: int = 10) -> list[ContextItem]:
        """Search KAS knowledge base using hybrid search."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.api_url}/search",
                json={
                    "query": query,
                    "limit": limit,
                    "search_type": "hybrid",
                },
            )

            if response.status_code != 200:
                return []

            data = response.json()
            results = data.get("results", [])

            return [self._convert_result(r) for r in results]

        except Exception:
            return []

    async def get_recent(self, hours: int = 24, limit: int = 20) -> list[ContextItem]:
        """Get recently added/modified knowledge items."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.api_url}/items/recent",
                params={"hours": hours, "limit": limit},
            )

            if response.status_code != 200:
                # Fallback: search for recent items
                return await self._search_recent_fallback(hours, limit)

            data = response.json()
            items = data.get("items", [])

            return [self._convert_item(item) for item in items]

        except Exception:
            return []

    async def ask(self, question: str) -> dict[str, Any]:
        """Ask a question using KAS Q&A capability."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.api_url}/ask",
                json={"question": question},
            )

            if response.status_code != 200:
                return {"answer": None, "confidence": 0, "sources": []}

            return response.json()

        except Exception:
            return {"answer": None, "confidence": 0, "sources": []}

    async def get_item(self, item_id: str) -> ContextItem | None:
        """Get a specific knowledge item by ID."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.api_url}/items/{item_id}")

            if response.status_code != 200:
                return None

            return self._convert_item(response.json())

        except Exception:
            return None

    async def get_namespaces(self) -> list[str]:
        """Get list of available namespaces/categories."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.api_url}/namespaces")

            if response.status_code != 200:
                return []

            data = response.json()
            return data.get("namespaces", [])

        except Exception:
            return []

    async def search_in_namespace(
        self, query: str, namespace: str, limit: int = 10
    ) -> list[ContextItem]:
        """Search within a specific namespace."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.api_url}/search",
                json={
                    "query": query,
                    "limit": limit,
                    "namespace": namespace,
                    "search_type": "hybrid",
                },
            )

            if response.status_code != 200:
                return []

            data = response.json()
            results = data.get("results", [])

            return [self._convert_result(r) for r in results]

        except Exception:
            return []

    async def _search_recent_fallback(
        self, hours: int, limit: int
    ) -> list[ContextItem]:
        """Fallback method if /items/recent endpoint doesn't exist."""
        # Try to search with a broad query and sort by date
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.api_url}/search",
                json={
                    "query": "*",
                    "limit": limit,
                    "sort_by": "created_at",
                    "sort_order": "desc",
                },
            )

            if response.status_code != 200:
                return []

            data = response.json()
            results = data.get("results", [])

            return [self._convert_result(r) for r in results[:limit]]

        except Exception:
            return []

    def _convert_result(self, result: dict[str, Any]) -> ContextItem:
        """Convert KAS search result to ContextItem."""
        # Handle different response formats
        content = result.get("content", result.get("text", ""))
        title = result.get("title", result.get("name", content[:50]))
        item_id = result.get("id", result.get("_id", ""))

        # Parse timestamp
        timestamp = datetime.now()
        for ts_field in ["created_at", "timestamp", "date", "modified_at"]:
            if ts_field in result:
                try:
                    ts_val = result[ts_field]
                    if isinstance(ts_val, str):
                        timestamp = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                    break
                except Exception:
                    pass

        return ContextItem(
            id=f"kas:{item_id}",
            source=ContextSource.KAS,
            title=title,
            content=content[:500] if len(content) > 500 else content,
            url=result.get("url"),
            timestamp=timestamp,
            metadata={
                "namespace": result.get("namespace", result.get("category")),
                "score": result.get("score", result.get("relevance_score")),
                "source_type": result.get("source_type", result.get("type")),
            },
            relevance_score=result.get("score", 0.0),
        )

    def _convert_item(self, item: dict[str, Any]) -> ContextItem:
        """Convert KAS item to ContextItem."""
        return self._convert_result(item)

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
