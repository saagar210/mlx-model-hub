"""Knowledge Activation System (KAS) API Client.

Client for communicating with the KAS ingestion API.
"""

from __future__ import annotations

import logging
from typing import Any
from datetime import datetime, timezone

import httpx

from knowledge_seeder.config import get_settings

logger = logging.getLogger(__name__)


class KASClient:
    """Client for Knowledge Activation System API."""

    def __init__(self, base_url: str | None = None) -> None:
        """Initialize KAS client.

        Args:
            base_url: KAS API base URL (default from settings)
        """
        settings = get_settings()
        self.base_url = base_url or settings.api_base_url
        self.timeout = settings.api_timeout

    async def health(self) -> dict[str, Any]:
        """Check KAS health status.

        Returns:
            Health status response

        Raises:
            httpx.HTTPError: If health check fails
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{self.base_url}/api/v1/health")
            r.raise_for_status()
            return r.json()

    async def ingest_document(self, document: dict[str, Any]) -> dict[str, Any]:
        """Ingest a single document.

        Args:
            document: Document payload matching KAS schema

        Returns:
            Ingestion response with content_id and chunks_created
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                f"{self.base_url}/api/v1/ingest/document",
                json=document,
            )
            return r.json()

    async def ingest_batch(
        self,
        documents: list[dict[str, Any]],
        stop_on_error: bool = False,
    ) -> dict[str, Any]:
        """Ingest multiple documents in batch.

        Args:
            documents: List of document payloads (max 50)
            stop_on_error: Stop batch on first error

        Returns:
            Batch ingestion response with results per document
        """
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(
                f"{self.base_url}/api/v1/ingest/batch",
                json={
                    "documents": documents,
                    "stop_on_error": stop_on_error,
                },
            )
            return r.json()

    async def search(
        self,
        query: str,
        limit: int = 5,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Search ingested content.

        Args:
            query: Search query
            limit: Maximum results
            namespace: Optional namespace filter

        Returns:
            Search results
        """
        params: dict[str, Any] = {"q": query, "limit": limit}
        if namespace:
            params["namespace"] = namespace

        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{self.base_url}/api/v1/search",
                params=params,
            )
            return r.json()

    async def stats(self) -> dict[str, Any]:
        """Get ingestion statistics.

        Returns:
            Statistics including total_content and total_chunks
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{self.base_url}/api/v1/stats")
            return r.json()


def build_kas_payload(
    content: str,
    title: str,
    document_type: str,
    namespace: str,
    source_url: str,
    tags: list[str],
    source_id: str,
    source_type: str,
    priority: str,
    quality_score: float,
    quality_grade: str,
) -> dict[str, Any]:
    """Build a KAS-compliant document payload.

    Args:
        content: Document content
        title: Document title
        document_type: Type (markdown, text, youtube, arxiv, code)
        namespace: Target namespace
        source_url: Original source URL
        tags: Classification tags
        source_id: Seeder source ID
        source_type: Seeder source type
        priority: Priority level (P0-P4)
        quality_score: Quality score (0-100)
        quality_grade: Quality grade (A-F)

    Returns:
        KAS-compliant document payload
    """
    return {
        "content": content,
        "title": title,
        "document_type": document_type,
        "namespace": namespace,
        "metadata": {
            "source": source_url,
            "author": None,
            "created_at": None,
            "tags": tags,
            "language": "en",
            "custom": {
                "seeder_source_id": source_id,
                "seeder_source_type": source_type,
                "seeder_priority": priority,
                "seeder_quality_score": quality_score,
                "seeder_quality_grade": quality_grade,
                "seeder_extracted_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }
