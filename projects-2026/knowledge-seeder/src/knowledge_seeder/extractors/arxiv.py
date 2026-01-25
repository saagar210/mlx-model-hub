"""arXiv paper extractor."""

from __future__ import annotations

import logging
import re
from typing import Any
from xml.etree import ElementTree

import httpx

from knowledge_seeder.config import get_settings
from knowledge_seeder.extractors.base import BaseExtractor, ExtractionResult
from knowledge_seeder.models import SourceType

logger = logging.getLogger(__name__)

# arXiv URL/ID patterns
ARXIV_PATTERNS = [
    re.compile(r"(?:https?://)?arxiv\.org/abs/(\d+\.\d+)(?:v\d+)?"),
    re.compile(r"(?:https?://)?arxiv\.org/pdf/(\d+\.\d+)(?:v\d+)?(?:\.pdf)?"),
    re.compile(r"^(\d+\.\d+)(?:v\d+)?$"),  # Just the ID
]

# arXiv API namespaces
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


class ArxivExtractor(BaseExtractor):
    """Extract metadata and abstract from arXiv papers.

    Uses the arXiv API to fetch paper metadata, abstract, and authors.
    Note: Full paper text requires PDF extraction which is not implemented here.
    """

    def __init__(self) -> None:
        """Initialize arXiv extractor."""
        settings = get_settings()
        self._timeout = settings.extraction_timeout
        self._user_agent = settings.user_agent
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent},
            )
        return self._client

    def can_handle(self, url: str) -> bool:
        """Check if this is an arXiv URL or ID."""
        return self._extract_arxiv_id(url) is not None

    def _extract_arxiv_id(self, url: str) -> str | None:
        """Extract arXiv ID from URL or string."""
        for pattern in ARXIV_PATTERNS:
            match = pattern.match(url)
            if match:
                return match.group(1)
        return None

    async def extract(self, url: str) -> ExtractionResult:
        """Extract paper metadata and abstract from arXiv."""
        arxiv_id = self._extract_arxiv_id(url)
        if not arxiv_id:
            raise ValueError(f"Could not extract arXiv ID from: {url}")

        logger.info("Fetching arXiv paper: %s", arxiv_id)

        client = await self._get_client()

        # Fetch from arXiv API
        api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"

        try:
            response = await client.get(api_url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch arXiv paper: {e}") from e

        # Parse XML response
        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError as e:
            raise ValueError(f"Failed to parse arXiv response: {e}") from e

        # Find the entry
        entry = root.find("atom:entry", ARXIV_NS)
        if entry is None:
            raise ValueError(f"Paper not found: {arxiv_id}")

        # Extract metadata
        title = self._get_text(entry, "atom:title")
        abstract = self._get_text(entry, "atom:summary")
        published = self._get_text(entry, "atom:published")
        updated = self._get_text(entry, "atom:updated")

        # Extract authors
        authors = []
        for author in entry.findall("atom:author", ARXIV_NS):
            name = self._get_text(author, "atom:name")
            if name:
                authors.append(name)

        # Extract categories
        categories = []
        for category in entry.findall("arxiv:primary_category", ARXIV_NS):
            term = category.get("term")
            if term:
                categories.append(term)
        for category in entry.findall("atom:category", ARXIV_NS):
            term = category.get("term")
            if term and term not in categories:
                categories.append(term)

        # Build structured content
        content = self._format_paper_content(
            title=title,
            authors=authors,
            abstract=abstract,
            arxiv_id=arxiv_id,
            categories=categories,
            published=published,
        )

        metadata = {
            "arxiv_id": arxiv_id,
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "authors": authors,
            "categories": categories,
            "published": published,
            "updated": updated,
        }

        return ExtractionResult(
            content=content,
            title=title,
            source_url=url,
            source_type=SourceType.ARXIV,
            metadata=metadata,
        )

    def _get_text(self, element: ElementTree.Element, path: str) -> str | None:
        """Get text content from an XML element."""
        child = element.find(path, ARXIV_NS)
        if child is not None and child.text:
            # Clean up whitespace
            return " ".join(child.text.split())
        return None

    def _format_paper_content(
        self,
        title: str | None,
        authors: list[str],
        abstract: str | None,
        arxiv_id: str,
        categories: list[str],
        published: str | None,
    ) -> str:
        """Format paper metadata as readable content."""
        lines = []

        if title:
            lines.append(f"# {title}")
            lines.append("")

        lines.append(f"**arXiv:** {arxiv_id}")

        if authors:
            lines.append(f"**Authors:** {', '.join(authors)}")

        if categories:
            lines.append(f"**Categories:** {', '.join(categories)}")

        if published:
            # Extract just the date part
            date = published.split("T")[0] if "T" in published else published
            lines.append(f"**Published:** {date}")

        if abstract:
            lines.append("")
            lines.append("## Abstract")
            lines.append("")
            lines.append(abstract)

        lines.append("")
        lines.append("---")
        lines.append(f"Full paper: https://arxiv.org/pdf/{arxiv_id}.pdf")

        return "\n".join(lines)

    async def check_accessible(self, url: str) -> tuple[bool, str | None]:
        """Check if arXiv paper is accessible."""
        arxiv_id = self._extract_arxiv_id(url)
        if not arxiv_id:
            return False, "Invalid arXiv URL"

        client = await self._get_client()

        try:
            api_url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
            response = await client.get(api_url)

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            # Check if paper exists
            root = ElementTree.fromstring(response.text)
            entry = root.find("atom:entry", ARXIV_NS)

            if entry is None:
                return False, "Paper not found"

            # Check if it's an error entry
            title = self._get_text(entry, "atom:title")
            if title and "Error" in title:
                return False, "Paper not found"

            return True, None

        except Exception as e:
            return False, str(e)

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
