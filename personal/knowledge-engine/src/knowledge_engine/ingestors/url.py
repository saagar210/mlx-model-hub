"""URL content ingestor using trafilatura."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import httpx
import trafilatura

from knowledge_engine.ingestors.base import BaseIngestor, IngestResult

logger = logging.getLogger(__name__)

# URL pattern for validation
URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
    r'localhost|'  # localhost
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP address
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE
)


class URLIngestor(BaseIngestor):
    """
    Ingest content from web URLs.

    Uses trafilatura for intelligent content extraction,
    which handles article text, metadata, and removes boilerplate.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; KnowledgeEngine/1.0; +https://github.com/knowledge-engine)"
                }
            )
        return self._client

    def can_handle(self, source: str) -> bool:
        """Check if source is a valid URL."""
        return bool(URL_PATTERN.match(source))

    async def ingest(self, source: str) -> IngestResult:
        """
        Fetch and extract content from a URL.

        Uses trafilatura for intelligent content extraction.
        """
        if not self.can_handle(source):
            raise ValueError(f"Invalid URL: {source}")

        logger.info("Fetching URL: %s", source)

        try:
            client = await self._get_client()
            response = await client.get(source)
            response.raise_for_status()
            html = response.text
        except httpx.HTTPError as e:
            logger.error("Failed to fetch URL %s: %s", source, e)
            raise ValueError(f"Failed to fetch URL: {e}")

        logger.info("Extracting content from URL: %s", source)

        # Extract content using trafilatura
        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=False,
            include_images=False,
            favor_recall=True,
            output_format="txt",
        )

        if not content:
            # Fallback to basic extraction
            content = trafilatura.extract(html) or ""

        # Extract metadata
        metadata = trafilatura.extract_metadata(html)

        title = None
        if metadata:
            title = metadata.title

        parsed = urlparse(source)
        domain = parsed.netloc

        return IngestResult(
            content=content or "",
            title=title,
            source=source,
            source_type="url",
            metadata={
                "domain": domain,
                "url": source,
                "author": metadata.author if metadata else None,
                "date": str(metadata.date) if metadata and metadata.date else None,
                "description": metadata.description if metadata else None,
            }
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
