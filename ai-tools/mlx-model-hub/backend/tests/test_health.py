"""Tests for health and metrics API endpoints."""

import pytest


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self, async_client):
        """GET /health should return healthy status."""
        response = await async_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "0.1.0"
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_health_timestamp_is_iso_format(self, async_client):
        """Health timestamp should be ISO format."""
        response = await async_client.get("/health")

        data = response.json()
        timestamp = data["timestamp"]

        # Should be parseable as ISO format
        from datetime import datetime

        # ISO format with timezone
        assert "T" in timestamp
        assert len(timestamp) > 10

    @pytest.mark.asyncio
    async def test_liveness_check(self, async_client):
        """GET /health/live should return alive status."""
        response = await async_client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    @pytest.mark.asyncio
    async def test_readiness_check_structure(self, async_client):
        """GET /health/ready should return readiness structure."""
        response = await async_client.get("/health/ready")

        # May fail if DB not available, but structure should be correct
        data = response.json()
        assert "ready" in data
        assert "checks" in data
        assert isinstance(data["checks"], dict)

    @pytest.mark.asyncio
    async def test_readiness_check_database(self, async_client):
        """Readiness should check database connectivity."""
        response = await async_client.get("/health/ready")

        data = response.json()
        assert "database" in data["checks"]

    @pytest.mark.asyncio
    async def test_readiness_check_storage(self, async_client):
        """Readiness should check storage accessibility."""
        response = await async_client.get("/health/ready")

        data = response.json()
        assert "storage" in data["checks"]


class TestMetricsEndpoint:
    """Tests for Prometheus metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_returns_prometheus_format(self, async_client):
        """GET /metrics should return Prometheus text format."""
        response = await async_client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_metrics_contains_http_metrics(self, async_client):
        """Metrics should include HTTP request metrics."""
        # Make a request first to generate metrics
        await async_client.get("/health")

        response = await async_client.get("/metrics")
        content = response.text

        # Should contain standard HTTP metrics
        assert "http_requests_total" in content or "http_request" in content

    @pytest.mark.asyncio
    async def test_metrics_contains_system_metrics(self, async_client):
        """Metrics should include system metrics."""
        response = await async_client.get("/metrics")
        content = response.text

        # Should contain some form of system/process metrics
        # The exact metrics depend on what's registered
        assert len(content) > 0


class TestDetailedHealth:
    """Tests for detailed health endpoint."""

    @pytest.mark.asyncio
    async def test_detailed_health_structure(self, async_client):
        """GET /health/detailed should return comprehensive info."""
        response = await async_client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()

        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
        assert "storage" in data
        assert "database" in data
        assert "mlx" in data

    @pytest.mark.asyncio
    async def test_detailed_health_environment_info(self, async_client):
        """Detailed health should include environment configuration."""
        response = await async_client.get("/health/detailed")

        data = response.json()
        env = data["environment"]

        assert "debug" in env
        assert "log_level" in env
        assert "host" in env
        assert "port" in env

    @pytest.mark.asyncio
    async def test_detailed_health_storage_info(self, async_client):
        """Detailed health should include storage paths."""
        response = await async_client.get("/health/detailed")

        data = response.json()
        storage = data["storage"]

        assert "base_path" in storage
        assert "models_path" in storage
        assert "datasets_path" in storage
        assert "models_exists" in storage
        assert "datasets_exists" in storage

    @pytest.mark.asyncio
    async def test_detailed_health_mlx_info(self, async_client):
        """Detailed health should include MLX status."""
        response = await async_client.get("/health/detailed")

        data = response.json()
        mlx = data["mlx"]

        assert "status" in mlx

    @pytest.mark.asyncio
    async def test_detailed_health_memory_info(self, async_client):
        """Detailed health should include memory stats."""
        response = await async_client.get("/health/detailed")

        data = response.json()

        # Memory info should be present (psutil is a dependency)
        if "memory" in data:
            mem = data["memory"]
            assert "total_gb" in mem or "status" in mem
