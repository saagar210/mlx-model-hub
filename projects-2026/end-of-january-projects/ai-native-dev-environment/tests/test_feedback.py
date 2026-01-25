"""Tests for feedback tracker and metrics."""

import pytest
from unittest.mock import MagicMock, patch
import tempfile
import os

from universal_context_engine.feedback.tracker import (
    FeedbackTracker,
    InteractionLog,
    feedback_tracker,
    log_interaction,
)
from universal_context_engine.feedback.metrics import QualityMetrics, get_metrics


class TestInteractionLog:
    """Test InteractionLog dataclass."""

    def test_default_values(self):
        """InteractionLog should have sensible defaults."""
        log = InteractionLog()
        assert log.id  # Should have auto-generated UUID
        assert log.timestamp  # Should have auto-generated timestamp
        assert log.tool == ""
        assert log.input_params == {}
        assert log.latency_ms == 0
        assert log.error is None
        assert log.user_feedback is None

    def test_custom_values(self):
        """InteractionLog should accept custom values."""
        log = InteractionLog(
            tool="search_context",
            input_params={"query": "test"},
            output="results",
            latency_ms=150,
            error="Test error",
        )
        assert log.tool == "search_context"
        assert log.input_params == {"query": "test"}
        assert log.latency_ms == 150
        assert log.error == "Test error"


class TestFeedbackTracker:
    """Test FeedbackTracker class."""

    @pytest.fixture
    def temp_tracker(self):
        """Create tracker with temporary storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = FeedbackTracker(persist_directory=tmpdir)
            yield tracker

    def test_log_interaction(self, temp_tracker):
        """log_interaction should store and return ID."""
        interaction_id = temp_tracker.log_interaction(
            tool="test_tool",
            input_params={"query": "test"},
            output={"result": "data"},
            latency_ms=100,
        )

        assert interaction_id
        assert temp_tracker._last_interaction_id == interaction_id

    def test_log_interaction_with_error(self, temp_tracker):
        """log_interaction should handle error field."""
        interaction_id = temp_tracker.log_interaction(
            tool="test_tool",
            input_params={},
            output=None,
            latency_ms=50,
            error="Something went wrong",
        )

        assert interaction_id
        # Verify it was stored with error
        interactions = temp_tracker.get_interactions()
        assert any(i.get("has_error") for i in interactions)

    def test_log_interaction_truncates_output(self, temp_tracker):
        """log_interaction should truncate long outputs."""
        long_output = "x" * 5000
        interaction_id = temp_tracker.log_interaction(
            tool="test_tool",
            input_params={},
            output=long_output,
            latency_ms=100,
        )

        # Verify output was truncated (stored in metadata preview)
        interactions = temp_tracker.get_interactions()
        for i in interactions:
            if i["id"] == interaction_id:
                assert len(i.get("output_preview", "")) <= 200

    def test_mark_helpful_success(self, temp_tracker):
        """mark_helpful should update feedback."""
        interaction_id = temp_tracker.log_interaction(
            tool="test_tool",
            input_params={},
            output="result",
            latency_ms=100,
        )

        result = temp_tracker.mark_helpful(interaction_id)
        assert result is True

        # Verify feedback was recorded
        interactions = temp_tracker.get_interactions(feedback_filter="helpful")
        assert any(i["id"] == interaction_id for i in interactions)

    def test_mark_helpful_last_interaction(self, temp_tracker):
        """mark_helpful with None should use last interaction."""
        temp_tracker.log_interaction(
            tool="test_tool",
            input_params={},
            output="result",
            latency_ms=100,
        )

        result = temp_tracker.mark_helpful(None)
        assert result is True

    def test_mark_helpful_no_last_interaction(self, temp_tracker):
        """mark_helpful should return False if no last interaction."""
        result = temp_tracker.mark_helpful(None)
        assert result is False

    def test_mark_not_helpful_with_reason(self, temp_tracker):
        """mark_not_helpful should store reason."""
        interaction_id = temp_tracker.log_interaction(
            tool="test_tool",
            input_params={},
            output="result",
            latency_ms=100,
        )

        result = temp_tracker.mark_not_helpful(interaction_id, reason="Results were irrelevant")
        assert result is True

    def test_get_interactions_filter_by_tool(self, temp_tracker):
        """get_interactions should filter by tool."""
        temp_tracker.log_interaction(tool="tool_a", input_params={}, output="", latency_ms=10)
        temp_tracker.log_interaction(tool="tool_b", input_params={}, output="", latency_ms=10)
        temp_tracker.log_interaction(tool="tool_a", input_params={}, output="", latency_ms=10)

        interactions = temp_tracker.get_interactions(tool="tool_a")
        assert len(interactions) == 2
        assert all(i["tool"] == "tool_a" for i in interactions)

    def test_get_interactions_limit(self, temp_tracker):
        """get_interactions should respect limit."""
        for i in range(10):
            temp_tracker.log_interaction(tool="tool", input_params={}, output="", latency_ms=10)

        interactions = temp_tracker.get_interactions(limit=5)
        assert len(interactions) == 5

    def test_get_stats(self, temp_tracker):
        """get_stats should return accurate statistics."""
        # Log some interactions
        id1 = temp_tracker.log_interaction(tool="tool_a", input_params={}, output="", latency_ms=100)
        id2 = temp_tracker.log_interaction(tool="tool_b", input_params={}, output="", latency_ms=200)
        id3 = temp_tracker.log_interaction(tool="tool_a", input_params={}, output="", latency_ms=150)

        # Mark feedback
        temp_tracker.mark_helpful(id1)
        temp_tracker.mark_not_helpful(id2)

        stats = temp_tracker.get_stats()

        assert stats["total_interactions"] == 3
        assert stats["helpful"] == 1
        assert stats["not_helpful"] == 1
        assert stats["no_feedback"] == 1
        assert stats["by_tool"]["tool_a"] == 2
        assert stats["by_tool"]["tool_b"] == 1
        assert stats["avg_latency_ms"] == 150  # (100 + 200 + 150) / 3


class TestLogInteractionFunction:
    """Test module-level log_interaction function."""

    def test_log_interaction_uses_default_tracker(self):
        """log_interaction should use default tracker."""
        with patch.object(feedback_tracker, "log_interaction", return_value="test-id") as mock:
            result = log_interaction(
                tool="test",
                input_params={},
                output="",
                latency_ms=10,
            )

            mock.assert_called_once()
            assert result == "test-id"


class TestQualityMetrics:
    """Test QualityMetrics dataclass."""

    def test_quality_metrics_fields(self):
        """QualityMetrics should have all fields."""
        metrics = QualityMetrics(
            total_interactions=100,
            helpful_count=80,
            not_helpful_count=10,
            feedback_rate=0.9,
            helpful_rate=0.89,
            avg_latency_ms=150.5,
            error_rate=0.05,
            by_tool={"search": 50, "save": 50},
        )

        assert metrics.total_interactions == 100
        assert metrics.helpful_rate == 0.89
        assert metrics.by_tool == {"search": 50, "save": 50}


class TestGetMetrics:
    """Test get_metrics function."""

    def test_get_metrics_returns_quality_metrics(self):
        """get_metrics should return QualityMetrics instance."""
        with patch.object(feedback_tracker, "get_stats") as mock_stats:
            mock_stats.return_value = {
                "total_interactions": 100,
                "helpful": 80,
                "not_helpful": 10,
                "feedback_rate": 0.9,
                "helpful_rate": 0.89,
                "avg_latency_ms": 150.5,
                "by_tool": {"search": 50},
            }

            metrics = get_metrics()

            assert isinstance(metrics, QualityMetrics)
            assert metrics.total_interactions == 100
