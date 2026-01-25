"""Tests for the KAS adapter."""

import pytest

from personal_context.adapters.kas import KASAdapter
from personal_context.schema import ContextSource


@pytest.fixture
def adapter() -> KASAdapter:
    """Create adapter with default URL."""
    return KASAdapter("http://localhost:8000")


class TestKASAdapter:
    """Tests for KASAdapter."""

    @pytest.mark.asyncio
    async def test_source_type(self, adapter: KASAdapter):
        """Test source type is KAS."""
        assert adapter.source == ContextSource.KAS

    @pytest.mark.asyncio
    async def test_health_check_offline(self):
        """Test health check fails gracefully when KAS is offline."""
        adapter = KASAdapter("http://localhost:9999")  # Non-existent port
        result = await adapter.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_search_offline(self):
        """Test search returns empty when KAS is offline."""
        adapter = KASAdapter("http://localhost:9999")
        results = await adapter.search("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_ask_offline(self):
        """Test ask returns empty result when KAS is offline."""
        adapter = KASAdapter("http://localhost:9999")
        result = await adapter.ask("test question")
        assert result["answer"] is None
        assert result["confidence"] == 0

    @pytest.mark.asyncio
    async def test_get_namespaces_offline(self):
        """Test get_namespaces returns empty when KAS is offline."""
        adapter = KASAdapter("http://localhost:9999")
        namespaces = await adapter.get_namespaces()
        assert namespaces == []

    @pytest.mark.asyncio
    async def test_convert_result(self, adapter: KASAdapter):
        """Test result conversion."""
        result = {
            "id": "123",
            "title": "Test Title",
            "content": "Test content here",
            "namespace": "support",
            "score": 0.95,
        }
        item = adapter._convert_result(result)

        assert item.id == "kas:123"
        assert item.source == ContextSource.KAS
        assert item.title == "Test Title"
        assert item.content == "Test content here"
        assert item.metadata["namespace"] == "support"
        assert item.metadata["score"] == 0.95

    @pytest.mark.asyncio
    async def test_convert_result_minimal(self, adapter: KASAdapter):
        """Test result conversion with minimal fields."""
        result = {
            "text": "Just some text content",
        }
        item = adapter._convert_result(result)

        assert item.source == ContextSource.KAS
        assert "Just some text" in item.title  # Title derived from content
        assert item.content == "Just some text content"


# Integration tests - only run when KAS is available
@pytest.mark.skipif(True, reason="Requires running KAS service")
class TestKASAdapterIntegration:
    """Integration tests requiring KAS service."""

    @pytest.mark.asyncio
    async def test_health_check_online(self, adapter: KASAdapter):
        """Test health check when KAS is running."""
        result = await adapter.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_search_online(self, adapter: KASAdapter):
        """Test search when KAS is running."""
        results = await adapter.search("troubleshooting", limit=5)
        assert len(results) > 0
        assert all(r.source == ContextSource.KAS for r in results)
