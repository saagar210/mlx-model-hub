"""API integration tests.

Tests API endpoints with real database and services.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from knowledge.db import Database


@pytest.mark.integration
class TestSearchAPIIntegration:
    """Integration tests for search endpoints."""

    async def test_search_endpoint_returns_results(
        self, api_client: AsyncClient, seeded_db: Database
    ):
        """Test search endpoint returns real results."""
        response = await api_client.post(
            "/search",
            json={"query": "Python programming", "limit": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "query" in data

    async def test_search_with_mode_bm25(
        self, api_client: AsyncClient, seeded_db: Database
    ):
        """Test BM25-only search mode."""
        response = await api_client.post(
            "/search",
            json={"query": "integration test", "mode": "bm25", "limit": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "bm25"

    async def test_empty_query_rejected(self, api_client: AsyncClient):
        """Test empty query is rejected."""
        response = await api_client.post(
            "/search",
            json={"query": "", "limit": 10},
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.integration
class TestContentAPIIntegration:
    """Integration tests for content endpoints."""

    @pytest.mark.skip(reason="Content creation API endpoint not implemented - use CLI/ingestion")
    async def test_create_content_endpoint(
        self, api_client: AsyncClient, clean_db: Database
    ):
        """Test content creation via API."""
        # Note: Content creation is done via CLI ingestion, not API
        pass

    async def test_get_content_endpoint(
        self, api_client: AsyncClient, seeded_db: Database
    ):
        """Test content retrieval via API."""
        # First get list of content
        list_response = await api_client.get("/content")
        assert list_response.status_code == 200

        data = list_response.json()
        if data["items"]:
            content_id = data["items"][0]["id"]

            # Get specific content
            response = await api_client.get(f"/content/{content_id}")
            assert response.status_code == 200

    async def test_delete_content_endpoint(
        self, api_client: AsyncClient, seeded_db: Database
    ):
        """Test content deletion via API using seeded content."""
        # Get seeded content
        list_response = await api_client.get("/content")
        assert list_response.status_code == 200

        data = list_response.json()
        assert len(data["items"]) > 0, "Seeded DB should have content"
        content_id = data["items"][0]["id"]

        # Delete it
        delete_response = await api_client.delete(f"/content/{content_id}")
        assert delete_response.status_code == 200

        # Verify deleted
        get_response = await api_client.get(f"/content/{content_id}")
        assert get_response.status_code == 404


@pytest.mark.integration
class TestHealthAPIIntegration:
    """Integration tests for health endpoints."""

    async def test_health_endpoint(self, api_client: AsyncClient):
        """Test health endpoint returns status."""
        response = await api_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data

    async def test_ready_endpoint(self, api_client: AsyncClient, clean_db: Database):
        """Test readiness endpoint."""
        response = await api_client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] is True


@pytest.mark.integration
class TestBatchAPIIntegration:
    """Integration tests for batch endpoints."""

    async def test_batch_search(
        self, api_client: AsyncClient, seeded_db: Database
    ):
        """Test batch search endpoint."""
        response = await api_client.post(
            "/api/v1/batch/search",
            json={
                "queries": [
                    {"query": "Python", "limit": 5},
                    {"query": "machine learning", "limit": 5},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_queries"] == 2
        assert len(data["results"]) == 2


@pytest.mark.integration
class TestRateLimiting:
    """Integration tests for rate limiting."""

    async def test_rate_limit_headers_present(
        self, api_client: AsyncClient, seeded_db: Database
    ):
        """Test rate limit headers are in response."""
        response = await api_client.post(
            "/search",
            json={"query": "test", "limit": 1},
        )

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
