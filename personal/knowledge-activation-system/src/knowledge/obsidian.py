"""Obsidian note creation and management."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from knowledge.config import Settings, get_settings


@dataclass
class NoteFrontmatter:
    """Obsidian note frontmatter data."""

    type: str
    title: str
    url: str | None = None
    tags: list[str] = field(default_factory=list)
    captured_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_yaml(self) -> str:
        """Convert to YAML frontmatter string."""
        data: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
        }

        if self.url:
            data["url"] = self.url

        if self.tags:
            data["tags"] = self.tags

        if self.captured_at:
            data["captured_at"] = self.captured_at.isoformat()

        if self.metadata:
            data["metadata"] = self.metadata

        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)


@dataclass
class ObsidianNote:
    """An Obsidian note with frontmatter and content."""

    frontmatter: NoteFrontmatter
    summary: str | None = None
    content: str = ""

    def to_markdown(self) -> str:
        """Convert to full markdown note."""
        parts = [
            "---",
            self.frontmatter.to_yaml().strip(),
            "---",
            "",
        ]

        if self.summary:
            parts.extend(
                [
                    "## Summary",
                    "",
                    self.summary,
                    "",
                ]
            )

        if self.content:
            parts.extend(
                [
                    "## Content",
                    "",
                    self.content,
                ]
            )

        return "\n".join(parts)


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    Sanitize a string for use as a filename.

    Args:
        name: Original name
        max_length: Maximum filename length

    Returns:
        Sanitized filename
    """
    # Remove or replace problematic characters
    # Obsidian doesn't like: \ / : * ? " < > | #
    sanitized = re.sub(r'[\\/:*?"<>|#]', "", name)

    # Replace multiple spaces with single space
    sanitized = re.sub(r"\s+", " ", sanitized)

    # Trim whitespace
    sanitized = sanitized.strip()

    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rsplit(" ", 1)[0]  # Try to break at word

    # Ensure not empty
    if not sanitized:
        sanitized = "untitled"

    return sanitized


def get_folder_for_type(content_type: str) -> str:
    """
    Get the subfolder name for a content type.

    Args:
        content_type: Content type (youtube, bookmark, file, note)

    Returns:
        Folder name
    """
    folders = {
        "youtube": "YouTube",
        "bookmark": "Bookmarks",
        "file": "Files",
        "note": "Notes",
    }
    return folders.get(content_type, "Other")


def create_note_path(
    title: str,
    content_type: str,
    settings: Settings | None = None,
) -> Path:
    """
    Create the full path for a new note.

    Args:
        title: Note title
        content_type: Content type
        settings: Optional settings override

    Returns:
        Full path to note file
    """
    settings = settings or get_settings()

    folder = get_folder_for_type(content_type)
    filename = sanitize_filename(title) + ".md"

    return settings.knowledge_dir / folder / filename


def ensure_note_directory(path: Path) -> None:
    """
    Ensure the directory for a note exists.

    Args:
        path: Full path to note file
    """
    path.parent.mkdir(parents=True, exist_ok=True)


def create_note(
    content_type: str,
    title: str,
    content: str,
    url: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    captured_at: datetime | None = None,
    settings: Settings | None = None,
) -> Path:
    """
    Create an Obsidian note.

    Args:
        content_type: Type of content (youtube, bookmark, file, note)
        title: Note title
        content: Main content
        url: Optional source URL
        summary: Optional summary
        tags: Optional tags
        metadata: Optional additional metadata
        captured_at: Optional capture timestamp
        settings: Optional settings override

    Returns:
        Path to created note
    """
    settings = settings or get_settings()

    # Create frontmatter
    frontmatter = NoteFrontmatter(
        type=content_type,
        title=title,
        url=url,
        tags=tags or [],
        captured_at=captured_at or datetime.now(),
        metadata=metadata or {},
    )

    # Create note
    note = ObsidianNote(
        frontmatter=frontmatter,
        summary=summary,
        content=content,
    )

    # Determine path
    path = create_note_path(title, content_type, settings)

    # Handle duplicate filenames
    path = handle_duplicate_path(path)

    # Ensure directory exists
    ensure_note_directory(path)

    # Write note
    path.write_text(note.to_markdown(), encoding="utf-8")

    return path


def handle_duplicate_path(path: Path) -> Path:
    """
    Handle duplicate filenames by adding a number suffix.

    Args:
        path: Original path

    Returns:
        Unique path
    """
    if not path.exists():
        return path

    # Add incrementing number
    base = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        new_path = parent / f"{base} ({counter}){suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def parse_frontmatter(path: Path) -> NoteFrontmatter | None:
    """
    Parse frontmatter from an existing note.

    Args:
        path: Path to note file

    Returns:
        Parsed frontmatter or None if invalid
    """
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")

    # Extract frontmatter
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    try:
        data = yaml.safe_load(match.group(1))
        if not isinstance(data, dict):
            return None

        # Parse captured_at if present
        captured_at = None
        if "captured_at" in data:
            try:
                captured_at = datetime.fromisoformat(data["captured_at"])
            except (ValueError, TypeError):
                pass

        return NoteFrontmatter(
            type=data.get("type", "note"),
            title=data.get("title", path.stem),
            url=data.get("url"),
            tags=data.get("tags", []),
            captured_at=captured_at,
            metadata=data.get("metadata", {}),
        )
    except yaml.YAMLError:
        return None


def update_frontmatter(
    path: Path,
    updates: dict[str, Any],
) -> bool:
    """
    Update frontmatter in an existing note.

    Args:
        path: Path to note file
        updates: Dictionary of fields to update

    Returns:
        True if successful, False otherwise
    """
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8")

    # Extract frontmatter
    match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if not match:
        return False

    try:
        data = yaml.safe_load(match.group(1))
        if not isinstance(data, dict):
            return False

        # Apply updates
        data.update(updates)

        # Rebuild frontmatter
        new_frontmatter = yaml.dump(
            data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )

        # Replace in content
        new_content = f"---\n{new_frontmatter.strip()}\n---\n{content[match.end() :]}"

        path.write_text(new_content, encoding="utf-8")
        return True

    except yaml.YAMLError:
        return False


def get_relative_path(path: Path, settings: Settings | None = None) -> str:
    """
    Get path relative to vault root.

    Args:
        path: Absolute path
        settings: Optional settings override

    Returns:
        Relative path string
    """
    settings = settings or get_settings()

    try:
        return str(path.relative_to(settings.vault_dir))
    except ValueError:
        return str(path)


def note_exists(title: str, content_type: str, settings: Settings | None = None) -> bool:
    """
    Check if a note with this title already exists.

    Args:
        title: Note title
        content_type: Content type
        settings: Optional settings override

    Returns:
        True if note exists
    """
    path = create_note_path(title, content_type, settings)
    return path.exists()
