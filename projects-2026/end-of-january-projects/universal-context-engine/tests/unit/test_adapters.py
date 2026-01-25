"""Tests for adapters."""

import pytest
from datetime import datetime, timedelta

from uce.adapters.base import SyncCursor
from uce.adapters.git_adapter import GitAdapter
from uce.adapters.browser_adapter import BrowserContextAdapter


class TestSyncCursor:
    """Tests for SyncCursor."""

    def test_cursor_creation(self):
        """Test creating a sync cursor."""
        cursor = SyncCursor(source="test")
        assert cursor.source == "test"
        assert cursor.cursor_value is None
        assert cursor.items_synced == 0

    def test_cursor_update(self):
        """Test updating a sync cursor."""
        cursor = SyncCursor(source="test")
        cursor.update("new_value", items_added=10)

        assert cursor.cursor_value == "new_value"
        assert cursor.items_synced == 10
        assert cursor.last_sync_at is not None


class TestGitAdapter:
    """Tests for GitAdapter."""

    def test_adapter_properties(self):
        """Test adapter has correct properties."""
        adapter = GitAdapter(repo_paths=["/tmp/test"])
        assert adapter.name == "Git Repository"
        assert adapter.source_type == "git"
        assert adapter.get_source_quality() == 0.75

    def test_sync_interval(self):
        """Test sync interval is reasonable."""
        adapter = GitAdapter(repo_paths=[])
        interval = adapter.get_sync_interval()
        assert interval == timedelta(minutes=2)


class TestBrowserAdapter:
    """Tests for BrowserContextAdapter."""

    def test_adapter_properties(self):
        """Test adapter has correct properties."""
        adapter = BrowserContextAdapter()
        assert adapter.name == "Browser Context"
        assert adapter.source_type == "browser"
        assert adapter.get_source_quality() == 0.6

    def test_add_tab_manually(self):
        """Test manually adding a tab."""
        adapter = BrowserContextAdapter()
        item = adapter.add_tab_manually(
            url="https://example.com",
            title="Example Site",
            content="Page content here",
        )

        assert item.source == "browser"
        assert item.content_type == "page_content"
        assert "example.com" in item.source_url
        assert item.expires_at is not None

    def test_domain_extraction(self):
        """Test domain extraction from URL."""
        adapter = BrowserContextAdapter()
        domain = adapter._domain_from_url("https://docs.python.org/3/library/")
        assert domain == "docs.python.org"

    def test_cache_management(self):
        """Test cache clearing."""
        adapter = BrowserContextAdapter()
        adapter._cached_tabs["test"] = {"url": "test", "timestamp": datetime.utcnow()}
        assert len(adapter._cached_tabs) == 1

        adapter.clear_cache()
        assert len(adapter._cached_tabs) == 0
