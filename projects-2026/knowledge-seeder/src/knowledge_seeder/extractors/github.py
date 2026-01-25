"""GitHub repository content extractor."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from knowledge_seeder.config import get_settings
from knowledge_seeder.extractors.base import BaseExtractor, ExtractionResult
from knowledge_seeder.models import SourceType

logger = logging.getLogger(__name__)

# GitHub URL patterns
GITHUB_REPO_PATTERN = re.compile(
    r"(?:https?://)?github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$"
)
GITHUB_FILE_PATTERN = re.compile(
    r"(?:https?://)?github\.com/([^/]+)/([^/]+)/(?:blob|tree)/([^/]+)/(.+)$"
)
GITHUB_RAW_PATTERN = re.compile(
    r"(?:https?://)?raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$"
)


class GitHubExtractor(BaseExtractor):
    """Extract content from GitHub repositories.

    Handles:
    - Repository root (fetches README)
    - Specific files (fetches raw content)
    - Tree/directory paths (fetches README in that directory)
    """

    # Files to try for README (in order of preference)
    README_FILES = [
        "README.md",
        "README.rst",
        "README.txt",
        "README",
        "readme.md",
        "Readme.md",
    ]

    # Default branch names to try
    DEFAULT_BRANCHES = ["main", "master"]

    def __init__(self) -> None:
        """Initialize GitHub extractor."""
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
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "application/vnd.github.v3.raw",
                },
            )
        return self._client

    def can_handle(self, url: str) -> bool:
        """Check if this is a GitHub URL."""
        return bool(
            GITHUB_REPO_PATTERN.match(url) or
            GITHUB_FILE_PATTERN.match(url) or
            GITHUB_RAW_PATTERN.match(url)
        )

    def _parse_github_url(self, url: str) -> dict[str, str | None]:
        """Parse GitHub URL into components."""
        # Try raw URL first
        match = GITHUB_RAW_PATTERN.match(url)
        if match:
            return {
                "owner": match.group(1),
                "repo": match.group(2),
                "branch": match.group(3),
                "path": match.group(4),
            }

        # Try file/blob URL
        match = GITHUB_FILE_PATTERN.match(url)
        if match:
            return {
                "owner": match.group(1),
                "repo": match.group(2),
                "branch": match.group(3),
                "path": match.group(4),
            }

        # Try repo URL
        match = GITHUB_REPO_PATTERN.match(url)
        if match:
            return {
                "owner": match.group(1),
                "repo": match.group(2),
                "branch": None,
                "path": None,
            }

        return {}

    async def extract(self, url: str) -> ExtractionResult:
        """Extract content from GitHub URL."""
        if not self.can_handle(url):
            raise ValueError(f"Invalid GitHub URL: {url}")

        parsed = self._parse_github_url(url)
        if not parsed:
            raise ValueError(f"Could not parse GitHub URL: {url}")

        owner = parsed["owner"]
        repo = parsed["repo"]
        branch = parsed["branch"]
        path = parsed["path"]

        logger.info("Fetching GitHub content: %s/%s", owner, repo)

        client = await self._get_client()

        # If specific file path, fetch it directly
        if path and not path.endswith("/"):
            content, actual_branch = await self._fetch_file(
                client, owner, repo, branch, path
            )
            title = f"{owner}/{repo}: {path}"
        else:
            # Fetch README
            content, actual_branch, readme_path = await self._fetch_readme(
                client, owner, repo, branch, path
            )
            title = f"{owner}/{repo}"
            path = readme_path

        if not content:
            raise ValueError(f"No content found for {owner}/{repo}")

        # Truncate if needed
        if len(content) > self._max_length:
            content = content[: self._max_length]
            logger.warning("Content truncated for %s/%s", owner, repo)

        metadata = {
            "owner": owner,
            "repo": repo,
            "branch": actual_branch,
            "path": path,
            "github_url": f"https://github.com/{owner}/{repo}",
        }

        return ExtractionResult(
            content=content,
            title=title,
            source_url=url,
            source_type=SourceType.GITHUB,
            metadata=metadata,
        )

    async def _fetch_file(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        branch: str | None,
        path: str,
    ) -> tuple[str, str]:
        """Fetch a specific file from GitHub."""
        branches = [branch] if branch else self.DEFAULT_BRANCHES

        for br in branches:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{br}/{path}"
            try:
                response = await client.get(raw_url)
                if response.status_code == 200:
                    return response.text, br
            except httpx.HTTPError:
                continue

        raise ValueError(f"Could not fetch {path} from {owner}/{repo}")

    async def _fetch_readme(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        branch: str | None,
        base_path: str | None,
    ) -> tuple[str, str, str]:
        """Fetch README from repository."""
        branches = [branch] if branch else self.DEFAULT_BRANCHES
        base = f"{base_path}/" if base_path else ""

        for br in branches:
            for readme in self.README_FILES:
                path = f"{base}{readme}"
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{br}/{path}"
                try:
                    response = await client.get(raw_url)
                    if response.status_code == 200:
                        return response.text, br, path
                except httpx.HTTPError:
                    continue

        raise ValueError(f"No README found in {owner}/{repo}")

    async def check_accessible(self, url: str) -> tuple[bool, str | None]:
        """Check if GitHub URL is accessible."""
        if not self.can_handle(url):
            return False, "Invalid GitHub URL"

        parsed = self._parse_github_url(url)
        if not parsed:
            return False, "Could not parse URL"

        client = await self._get_client()

        # Try to fetch the content
        try:
            owner = parsed["owner"]
            repo = parsed["repo"]

            # Check if repo exists via API
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            response = await client.get(api_url)

            if response.status_code == 404:
                return False, "Repository not found"
            if response.status_code == 403:
                return False, "Rate limited or access denied"
            if response.status_code == 200:
                return True, None

            return False, f"HTTP {response.status_code}"
        except httpx.HTTPError as e:
            return False, str(e)

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
