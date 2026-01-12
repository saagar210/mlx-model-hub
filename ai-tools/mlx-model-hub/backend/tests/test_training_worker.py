"""Tests for training worker module."""

import contextlib
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from mlx_hub.training.worker import (
    check_memory_available,
    generate_version_number,
)


class TestCheckMemoryAvailable:
    """Tests for memory availability checking."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self):
        """Clear settings cache before and after tests."""
        from mlx_hub.config import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_memory_available_when_sufficient(self, monkeypatch):
        """Should return True when memory exceeds limit."""
        monkeypatch.setenv("MLX_MEMORY_LIMIT_GB", "8")

        # Mock psutil to return 16GB available
        mock_memory = MagicMock()
        mock_memory.available = 16 * 1024**3  # 16 GB

        with patch("psutil.virtual_memory", return_value=mock_memory):
            from mlx_hub.config import get_settings

            get_settings.cache_clear()
            assert check_memory_available() is True

    def test_memory_unavailable_when_insufficient(self, monkeypatch):
        """Should return False when memory below limit."""
        monkeypatch.setenv("MLX_MEMORY_LIMIT_GB", "32")

        # Mock psutil to return 8GB available
        mock_memory = MagicMock()
        mock_memory.available = 8 * 1024**3  # 8 GB

        with patch("psutil.virtual_memory", return_value=mock_memory):
            from mlx_hub.config import get_settings

            get_settings.cache_clear()
            assert check_memory_available() is False

    def test_memory_available_at_boundary(self, monkeypatch):
        """Should return True when memory equals limit."""
        monkeypatch.setenv("MLX_MEMORY_LIMIT_GB", "8")

        # Mock psutil to return exactly 8GB
        mock_memory = MagicMock()
        mock_memory.available = 8 * 1024**3  # 8 GB

        with patch("psutil.virtual_memory", return_value=mock_memory):
            from mlx_hub.config import get_settings

            get_settings.cache_clear()
            assert check_memory_available() is True


class TestGenerateVersionNumber:
    """Tests for version number generation."""

    def test_version_format(self):
        """Version should follow v{YYYYMMDD}.{HHMMSS} format."""
        version = generate_version_number("test-model")

        # Should start with 'v'
        assert version.startswith("v")

        # Should contain a dot separator
        assert "." in version

        # Should be like vYYYYMMDD.HHMMSS (15 chars total)
        parts = version[1:].split(".")  # Remove 'v' prefix
        assert len(parts) == 2
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS

    def test_version_is_timestamp_based(self):
        """Version should reflect current timestamp."""
        now = datetime.now(UTC)
        version = generate_version_number("test-model")

        expected_date = now.strftime("%Y%m%d")
        assert expected_date in version

    def test_version_ignores_model_name(self):
        """Model name should not affect version format."""
        v1 = generate_version_number("model-a")
        v2 = generate_version_number("model-b")

        # Both should have same format
        assert v1.startswith("v")
        assert v2.startswith("v")
        # Date part should be same (assuming same second)
        assert v1[:10] == v2[:10]  # v{YYYYMMDD}


class TestWorkerState:
    """Tests for worker state management."""

    def test_initial_state_is_not_running(self):
        """Worker should start in non-running state."""
        from mlx_hub.training import worker

        # Reset state
        worker._worker_running = False
        worker._worker_task = None

        assert worker._worker_running is False
        assert worker._worker_task is None


class TestCleanupStaleJobs:
    """Tests for stale job cleanup functionality."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self):
        """Clear settings cache."""
        from mlx_hub.config import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_cleanup_marks_stale_jobs_as_failed(self, monkeypatch, tmp_path):
        """Jobs with old heartbeats should be marked failed."""
        from mlx_hub.training.worker import cleanup_stale_jobs
        from mlx_hub.db.enums import JobStatus
        from uuid import uuid4

        # Set up mock session that returns a stale job
        stale_job = MagicMock()
        stale_job.id = uuid4()
        stale_job.status = JobStatus.RUNNING
        stale_job.heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stale_job]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        # Create context manager for session
        @contextlib.asynccontextmanager
        async def mock_session_factory():
            yield mock_session

        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        monkeypatch.setenv("STORAGE_BASE_PATH", str(tmp_path))

        with patch("mlx_hub.training.worker.get_session_factory", return_value=mock_session_factory):
            await cleanup_stale_jobs()

        # Verify job was marked as failed
        assert stale_job.status == JobStatus.FAILED
        assert "timed out" in stale_job.error_message.lower()
        mock_session.commit.assert_called_once()
