"""YAML source file parser."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from knowledge_seeder.models import (
    Source,
    SourceFile,
    SourceLifecycleStatus,
    SourcePriority,
    SourceType,
    ValidationResult,
)


# YouTube URL patterns
YOUTUBE_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
    r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
]

# GitHub URL pattern
GITHUB_PATTERN = r"(?:https?://)?github\.com/([^/]+)/([^/]+)"

# arXiv URL pattern
ARXIV_PATTERN = r"(?:https?://)?arxiv\.org/abs/(\d+\.\d+)"


class SourceParser:
    """Parser for YAML source definition files."""

    def __init__(self) -> None:
        """Initialize parser."""
        self._youtube_patterns = [re.compile(p) for p in YOUTUBE_PATTERNS]
        self._github_pattern = re.compile(GITHUB_PATTERN)
        self._arxiv_pattern = re.compile(ARXIV_PATTERN)

    def parse_file(self, path: Path) -> SourceFile:
        """Parse a YAML source file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty or invalid YAML file: {path}")

        # Parse file-level settings
        namespace = data.get("namespace", "default")
        refresh_interval = data.get("refresh_interval", "30d")
        priority = SourcePriority(data.get("priority", "P2"))
        project = data.get("project")
        dependencies = data.get("dependencies", [])

        # Parse sources
        sources = []
        raw_sources = data.get("sources", [])

        for raw in raw_sources:
            source = self._parse_source(raw, namespace, priority)
            sources.append(source)

        return SourceFile(
            namespace=namespace,
            refresh_interval=refresh_interval,
            priority=priority,
            sources=sources,
            project=project,
            dependencies=dependencies,
        )

    def _parse_source(
        self,
        raw: dict,
        default_namespace: str,
        default_priority: SourcePriority,
    ) -> Source:
        """Parse a single source entry."""
        name = raw.get("name")
        url = raw.get("url")

        if not name:
            raise ValueError(f"Source missing 'name': {raw}")
        if not url:
            raise ValueError(f"Source '{name}' missing 'url'")

        # Detect source type
        source_type = self._detect_type(raw, url)

        # Parse lifecycle status
        status_raw = raw.get("status", "active")
        try:
            status = SourceLifecycleStatus(status_raw)
        except ValueError:
            status = SourceLifecycleStatus.ACTIVE

        # Build source
        return Source(
            name=name,
            url=url,
            source_type=source_type,
            tags=raw.get("tags", []),
            namespace=raw.get("namespace", default_namespace),
            priority=SourcePriority(raw.get("priority", default_priority.value)),
            crawl_depth=raw.get("crawl_depth", 1),
            metadata=raw.get("metadata", {}),
            placeholder=raw.get("placeholder", False),
            # Lifecycle fields
            status=status,
            deprecated_date=raw.get("deprecated_date"),
            replacement=raw.get("replacement"),
            note=raw.get("note"),
        )

    def _detect_type(self, raw: dict, url: str) -> SourceType:
        """Detect the type of a source from its URL or explicit type."""
        # Check for explicit type
        explicit_type = raw.get("type")
        if explicit_type:
            return SourceType(explicit_type)

        # Auto-detect from URL
        if self._is_youtube(url):
            return SourceType.YOUTUBE
        if self._is_github(url):
            return SourceType.GITHUB
        if self._is_arxiv(url):
            return SourceType.ARXIV
        if self._is_file(url):
            return SourceType.FILE

        return SourceType.URL

    def _is_youtube(self, url: str) -> bool:
        """Check if URL is a YouTube video."""
        return any(p.match(url) for p in self._youtube_patterns)

    def _is_github(self, url: str) -> bool:
        """Check if URL is a GitHub URL."""
        return bool(self._github_pattern.match(url))

    def _is_arxiv(self, url: str) -> bool:
        """Check if URL is an arXiv paper."""
        return bool(self._arxiv_pattern.match(url))

    def _is_file(self, url: str) -> bool:
        """Check if URL is a local file path."""
        return url.startswith("/") or url.startswith("~") or url.startswith("./")

    def parse_directory(self, directory: Path) -> list[SourceFile]:
        """Parse all YAML files in a directory."""
        source_files = []
        for path in sorted(directory.glob("*.yaml")):
            try:
                source_file = self.parse_file(path)
                source_files.append(source_file)
            except Exception as e:
                raise ValueError(f"Error parsing {path}: {e}") from e
        return source_files

    def validate_source(self, source: Source) -> ValidationResult:
        """Validate a single source."""
        warnings = []

        # Check for placeholder
        if source.placeholder:
            return ValidationResult(
                source_id=source.source_id,
                name=source.name,
                url=source.url,
                is_valid=False,
                error="Source is marked as placeholder - needs real URL",
            )

        # Check URL format
        if source.source_type == SourceType.URL:
            if not source.url.startswith(("http://", "https://")):
                warnings.append("URL should start with http:// or https://")

        # Check YouTube
        if source.source_type == SourceType.YOUTUBE:
            if not self._is_youtube(source.url):
                return ValidationResult(
                    source_id=source.source_id,
                    name=source.name,
                    url=source.url,
                    is_valid=False,
                    error="Invalid YouTube URL format",
                )

        # Check for empty tags
        if not source.tags:
            warnings.append("No tags specified")

        return ValidationResult(
            source_id=source.source_id,
            name=source.name,
            url=source.url,
            is_valid=True,
            warnings=warnings,
        )

    def validate_file(self, path: Path) -> list[ValidationResult]:
        """Validate all sources in a file."""
        source_file = self.parse_file(path)
        return [self.validate_source(s) for s in source_file.sources]

    def get_all_sources(
        self,
        paths: list[Path],
        include_inactive: bool = False,
    ) -> list[Source]:
        """Get all sources from multiple files.

        Args:
            paths: List of YAML source files to parse
            include_inactive: If True, include deprecated/disabled sources

        Returns:
            List of Source objects (filtered by is_active by default)
        """
        sources = []
        for path in paths:
            source_file = self.parse_file(path)
            for source in source_file.sources:
                if include_inactive or source.is_active:
                    sources.append(source)
        return sources

    def count_sources(self, paths: list[Path]) -> dict:
        """Count sources by namespace and type."""
        counts = {
            "by_namespace": {},
            "by_type": {},
            "by_status": {},
            "total": 0,
            "active": 0,
            "placeholders": 0,
            "deprecated": 0,
            "disabled": 0,
        }

        for path in paths:
            source_file = self.parse_file(path)
            for source in source_file.sources:
                # By namespace
                ns = source.namespace
                counts["by_namespace"][ns] = counts["by_namespace"].get(ns, 0) + 1

                # By type
                st = source.source_type.value
                counts["by_type"][st] = counts["by_type"].get(st, 0) + 1

                # By status
                status = source.status.value
                counts["by_status"][status] = counts["by_status"].get(status, 0) + 1

                # Total
                counts["total"] += 1

                # Active (will be synced)
                if source.is_active:
                    counts["active"] += 1

                # Placeholders
                if source.placeholder:
                    counts["placeholders"] += 1

                # Deprecated
                if source.status == SourceLifecycleStatus.DEPRECATED:
                    counts["deprecated"] += 1

                # Disabled
                if source.status == SourceLifecycleStatus.DISABLED:
                    counts["disabled"] += 1

        return counts
