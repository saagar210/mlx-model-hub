"""URL content extractor using trafilatura."""

from __future__ import annotations

import logging
import re

import httpx
import trafilatura

from knowledge_seeder.config import get_settings
from knowledge_seeder.extractors.base import BaseExtractor, ExtractionResult
from knowledge_seeder.models import SourceType

logger = logging.getLogger(__name__)

# URL validation pattern
URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


class URLExtractor(BaseExtractor):
    """Extract content from web URLs using trafilatura."""

    def __init__(self) -> None:
        """Initialize URL extractor."""
        settings = get_settings()
        self._timeout = settings.extraction_timeout
        self._user_agent = settings.user_agent
        self._max_length = settings.max_content_length
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": self._user_agent},
            )
        return self._client

    def can_handle(self, url: str) -> bool:
        """Check if this is a valid HTTP(S) URL."""
        return bool(URL_PATTERN.match(url))

    async def extract(self, url: str) -> ExtractionResult:
        """Fetch and extract content from URL."""
        if not self.can_handle(url):
            raise ValueError(f"Invalid URL: {url}")

        logger.info("Fetching URL: %s", url)

        # Fetch HTML
        client = await self._get_client()
        try:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
        except httpx.HTTPError as e:
            logger.error("Failed to fetch %s: %s", url, e)
            raise ValueError(f"Failed to fetch URL: {e}") from e

        # Extract content with trafilatura
        logger.info("Extracting content from: %s", url)

        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=False,
            include_images=False,
            favor_recall=True,
            output_format="txt",
        )

        # Fallback extraction if first attempt fails
        if not content:
            content = trafilatura.extract(html) or ""

        # Truncate if too long
        if len(content) > self._max_length:
            content = content[: self._max_length]
            logger.warning("Content truncated to %d chars for %s", self._max_length, url)

        # Extract metadata
        metadata_obj = trafilatura.extract_metadata(html)
        title = None
        metadata = {}

        if metadata_obj:
            title = metadata_obj.title
            metadata = {
                "author": metadata_obj.author,
                "date": str(metadata_obj.date) if metadata_obj.date else None,
                "description": metadata_obj.description,
                "sitename": metadata_obj.sitename,
            }

        # Add URL info
        from urllib.parse import urlparse

        parsed = urlparse(url)
        metadata["domain"] = parsed.netloc
        metadata["path"] = parsed.path

        return ExtractionResult(
            content=content or "",
            title=title,
            source_url=url,
            source_type=SourceType.URL,
            metadata=metadata,
        )

    async def check_accessible(self, url: str) -> tuple[bool, str | None]:
        """Check if URL is accessible without full extraction."""
        if not self.can_handle(url):
            return False, "Invalid URL format"

        client = await self._get_client()
        try:
            response = await client.head(url, follow_redirects=True)
            if response.status_code < 400:
                return True, None
            return False, f"HTTP {response.status_code}"
        except httpx.HTTPError as e:
            return False, str(e)

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
