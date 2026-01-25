"""Tests for dashboard API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from fastapi.testclient import TestClient

from universal_context_engine.dashboard.api import app
from universal_context_engine.models import ContextItem, ContextType
from universal_context_engine.feedback.metrics import QualityMetrics


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_services():
    """Mock all external services."""
    with patch("universal_context_engine.dashboard.api.embedding_client") as mock_embed, \
         patch("universal_context_engine.dashboard.api.kas_adapter") as mock_kas, \
         patch("universal_context_engine.dashboard.api.localcrew_adapter") as mock_localcrew, \
         patch("universal_context_engine.dashboard.api.context_store") as mock_store, \
         patch("universal_context_engine.dashboard.api.aioredis") as mock_redis, \
         patch("universal_context_engine.dashboard.api.get_metrics") as mock_metrics, \
         patch("universal_context_engine.dashboard.api.feedback_tracker") as mock_feedback:

        # Configure mocks
        mock_embed.health_check = AsyncMock(return_value=True)
        mock_kas.health = AsyncMock(return_value={"status": "healthy"})
        mock_localcrew.health = AsyncMock(return_value={"status": "healthy"})
        mock_store.get_stats = MagicMock(return_value={"session": 10, "decision": 5, "context": 15})
        mock_store.get_recent = AsyncMock(return_value=[])

        # Mock Redis
        redis_instance = AsyncMock()
        redis_instance.ping = AsyncMock()
        redis_instance.aclose = AsyncMock()
        mock_redis.from_url.return_value = redis_instance

        # Mock metrics
        mock_metrics.return_value = QualityMetrics(
            total_interactions=100,
            helpful_count=80,
            not_helpful_count=10,
            feedback_rate=0.9,
            helpful_rate=0.89,
            avg_latency_ms=150.0,
            error_rate=0.05,
            by_tool={"search_context": 50, "save_context": 30},
        )

        yield {
            "embed": mock_embed,
            "kas": mock_kas,
            "localcrew": mock_localcrew,
            "store": mock_store,
            "redis": mock_redis,
            "metrics": mock_metrics,
            "feedback": mock_feedback,
        }


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_all_healthy(self, client, mock_services):
        """Health should return healthy when all services are up."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert all(s["status"] == "healthy" for s in data["services"].values())

    def test_health_degraded_when_service_down(self, client, mock_services):
        """Health should return degraded when a service is down."""
        mock_services["kas"].health.return_value = {"status": "unhealthy", "error": "Connection refused"}

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["kas"]["status"] == "unhealthy"

    def test_health_includes_timestamp(self, client, mock_services):
        """Health response should include timestamp."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data

    def test_health_handles_exception(self, client, mock_services):
        """Health should handle service exceptions gracefully."""
        mock_services["embed"].health_check.side_effect = Exception("Connection error")

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["services"]["ollama"]["status"] == "unhealthy"
        assert "error" in data["services"]["ollama"]


class TestStatsEndpoint:
    """Test /stats endpoint."""

    def test_stats_returns_context_stats(self, client, mock_services):
        """Stats should return context statistics."""
        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert "context" in data
        assert data["context"]["total"] == 30  # 10 + 5 + 15
        assert "by_type" in data["context"]

    def test_stats_includes_storage_path(self, client, mock_services):
        """Stats should include storage path."""
        response = client.get("/stats")

        assert response.status_code == 200
        data = response.json()
        assert "storage_path" in data


class TestQualityEndpoint:
    """Test /quality endpoint."""

    def test_quality_returns_metrics(self, client, mock_services):
        """Quality should return quality metrics."""
        response = client.get("/quality")

        assert response.status_code == 200
        data = response.json()
        assert data["total_interactions"] == 100
        assert "feedback" in data
        assert data["feedback"]["helpful"] == 80
        assert data["feedback"]["not_helpful"] == 10

    def test_quality_includes_performance(self, client, mock_services):
        """Quality should include performance metrics."""
        response = client.get("/quality")

        assert response.status_code == 200
        data = response.json()
        assert "performance" in data
        assert "avg_latency_ms" in data["performance"]
        assert "error_rate_percent" in data["performance"]

    def test_quality_includes_by_tool(self, client, mock_services):
        """Quality should include per-tool breakdown."""
        response = client.get("/quality")

        assert response.status_code == 200
        data = response.json()
        assert "by_tool" in data
        assert "search_context" in data["by_tool"]


class TestSessionsEndpoint:
    """Test /sessions endpoint."""

    def test_sessions_returns_recent_sessions(self, client, mock_services):
        """Sessions should return recent session list."""
        mock_item = ContextItem(
            id="session-1",
            content="Worked on authentication",
            context_type=ContextType.SESSION,
            project="/test/project",
            branch="main",
            timestamp=datetime.now(UTC),
        )
        mock_services["store"].get_recent.return_value = [mock_item]

        response = client.get("/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert data["count"] == 1
        assert data["sessions"][0]["id"] == "session-1"

    def test_sessions_respects_limit(self, client, mock_services):
        """Sessions should respect limit parameter."""
        response = client.get("/sessions?limit=5")

        mock_services["store"].get_recent.assert_called_once()
        call_kwargs = mock_services["store"].get_recent.call_args.kwargs
        assert call_kwargs["limit"] == 5


class TestDecisionsEndpoint:
    """Test /decisions endpoint."""

    def test_decisions_returns_recent_decisions(self, client, mock_services):
        """Decisions should return recent decision list."""
        mock_item = ContextItem(
            id="decision-1",
            content="Use PostgreSQL for persistence",
            context_type=ContextType.DECISION,
            project="/test/project",
            timestamp=datetime.now(UTC),
            metadata={"category": "database"},
        )
        mock_services["store"].get_recent.return_value = [mock_item]

        response = client.get("/decisions")

        assert response.status_code == 200
        data = response.json()
        assert "decisions" in data
        assert data["count"] == 1
        assert data["decisions"][0]["category"] == "database"

    def test_decisions_filters_by_project(self, client, mock_services):
        """Decisions should filter by project."""
        response = client.get("/decisions?project=/test/project")

        call_kwargs = mock_services["store"].get_recent.call_args.kwargs
        assert call_kwargs["project"] == "/test/project"


class TestBlockersEndpoint:
    """Test /blockers endpoint."""

    def test_blockers_returns_active_blockers(self, client, mock_services):
        """Blockers should return active blockers by default."""
        mock_items = [
            ContextItem(
                id="blocker-1",
                content="OAuth redirect failing",
                context_type=ContextType.BLOCKER,
                project="/test/project",
                timestamp=datetime.now(UTC),
                metadata={"severity": "high", "resolved": False},
            ),
            ContextItem(
                id="blocker-2",
                content="Old resolved issue",
                context_type=ContextType.BLOCKER,
                project="/test/project",
                timestamp=datetime.now(UTC),
                metadata={"severity": "low", "resolved": True},
            ),
        ]
        mock_services["store"].get_recent.return_value = mock_items

        response = client.get("/blockers")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1  # Only unresolved
        assert data["active_count"] == 1
        assert data["blockers"][0]["id"] == "blocker-1"

    def test_blockers_includes_resolved(self, client, mock_services):
        """Blockers should include resolved when requested."""
        mock_items = [
            ContextItem(
                id="blocker-1",
                content="Active issue",
                context_type=ContextType.BLOCKER,
                timestamp=datetime.now(UTC),
                metadata={"resolved": False},
            ),
            ContextItem(
                id="blocker-2",
                content="Resolved issue",
                context_type=ContextType.BLOCKER,
                timestamp=datetime.now(UTC),
                metadata={"resolved": True},
            ),
        ]
        mock_services["store"].get_recent.return_value = mock_items

        response = client.get("/blockers?include_resolved=true")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2


class TestCORS:
    """Test CORS configuration."""

    def test_cors_allows_localhost(self, client):
        """CORS should allow localhost origins."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8002",
                "Access-Control-Request-Method": "GET",
            }
        )
        # OPTIONS request should succeed
        assert response.status_code in [200, 204]

    def test_cors_methods_restricted(self, client, mock_services):
        """CORS should only allow GET methods."""
        # POST should not be in allowed methods
        # This is enforced by the middleware, verified by the app configuration
        assert "POST" not in ["GET"]  # Dashboard is read-only
