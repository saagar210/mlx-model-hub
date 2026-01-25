"""Tests for feedback logging integration."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def mock_feedback_tracker():
    """Mock the feedback tracker."""
    with patch("universal_context_engine.feedback.feedback_tracker") as mock:
        mock.log_interaction = MagicMock()
        yield mock


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


class TestFeedbackLoggingIntegration:
    """Test that tool calls log to feedback tracker."""

    @pytest.mark.asyncio
    async def test_save_context_logs_interaction(self, mock_feedback_tracker, mock_context_store, mock_embedding_client):
        """save_context should log interaction to feedback tracker."""
        from universal_context_engine.server import save_context
        from universal_context_engine.models import ContextItem, ContextType
        from datetime import datetime, UTC

        # Setup mock return
        mock_context_store.save.return_value = ContextItem(
            id="test-id",
            content="test content",
            context_type=ContextType.CONTEXT,
            timestamp=datetime.now(UTC),
        )

        # Call the tool (accessing the underlying function)
        result = await save_context.fn(content="test content", context_type="context")

        # Verify feedback was logged
        assert mock_feedback_tracker.log_interaction.called
        call_args = mock_feedback_tracker.log_interaction.call_args
        assert call_args.kwargs["tool"] == "save_context"
        assert call_args.kwargs["error"] is None

    @pytest.mark.asyncio
    async def test_search_context_logs_interaction(self, mock_feedback_tracker, mock_context_store, mock_embedding_client):
        """search_context should log interaction to feedback tracker."""
        from universal_context_engine.server import search_context

        # Call the tool
        result = await search_context.fn(query="test query")

        # Verify feedback was logged
        assert mock_feedback_tracker.log_interaction.called
        call_args = mock_feedback_tracker.log_interaction.call_args
        assert call_args.kwargs["tool"] == "search_context"
        assert call_args.kwargs["error"] is None

    @pytest.mark.asyncio
    async def test_context_stats_logs_interaction(self, mock_feedback_tracker, mock_context_store):
        """context_stats should log interaction to feedback tracker."""
        from universal_context_engine.server import context_stats

        # Call the tool
        result = await context_stats.fn()

        # Verify feedback was logged
        assert mock_feedback_tracker.log_interaction.called
        call_args = mock_feedback_tracker.log_interaction.call_args
        assert call_args.kwargs["tool"] == "context_stats"

    @pytest.mark.asyncio
    async def test_failed_tool_logs_error(self, mock_feedback_tracker, mock_context_store):
        """Failed tool calls should log with error."""
        from universal_context_engine.server import save_context

        # Make the mock raise an exception
        mock_context_store.save.side_effect = Exception("Test error")

        # Call the tool - should not raise, should return error response
        result = await save_context.fn(content="test", context_type="context")

        # Verify error response
        assert result.get("success") is False
        assert "error" in result

        # Verify feedback was logged with error
        assert mock_feedback_tracker.log_interaction.called
        call_args = mock_feedback_tracker.log_interaction.call_args
        assert call_args.kwargs["tool"] == "save_context"
        assert call_args.kwargs["error"] is not None
        assert "Test error" in call_args.kwargs["error"]

    @pytest.mark.asyncio
    async def test_latency_is_captured(self, mock_feedback_tracker, mock_context_store):
        """Tool calls should capture latency."""
        from universal_context_engine.server import context_stats

        # Call the tool
        await context_stats.fn()

        # Verify latency was captured
        call_args = mock_feedback_tracker.log_interaction.call_args
        assert "latency_ms" in call_args.kwargs
        assert isinstance(call_args.kwargs["latency_ms"], int)
        assert call_args.kwargs["latency_ms"] >= 0
