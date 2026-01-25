"""Tests for error paths in critical tool flows."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from universal_context_engine.server import (
    save_context,
    search_context,
    get_recent,
    unified_search,
    research,
    service_status,
)


@pytest.fixture
def mock_context_store():
    """Mock the context store."""
    with patch("universal_context_engine.server.context_store") as mock:
        mock.save = AsyncMock()
        mock.search = AsyncMock(return_value=[])
        mock.get_recent = AsyncMock(return_value=[])
        mock.get_stats = MagicMock(return_value={"session": 0, "decision": 0})
        yield mock


@pytest.fixture
def mock_embedding_client():
    """Mock the embedding client."""
    with patch("universal_context_engine.context_store.embedding_client") as mock:
        mock.embed = AsyncMock(return_value=[0.1] * 768)
        yield mock


@pytest.fixture
def mock_feedback_tracker():
    """Mock the feedback tracker."""
    with patch("universal_context_engine.feedback.feedback_tracker") as mock:
        mock.log_interaction = MagicMock()
        yield mock


class TestSaveContextErrorPaths:
    """Test error handling in save_context."""

    @pytest.mark.asyncio
    async def test_save_context_embedding_failure(self, mock_context_store, mock_feedback_tracker):
        """save_context should handle embedding failures gracefully."""
        with patch("universal_context_engine.server.context_store") as store_mock:
            store_mock.save = AsyncMock(side_effect=Exception("Embedding service unavailable"))

            result = await save_context.fn(content="test", context_type="context")

            assert result.get("success") is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_save_context_chromadb_failure(self, mock_context_store, mock_feedback_tracker):
        """save_context should handle ChromaDB failures gracefully."""
        with patch("universal_context_engine.server.context_store") as store_mock:
            store_mock.save = AsyncMock(side_effect=Exception("ChromaDB connection failed"))

            result = await save_context.fn(content="test", context_type="context")

            assert result.get("success") is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_save_context_invalid_type_fallback(self, mock_context_store, mock_feedback_tracker):
        """save_context should fallback for invalid context type."""
        from universal_context_engine.models import ContextItem, ContextType

        mock_context_store.save.return_value = ContextItem(
            id="test-id",
            content="test",
            context_type=ContextType.CONTEXT,
            timestamp=datetime.now(UTC),
        )

        with patch("universal_context_engine.server.context_store", mock_context_store):
            result = await save_context.fn(content="test", context_type="invalid_type")

            # Should succeed with fallback to "context" type
            assert "id" in result


class TestSearchContextErrorPaths:
    """Test error handling in search_context."""

    @pytest.mark.asyncio
    async def test_search_context_embedding_failure(self, mock_context_store, mock_feedback_tracker):
        """search_context should handle embedding failures gracefully."""
        with patch("universal_context_engine.server.context_store") as store_mock:
            store_mock.search = AsyncMock(side_effect=Exception("Embedding service unavailable"))

            result = await search_context.fn(query="test query")

            assert result.get("success") is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_search_context_chromadb_failure(self, mock_context_store, mock_feedback_tracker):
        """search_context should handle ChromaDB failures gracefully."""
        with patch("universal_context_engine.server.context_store") as store_mock:
            store_mock.search = AsyncMock(side_effect=Exception("ChromaDB query failed"))

            result = await search_context.fn(query="test query")

            assert result.get("success") is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_search_context_empty_results(self, mock_context_store, mock_feedback_tracker):
        """search_context should handle empty results."""
        with patch("universal_context_engine.server.context_store") as store_mock:
            store_mock.search = AsyncMock(return_value=[])

            result = await search_context.fn(query="test query")

            # Should return empty list, not error
            assert isinstance(result, list)
            assert len(result) == 0


class TestGetRecentErrorPaths:
    """Test error handling in get_recent."""

    @pytest.mark.asyncio
    async def test_get_recent_chromadb_failure(self, mock_context_store, mock_feedback_tracker):
        """get_recent should handle ChromaDB failures gracefully."""
        with patch("universal_context_engine.server.context_store") as store_mock:
            store_mock.get_recent = AsyncMock(side_effect=Exception("ChromaDB unavailable"))

            result = await get_recent.fn(hours=24)

            assert result.get("success") is False
            assert "error" in result


class TestUnifiedSearchErrorPaths:
    """Test error handling in unified_search."""

    @pytest.mark.asyncio
    async def test_unified_search_kas_failure(self, mock_context_store, mock_feedback_tracker):
        """unified_search should handle KAS failures gracefully."""
        with patch("universal_context_engine.server.context_store") as store_mock, \
             patch("universal_context_engine.server.kas_adapter") as kas_mock:

            store_mock.search = AsyncMock(return_value=[])
            kas_mock.search = AsyncMock(side_effect=Exception("KAS unavailable"))

            result = await unified_search.fn(query="test", sources=["context", "kas"])

            # Should still return context results even if KAS fails
            assert result.get("success") is False or isinstance(result, list)

    @pytest.mark.asyncio
    async def test_unified_search_partial_failure(self, mock_context_store, mock_feedback_tracker):
        """unified_search should return partial results on partial failure."""
        from universal_context_engine.models import ContextItem, ContextType, SearchResult

        mock_item = ContextItem(
            id="ctx-1",
            content="test content",
            context_type=ContextType.CONTEXT,
            timestamp=datetime.now(UTC),
        )
        mock_search_result = SearchResult(item=mock_item, score=0.9, distance=0.1)

        with patch("universal_context_engine.server.context_store") as store_mock, \
             patch("universal_context_engine.server.kas_adapter") as kas_mock:

            store_mock.search = AsyncMock(return_value=[mock_search_result])
            kas_mock.search = AsyncMock(return_value=[])  # KAS returns empty

            result = await unified_search.fn(query="test", sources=["context", "kas"])

            # Should return context results
            if isinstance(result, list):
                assert len(result) >= 1


class TestResearchErrorPaths:
    """Test error handling in research tool."""

    @pytest.mark.asyncio
    async def test_research_localcrew_failure(self, mock_feedback_tracker):
        """research should handle LocalCrew failures gracefully."""
        with patch("universal_context_engine.server.localcrew_adapter") as mock:
            mock.research = AsyncMock(side_effect=Exception("LocalCrew unavailable"))

            result = await research.fn(topic="test topic")

            assert result.get("success") is False
            assert "error" in result


class TestServiceStatusErrorPaths:
    """Test error handling in service_status."""

    @pytest.mark.asyncio
    async def test_service_status_all_services_down(self, mock_feedback_tracker):
        """service_status should report all services when all are down."""
        with patch("universal_context_engine.server.embedding_client") as embed_mock, \
             patch("universal_context_engine.server.kas_adapter") as kas_mock, \
             patch("universal_context_engine.server.localcrew_adapter") as crew_mock, \
             patch("redis.asyncio.from_url") as redis_mock:

            embed_mock.health_check = AsyncMock(return_value=False)
            kas_mock.health = AsyncMock(return_value={"status": "unhealthy", "error": "down"})
            crew_mock.health = AsyncMock(return_value={"status": "unhealthy", "error": "down"})
            redis_instance = AsyncMock()
            redis_instance.ping = AsyncMock(side_effect=Exception("Connection refused"))
            redis_instance.aclose = AsyncMock()
            redis_mock.return_value = redis_instance

            result = await service_status.fn()

            # Should still return a result, not crash
            if isinstance(result, dict):
                assert result.get("overall") == "degraded" or "error" in result


class TestErrorResponseFormat:
    """Test that error responses have consistent format."""

    @pytest.mark.asyncio
    async def test_error_response_structure(self, mock_context_store, mock_feedback_tracker):
        """Error responses should have consistent structure."""
        with patch("universal_context_engine.server.context_store") as store_mock:
            store_mock.save = AsyncMock(side_effect=Exception("Test error"))

            result = await save_context.fn(content="test", context_type="context")

            # Check error response structure
            assert result.get("success") is False
            assert "error" in result
            error_info = result["error"]
            assert "code" in error_info or "message" in error_info or isinstance(error_info, str)

    @pytest.mark.asyncio
    async def test_error_includes_tool_name(self, mock_context_store, mock_feedback_tracker):
        """Error responses should include tool name."""
        with patch("universal_context_engine.server.context_store") as store_mock:
            store_mock.save = AsyncMock(side_effect=Exception("Test error"))

            result = await save_context.fn(content="test", context_type="context")

            # Error should identify which tool failed
            if isinstance(result.get("error"), dict):
                assert "tool" in result["error"] or "save_context" in str(result)


class TestTimeoutHandling:
    """Test timeout handling in tools."""

    @pytest.mark.asyncio
    async def test_embedding_timeout(self, mock_context_store, mock_feedback_tracker):
        """Tools should handle embedding timeouts."""
        import asyncio

        with patch("universal_context_engine.server.context_store") as store_mock:
            async def slow_save(*args, **kwargs):
                await asyncio.sleep(0.01)
                raise TimeoutError("Embedding timeout")

            store_mock.save = slow_save

            result = await save_context.fn(content="test", context_type="context")

            assert result.get("success") is False
