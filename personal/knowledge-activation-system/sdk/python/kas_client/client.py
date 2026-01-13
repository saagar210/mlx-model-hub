"""
KAS Python SDK Client Implementation

Provides both async (KASClient) and sync (KASClientSync) clients.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

import httpx


# =============================================================================
# Exceptions
# =============================================================================


class KASError(Exception):
    """Base exception for KAS SDK errors."""

    pass


class KASConnectionError(KASError):
    """Raised when connection to KAS API fails."""

    pass


class KASAPIError(KASError):
    """Raised when KAS API returns an error response."""

    def __init__(self, status_code: int, message: str, details: dict[str, Any] | None = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"KAS API error ({status_code}): {message}")


class KASValidationError(KASError):
    """Raised when request validation fails."""

    pass


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SearchResult:
    """A single search result from the knowledge base."""

    content_id: str
    title: str
    content_type: str
    score: float
    namespace: str | None = None
    chunk_text: str | None = None
    source_ref: str | None = None
    vector_similarity: float | None = None
    bm25_score: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchResult:
        return cls(
            content_id=data["content_id"],
            title=data["title"],
            content_type=data["content_type"],
            score=data["score"],
            namespace=data.get("namespace"),
            chunk_text=data.get("chunk_text"),
            source_ref=data.get("source_ref"),
            vector_similarity=data.get("vector_similarity"),
            bm25_score=data.get("bm25_score"),
        )


@dataclass
class SearchResponse:
    """Response from a search query."""

    results: list[SearchResult]
    query: str
    total: int
    source: str
    reranked: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SearchResponse:
        return cls(
            results=[SearchResult.from_dict(r) for r in data["results"]],
            query=data["query"],
            total=data["total"],
            source=data["source"],
            reranked=data["reranked"],
        )


@dataclass
class Citation:
    """A citation in an answer response."""

    index: int
    title: str
    content_type: str
    chunk_text: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Citation:
        return cls(
            index=data["index"],
            title=data["title"],
            content_type=data["content_type"],
            chunk_text=data["chunk_text"],
        )


@dataclass
class AskResponse:
    """Response from asking a question."""

    query: str
    answer: str
    confidence: str
    confidence_score: float
    citations: list[Citation]
    warning: str | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AskResponse:
        return cls(
            query=data["query"],
            answer=data["answer"],
            confidence=data["confidence"],
            confidence_score=data["confidence_score"],
            citations=[Citation.from_dict(c) for c in data.get("citations", [])],
            warning=data.get("warning"),
            error=data.get("error"),
        )


@dataclass
class IngestResponse:
    """Response from content ingestion."""

    content_id: str
    success: bool
    chunks_created: int
    message: str
    namespace: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IngestResponse:
        return cls(
            content_id=data["content_id"],
            success=data["success"],
            chunks_created=data["chunks_created"],
            message=data["message"],
            namespace=data["namespace"],
        )


@dataclass
class ServiceStatus:
    """Status of a KAS service component."""

    database: str
    embeddings: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServiceStatus:
        return cls(
            database=data["database"],
            embeddings=data["embeddings"],
        )


@dataclass
class Stats:
    """Knowledge base statistics."""

    total_content: int
    total_chunks: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Stats:
        return cls(
            total_content=data["total_content"],
            total_chunks=data["total_chunks"],
        )


@dataclass
class HealthResponse:
    """Health check response."""

    status: str
    version: str
    services: ServiceStatus
    stats: Stats

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HealthResponse:
        return cls(
            status=data["status"],
            version=data["version"],
            services=ServiceStatus.from_dict(data["services"]),
            stats=Stats.from_dict(data["stats"]),
        )


@dataclass
class ReviewItem:
    """An item due for review."""

    content_id: str
    title: str
    content_type: str
    preview_text: str | None
    is_new: bool
    is_learning: bool
    reps: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewItem:
        return cls(
            content_id=data["content_id"],
            title=data["title"],
            content_type=data["content_type"],
            preview_text=data.get("preview_text"),
            is_new=data["is_new"],
            is_learning=data["is_learning"],
            reps=data["reps"],
        )


@dataclass
class ReviewSubmitResponse:
    """Response from submitting a review."""

    success: bool
    next_review: str
    new_state: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewSubmitResponse:
        return cls(
            success=data["success"],
            next_review=data["next_review"],
            new_state=data["new_state"],
        )


@dataclass
class ReviewStats:
    """Review queue statistics."""

    due_now: int
    new: int
    learning: int
    review: int
    total_active: int
    reviews_today: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewStats:
        return cls(
            due_now=data["due_now"],
            new=data["new"],
            learning=data["learning"],
            review=data["review"],
            total_active=data["total_active"],
            reviews_today=data["reviews_today"],
        )


@dataclass
class Namespace:
    """A content namespace."""

    name: str
    document_count: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Namespace:
        return cls(
            name=data["name"],
            document_count=data["document_count"],
        )


@dataclass
class BatchSearchResult:
    """Result from a batch search query."""

    query: str
    results: list[SearchResult]
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BatchSearchResult:
        return cls(
            query=data["query"],
            results=[SearchResult.from_dict(r) for r in data.get("results", [])],
            error=data.get("error"),
        )


@dataclass
class BatchSearchResponse:
    """Response from batch search."""

    results: list[BatchSearchResult]
    total_queries: int
    successful: int
    failed: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BatchSearchResponse:
        return cls(
            results=[BatchSearchResult.from_dict(r) for r in data["results"]],
            total_queries=data["total_queries"],
            successful=data["successful"],
            failed=data["failed"],
        )


# =============================================================================
# Async Client
# =============================================================================


class KASClient:
    """
    Async client for the KAS API.

    Example:
        async with KASClient("http://localhost:8000") as client:
            results = await client.search("python patterns")
            print(results.total, "results found")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        api_key: str | None = None,
    ):
        """
        Initialize KAS client.

        Args:
            base_url: Base URL of the KAS API server
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> KASClient:
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API."""
        client = await self._ensure_client()

        try:
            response = await client.request(method, endpoint, **kwargs)
        except httpx.ConnectError as e:
            raise KASConnectionError(f"Failed to connect to KAS API: {e}") from e
        except httpx.TimeoutException as e:
            raise KASConnectionError(f"Request timed out: {e}") from e

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("detail", response.text)
            except Exception:
                message = response.text

            raise KASAPIError(response.status_code, message)

        return response.json()

    # -------------------------------------------------------------------------
    # Health & Status
    # -------------------------------------------------------------------------

    async def health(self) -> HealthResponse:
        """Check KAS API health status."""
        data = await self._request("GET", "/api/v1/health")
        return HealthResponse.from_dict(data)

    async def stats(self) -> Stats:
        """Get knowledge base statistics."""
        health = await self.health()
        return health.stats

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace: str | None = None,
        min_score: float | None = None,
        rerank: bool = False,
    ) -> SearchResponse:
        """
        Search the knowledge base.

        Args:
            query: Search query text
            limit: Maximum number of results
            namespace: Filter by namespace
            min_score: Minimum relevance score threshold
            rerank: Whether to apply reranking

        Returns:
            SearchResponse with results
        """
        params: dict[str, Any] = {"q": query, "limit": limit}
        if namespace:
            params["namespace"] = namespace
        if min_score is not None:
            params["min_score"] = min_score
        if rerank:
            params["rerank"] = "true"

        data = await self._request("GET", "/api/v1/search", params=params)
        return SearchResponse.from_dict(data)

    async def batch_search(
        self,
        queries: list[str],
        *,
        limit: int = 5,
        namespace: str | None = None,
    ) -> BatchSearchResponse:
        """
        Execute multiple search queries in a single request.

        Args:
            queries: List of search queries (max 10)
            limit: Results per query
            namespace: Filter by namespace

        Returns:
            BatchSearchResponse with all results
        """
        if len(queries) > 10:
            raise KASValidationError("Maximum 10 queries per batch")

        payload: dict[str, Any] = {"queries": queries, "limit": limit}
        if namespace:
            payload["namespace"] = namespace

        data = await self._request("POST", "/api/v1/batch/search", json=payload)
        return BatchSearchResponse.from_dict(data)

    # -------------------------------------------------------------------------
    # Q&A
    # -------------------------------------------------------------------------

    async def ask(
        self,
        query: str,
        *,
        context_limit: int = 5,
    ) -> AskResponse:
        """
        Ask a question and get a synthesized answer.

        Args:
            query: Question to ask
            context_limit: Number of context chunks to use

        Returns:
            AskResponse with answer and citations
        """
        data = await self._request(
            "POST",
            "/search/ask",
            json={"query": query, "limit": context_limit},
        )
        return AskResponse.from_dict(data)

    # -------------------------------------------------------------------------
    # Content Ingestion
    # -------------------------------------------------------------------------

    async def ingest(
        self,
        content: str,
        *,
        title: str,
        namespace: str = "default",
        document_type: Literal["markdown", "text", "code"] = "markdown",
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> IngestResponse:
        """
        Ingest content into the knowledge base.

        Args:
            content: Content text to ingest
            title: Content title
            namespace: Namespace to store under
            document_type: Type of document
            tags: Optional tags
            source: Source reference

        Returns:
            IngestResponse with content_id and chunk count
        """
        payload = {
            "content": content,
            "title": title,
            "namespace": namespace,
            "document_type": document_type,
            "metadata": {
                "tags": tags or [],
                "source": source or "kas-python-sdk",
                "captured_at": datetime.now().astimezone().isoformat(),
                "custom": {},
            },
        }

        data = await self._request("POST", "/api/v1/ingest/document", json=payload)
        return IngestResponse.from_dict(data)

    async def ingest_youtube(
        self,
        video_id: str,
        *,
        namespace: str = "youtube",
        tags: list[str] | None = None,
    ) -> IngestResponse:
        """
        Ingest a YouTube video transcript.

        Args:
            video_id: YouTube video ID
            namespace: Namespace to store under
            tags: Optional tags

        Returns:
            IngestResponse with content_id
        """
        payload = {
            "video_id": video_id,
            "namespace": namespace,
            "tags": tags or [],
        }

        data = await self._request("POST", "/api/v1/ingest/youtube", json=payload)
        return IngestResponse.from_dict(data)

    async def ingest_bookmark(
        self,
        url: str,
        *,
        title: str | None = None,
        namespace: str = "bookmarks",
        tags: list[str] | None = None,
    ) -> IngestResponse:
        """
        Ingest a web page as a bookmark.

        Args:
            url: URL to ingest
            title: Optional title override
            namespace: Namespace to store under
            tags: Optional tags

        Returns:
            IngestResponse with content_id
        """
        payload: dict[str, Any] = {
            "url": url,
            "namespace": namespace,
            "tags": tags or [],
        }
        if title:
            payload["title"] = title

        data = await self._request("POST", "/api/v1/ingest/bookmark", json=payload)
        return IngestResponse.from_dict(data)

    # -------------------------------------------------------------------------
    # Namespaces
    # -------------------------------------------------------------------------

    async def list_namespaces(self) -> list[Namespace]:
        """List all namespaces in the knowledge base."""
        data = await self._request("GET", "/api/v1/namespaces")
        return [Namespace.from_dict(ns) for ns in data["namespaces"]]

    # -------------------------------------------------------------------------
    # Review (Spaced Repetition)
    # -------------------------------------------------------------------------

    async def get_review_items(self, limit: int = 5) -> list[ReviewItem]:
        """
        Get items due for review.

        Args:
            limit: Maximum items to return

        Returns:
            List of ReviewItem objects
        """
        data = await self._request("GET", f"/api/v1/review/due?limit={limit}")
        return [ReviewItem.from_dict(item) for item in data["items"]]

    async def submit_review(
        self,
        content_id: str,
        rating: int,
    ) -> ReviewSubmitResponse:
        """
        Submit a review rating for content.

        Args:
            content_id: ID of content reviewed
            rating: Rating (1=Again, 2=Hard, 3=Good, 4=Easy)

        Returns:
            ReviewSubmitResponse with next review date
        """
        if not 1 <= rating <= 4:
            raise KASValidationError("Rating must be between 1 and 4")

        data = await self._request(
            "POST",
            "/api/v1/review/submit",
            json={"content_id": content_id, "rating": rating},
        )
        return ReviewSubmitResponse.from_dict(data)

    async def get_review_stats(self) -> ReviewStats:
        """Get review queue statistics."""
        data = await self._request("GET", "/api/v1/review/stats")
        return ReviewStats.from_dict(data)

    # -------------------------------------------------------------------------
    # Content Management
    # -------------------------------------------------------------------------

    async def delete_content(self, content_id: str) -> bool:
        """
        Delete content by ID.

        Args:
            content_id: ID of content to delete

        Returns:
            True if deleted successfully
        """
        await self._request("DELETE", f"/api/v1/content/{content_id}")
        return True

    async def batch_delete(self, content_ids: list[str]) -> dict[str, Any]:
        """
        Delete multiple content items.

        Args:
            content_ids: List of content IDs to delete (max 100)

        Returns:
            Dict with deleted count and any errors
        """
        if len(content_ids) > 100:
            raise KASValidationError("Maximum 100 items per batch delete")

        return await self._request(
            "DELETE",
            "/api/v1/batch/content",
            json={"content_ids": content_ids},
        )


# =============================================================================
# Sync Client Wrapper
# =============================================================================


class KASClientSync:
    """
    Synchronous wrapper for KASClient.

    Example:
        client = KASClientSync("http://localhost:8000")
        results = client.search("python patterns")
        print(results.total, "results found")
        client.close()
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        api_key: str | None = None,
    ):
        """
        Initialize sync KAS client.

        Args:
            base_url: Base URL of the KAS API server
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self._async_client = KASClient(base_url, timeout, api_key)
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    def _run(self, coro: Any) -> Any:
        loop = self._get_loop()
        return loop.run_until_complete(coro)

    def close(self) -> None:
        """Close the client."""
        self._run(self._async_client.close())
        if self._loop and not self._loop.is_closed():
            self._loop.close()
            self._loop = None

    def __enter__(self) -> KASClientSync:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # Proxy methods
    def health(self) -> HealthResponse:
        return self._run(self._async_client.health())

    def stats(self) -> Stats:
        return self._run(self._async_client.stats())

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace: str | None = None,
        min_score: float | None = None,
        rerank: bool = False,
    ) -> SearchResponse:
        return self._run(
            self._async_client.search(
                query,
                limit=limit,
                namespace=namespace,
                min_score=min_score,
                rerank=rerank,
            )
        )

    def batch_search(
        self,
        queries: list[str],
        *,
        limit: int = 5,
        namespace: str | None = None,
    ) -> BatchSearchResponse:
        return self._run(
            self._async_client.batch_search(queries, limit=limit, namespace=namespace)
        )

    def ask(self, query: str, *, context_limit: int = 5) -> AskResponse:
        return self._run(self._async_client.ask(query, context_limit=context_limit))

    def ingest(
        self,
        content: str,
        *,
        title: str,
        namespace: str = "default",
        document_type: Literal["markdown", "text", "code"] = "markdown",
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> IngestResponse:
        return self._run(
            self._async_client.ingest(
                content,
                title=title,
                namespace=namespace,
                document_type=document_type,
                tags=tags,
                source=source,
            )
        )

    def ingest_youtube(
        self,
        video_id: str,
        *,
        namespace: str = "youtube",
        tags: list[str] | None = None,
    ) -> IngestResponse:
        return self._run(
            self._async_client.ingest_youtube(video_id, namespace=namespace, tags=tags)
        )

    def ingest_bookmark(
        self,
        url: str,
        *,
        title: str | None = None,
        namespace: str = "bookmarks",
        tags: list[str] | None = None,
    ) -> IngestResponse:
        return self._run(
            self._async_client.ingest_bookmark(
                url, title=title, namespace=namespace, tags=tags
            )
        )

    def list_namespaces(self) -> list[Namespace]:
        return self._run(self._async_client.list_namespaces())

    def get_review_items(self, limit: int = 5) -> list[ReviewItem]:
        return self._run(self._async_client.get_review_items(limit))

    def submit_review(self, content_id: str, rating: int) -> ReviewSubmitResponse:
        return self._run(self._async_client.submit_review(content_id, rating))

    def get_review_stats(self) -> ReviewStats:
        return self._run(self._async_client.get_review_stats())

    def delete_content(self, content_id: str) -> bool:
        return self._run(self._async_client.delete_content(content_id))

    def batch_delete(self, content_ids: list[str]) -> dict[str, Any]:
        return self._run(self._async_client.batch_delete(content_ids))
