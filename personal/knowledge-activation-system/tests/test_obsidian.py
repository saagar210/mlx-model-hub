"""Tests for Obsidian note management."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from knowledge.config import Settings
from knowledge.obsidian import (
    NoteFrontmatter,
    ObsidianNote,
    create_note,
    create_note_path,
    get_folder_for_type,
    get_relative_path,
    handle_duplicate_path,
    note_exists,
    parse_frontmatter,
    sanitize_filename,
    update_frontmatter,
)


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_basic_sanitization(self):
        """Test basic filename sanitization."""
        result = sanitize_filename("Normal Title")
        assert result == "Normal Title"

    def test_removes_special_chars(self):
        """Test removal of special characters."""
        result = sanitize_filename('Title: With "Special" <chars>')
        assert ":" not in result
        assert '"' not in result
        assert "<" not in result
        assert ">" not in result

    def test_truncates_long_names(self):
        """Test truncation of long names."""
        long_name = "A" * 150
        result = sanitize_filename(long_name, max_length=100)
        assert len(result) <= 100

    def test_handles_empty_after_sanitization(self):
        """Test handling of empty result."""
        result = sanitize_filename(':"<>|')
        assert result == "untitled"

    def test_normalizes_whitespace(self):
        """Test whitespace normalization."""
        result = sanitize_filename("Multiple   spaces   here")
        assert "  " not in result


class TestGetFolderForType:
    """Tests for folder selection by content type."""

    def test_youtube_folder(self):
        """Test YouTube folder."""
        assert get_folder_for_type("youtube") == "YouTube"

    def test_bookmark_folder(self):
        """Test bookmark folder."""
        assert get_folder_for_type("bookmark") == "Bookmarks"

    def test_file_folder(self):
        """Test file folder."""
        assert get_folder_for_type("file") == "Files"

    def test_note_folder(self):
        """Test note folder."""
        assert get_folder_for_type("note") == "Notes"

    def test_unknown_folder(self):
        """Test unknown type defaults to Other."""
        assert get_folder_for_type("unknown") == "Other"


class TestNoteFrontmatter:
    """Tests for NoteFrontmatter dataclass."""

    def test_to_yaml_basic(self):
        """Test basic YAML conversion."""
        frontmatter = NoteFrontmatter(
            type="youtube",
            title="Test Video",
        )

        yaml_str = frontmatter.to_yaml()

        assert "type: youtube" in yaml_str
        assert "title: Test Video" in yaml_str

    def test_to_yaml_with_url(self):
        """Test YAML with URL."""
        frontmatter = NoteFrontmatter(
            type="bookmark",
            title="Test Page",
            url="https://example.com",
        )

        yaml_str = frontmatter.to_yaml()

        assert "url: https://example.com" in yaml_str

    def test_to_yaml_with_tags(self):
        """Test YAML with tags."""
        frontmatter = NoteFrontmatter(
            type="note",
            title="Test Note",
            tags=["tag1", "tag2"],
        )

        yaml_str = frontmatter.to_yaml()

        assert "tags:" in yaml_str
        assert "tag1" in yaml_str

    def test_to_yaml_with_metadata(self):
        """Test YAML with metadata."""
        frontmatter = NoteFrontmatter(
            type="youtube",
            title="Test",
            metadata={"channel": "Test Channel", "duration": 300},
        )

        yaml_str = frontmatter.to_yaml()

        assert "metadata:" in yaml_str
        assert "channel:" in yaml_str


class TestObsidianNote:
    """Tests for ObsidianNote dataclass."""

    def test_to_markdown_basic(self):
        """Test basic markdown conversion."""
        frontmatter = NoteFrontmatter(type="note", title="Test")
        note = ObsidianNote(
            frontmatter=frontmatter,
            content="Main content here.",
        )

        md = note.to_markdown()

        assert md.startswith("---")
        assert "## Content" in md
        assert "Main content here." in md

    def test_to_markdown_with_summary(self):
        """Test markdown with summary."""
        frontmatter = NoteFrontmatter(type="note", title="Test")
        note = ObsidianNote(
            frontmatter=frontmatter,
            summary="This is a summary.",
            content="Main content.",
        )

        md = note.to_markdown()

        assert "## Summary" in md
        assert "This is a summary." in md


class TestHandleDuplicatePath:
    """Tests for duplicate path handling."""

    def test_no_duplicate(self, tmp_path: Path):
        """Test when no duplicate exists."""
        path = tmp_path / "test.md"
        result = handle_duplicate_path(path)

        assert result == path

    def test_with_duplicate(self, tmp_path: Path):
        """Test when duplicate exists."""
        path = tmp_path / "test.md"
        path.touch()  # Create the file

        result = handle_duplicate_path(path)

        assert result == tmp_path / "test (1).md"

    def test_multiple_duplicates(self, tmp_path: Path):
        """Test with multiple duplicates."""
        path = tmp_path / "test.md"
        path.touch()
        (tmp_path / "test (1).md").touch()
        (tmp_path / "test (2).md").touch()

        result = handle_duplicate_path(path)

        assert result == tmp_path / "test (3).md"


class TestCreateNote:
    """Tests for note creation."""

    def test_creates_note_file(self, tmp_path: Path):
        """Test that note file is created."""
        settings = Settings(vault_path=str(tmp_path), knowledge_folder="Knowledge")

        path = create_note(
            content_type="note",
            title="Test Note",
            content="Some content",
            settings=settings,
        )

        assert path.exists()
        assert path.suffix == ".md"

    def test_creates_correct_folder(self, tmp_path: Path):
        """Test that correct folder is created."""
        settings = Settings(vault_path=str(tmp_path), knowledge_folder="Knowledge")

        path = create_note(
            content_type="youtube",
            title="Test Video",
            content="Transcript",
            settings=settings,
        )

        assert "YouTube" in str(path)

    def test_note_content_is_correct(self, tmp_path: Path):
        """Test that note content is correct."""
        settings = Settings(vault_path=str(tmp_path), knowledge_folder="Knowledge")

        path = create_note(
            content_type="bookmark",
            title="Test Page",
            content="Page content",
            url="https://example.com",
            settings=settings,
        )

        content = path.read_text()

        assert "---" in content  # Frontmatter
        assert "type: bookmark" in content
        assert "Page content" in content


class TestParseFrontmatter:
    """Tests for frontmatter parsing."""

    def test_parse_valid_frontmatter(self, tmp_path: Path):
        """Test parsing valid frontmatter."""
        note_path = tmp_path / "test.md"
        note_path.write_text("""---
type: youtube
title: Test Video
url: https://youtube.com/watch?v=test
tags:
  - tag1
  - tag2
---

Content here.
""")

        result = parse_frontmatter(note_path)

        assert result is not None
        assert result.type == "youtube"
        assert result.title == "Test Video"
        assert result.url == "https://youtube.com/watch?v=test"
        assert "tag1" in result.tags

    def test_parse_missing_frontmatter(self, tmp_path: Path):
        """Test parsing file without frontmatter."""
        note_path = tmp_path / "test.md"
        note_path.write_text("Just content, no frontmatter.")

        result = parse_frontmatter(note_path)

        assert result is None

    def test_parse_nonexistent_file(self, tmp_path: Path):
        """Test parsing nonexistent file."""
        note_path = tmp_path / "nonexistent.md"

        result = parse_frontmatter(note_path)

        assert result is None


class TestUpdateFrontmatter:
    """Tests for frontmatter updating."""

    def test_update_existing_field(self, tmp_path: Path):
        """Test updating existing field."""
        note_path = tmp_path / "test.md"
        note_path.write_text("""---
type: note
title: Old Title
---

Content.
""")

        result = update_frontmatter(note_path, {"title": "New Title"})

        assert result is True
        content = note_path.read_text()
        assert "New Title" in content

    def test_add_new_field(self, tmp_path: Path):
        """Test adding new field."""
        note_path = tmp_path / "test.md"
        note_path.write_text("""---
type: note
title: Test
---

Content.
""")

        result = update_frontmatter(note_path, {"new_field": "value"})

        assert result is True
        content = note_path.read_text()
        assert "new_field:" in content

    def test_update_nonexistent_file(self, tmp_path: Path):
        """Test updating nonexistent file."""
        note_path = tmp_path / "nonexistent.md"

        result = update_frontmatter(note_path, {"title": "Test"})

        assert result is False


class TestNoteExists:
    """Tests for note existence checking."""

    def test_note_exists_true(self, tmp_path: Path):
        """Test when note exists."""
        settings = Settings(vault_path=str(tmp_path), knowledge_folder="Knowledge")

        # Create the note first
        create_note(
            content_type="note",
            title="Existing Note",
            content="Content",
            settings=settings,
        )

        result = note_exists("Existing Note", "note", settings)

        assert result is True

    def test_note_exists_false(self, tmp_path: Path):
        """Test when note doesn't exist."""
        settings = Settings(vault_path=str(tmp_path), knowledge_folder="Knowledge")

        result = note_exists("Nonexistent Note", "note", settings)

        assert result is False


class TestGetRelativePath:
    """Tests for relative path calculation."""

    def test_relative_path(self, tmp_path: Path):
        """Test getting relative path."""
        settings = Settings(vault_path=str(tmp_path), knowledge_folder="Knowledge")

        full_path = tmp_path / "Knowledge" / "Notes" / "test.md"
        result = get_relative_path(full_path, settings)

        assert result == "Knowledge/Notes/test.md"

    def test_path_outside_vault(self, tmp_path: Path):
        """Test path outside vault."""
        settings = Settings(vault_path=str(tmp_path), knowledge_folder="Knowledge")

        outside_path = Path("/some/other/path.md")
        result = get_relative_path(outside_path, settings)

        assert result == str(outside_path)
