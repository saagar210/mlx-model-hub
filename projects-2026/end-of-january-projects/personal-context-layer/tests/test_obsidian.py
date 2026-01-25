"""Tests for the Obsidian adapter."""

from pathlib import Path

import pytest

from personal_context.adapters.obsidian import ObsidianAdapter
from personal_context.schema import ContextSource


@pytest.fixture
def adapter(temp_vault: Path) -> ObsidianAdapter:
    """Create adapter with test vault."""
    return ObsidianAdapter(temp_vault)


class TestObsidianAdapter:
    """Tests for ObsidianAdapter."""

    @pytest.mark.asyncio
    async def test_health_check(self, adapter: ObsidianAdapter):
        """Test health check passes for valid vault."""
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_invalid_path(self, tmp_path: Path):
        """Test health check fails for invalid vault."""
        with pytest.raises(ValueError):
            ObsidianAdapter(tmp_path / "nonexistent")

    @pytest.mark.asyncio
    async def test_search_by_content(self, adapter: ObsidianAdapter):
        """Test searching notes by content."""
        results = await adapter.search("OAuth", limit=10)
        assert len(results) >= 1
        assert any("authentication" in r.path.lower() for r in results)

    @pytest.mark.asyncio
    async def test_search_by_title(self, adapter: ObsidianAdapter):
        """Test searching notes by filename."""
        results = await adapter.search("authentication", limit=10)
        assert len(results) >= 1
        assert results[0].source == ContextSource.OBSIDIAN

    @pytest.mark.asyncio
    async def test_search_no_results(self, adapter: ObsidianAdapter):
        """Test search with no matches."""
        results = await adapter.search("nonexistent-xyz-123", limit=10)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_read_note_with_frontmatter(self, adapter: ObsidianAdapter):
        """Test reading a note with YAML frontmatter."""
        result = await adapter.read_note("Knowledge/Notes/authentication.md")
        assert result is not None
        assert result.title == "Authentication Approaches"
        assert "tags" in result.frontmatter
        assert "OAuth" in result.content

    @pytest.mark.asyncio
    async def test_read_note_without_extension(self, adapter: ObsidianAdapter):
        """Test reading a note without .md extension."""
        result = await adapter.read_note("Knowledge/Notes/authentication")
        assert result is not None
        assert result.title == "Authentication Approaches"

    @pytest.mark.asyncio
    async def test_read_note_not_found(self, adapter: ObsidianAdapter):
        """Test reading a nonexistent note."""
        result = await adapter.read_note("nonexistent/note.md")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_backlinks(self, adapter: ObsidianAdapter):
        """Test finding backlinks to a note."""
        backlinks = await adapter.get_backlinks("Knowledge/Notes/authentication.md")
        # session-management links to authentication
        assert len(backlinks) >= 1
        assert any("session-management" in b for b in backlinks)

    @pytest.mark.asyncio
    async def test_get_recent(self, adapter: ObsidianAdapter):
        """Test getting recently modified notes."""
        results = await adapter.get_recent(hours=24 * 365, limit=10)  # Look back a year
        assert len(results) >= 1
        # Should return our test notes
        assert all(r.source == ContextSource.OBSIDIAN for r in results)

    @pytest.mark.asyncio
    async def test_list_by_tag(self, adapter: ObsidianAdapter):
        """Test finding notes by tag."""
        results = await adapter.list_by_tag("security", limit=10)
        assert len(results) >= 2  # authentication and session-management

    @pytest.mark.asyncio
    async def test_list_by_tag_with_hash(self, adapter: ObsidianAdapter):
        """Test tag search works with or without hash prefix."""
        results1 = await adapter.list_by_tag("security")
        results2 = await adapter.list_by_tag("#security")
        assert len(results1) == len(results2)
