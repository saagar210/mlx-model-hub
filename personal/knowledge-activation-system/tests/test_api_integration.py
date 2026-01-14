"""API Integration tests for KAS.

Tests all API endpoints with mocked dependencies to enable CI testing
without requiring PostgreSQL or Ollama services.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from knowledge.api.main import app
from knowledge.config import Settings


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    return Settings(
        database_url="postgresql://test:test@localhost:5432/test",
        ollama_url="http://localhost:11434",
        embedding_model="nomic-embed-text",
        vault_path="/tmp/test_vault",
        knowledge_folder="Knowledge",
    )


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a comprehensive mock database."""
    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    mock.check_health = AsyncMock(
        return_value={
            "status": "healthy",
            "extensions": ["vector", "vectorscale"],
            "content_count": 10,
            "chunk_count": 50,
        }
    )
    mock.bm25_search = AsyncMock(return_value=[])
    mock.vector_search = AsyncMock(return_value=[])
    mock.get_stats = AsyncMock(
        return_value={
            "content_by_type": {"youtube": 5, "bookmark": 3, "file": 2},
            "total_content": 10,
            "total_chunks": 50,
            "review_active": 8,
            "review_due": 2,
        }
    )

    # Mock connection context manager
    conn_mock = MagicMock()
    conn_mock.fetch = AsyncMock(return_value=[])
    conn_mock.fetchrow = AsyncMock(return_value={"count": 0})
    conn_mock.fetchval = AsyncMock(return_value=1)
    conn_mock.execute = AsyncMock()

    mock.acquire.return_value.__aenter__ = AsyncMock(return_value=conn_mock)
    mock.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    return mock


@pytest.fixture
def mock_ollama_healthy() -> MagicMock:
    """Mock healthy Ollama status."""
    from knowledge.embeddings import OllamaStatus

    return OllamaStatus(
        healthy=True,
        models_loaded=["nomic-embed-text:latest", "mxbai-rerank-base-v1:latest"],
    )


@pytest.fixture
def mock_embedding() -> list[float]:
    """Create deterministic mock embedding."""
    import random
    random.seed(42)
    return [random.random() for _ in range(768)]


@pytest.fixture
def client(mock_db: MagicMock, mock_ollama_healthy: Any, mock_settings: Settings) -> TestClient:
    """Create test client with mocked dependencies."""
    # Mock the HybridSearchResponse for the search route
    from knowledge.search import HybridSearchResponse
    mock_search_response = HybridSearchResponse(results=[], degraded=False, search_mode="hybrid")

    with patch("knowledge.api.routes.health.get_db", AsyncMock(return_value=mock_db)), \
         patch("knowledge.api.routes.health._check_ollama", AsyncMock(return_value=mock_ollama_healthy)), \
         patch("knowledge.api.routes.content.get_db", AsyncMock(return_value=mock_db)), \
         patch("knowledge.api.routes.search.hybrid_search_with_status", AsyncMock(return_value=mock_search_response)), \
         patch("knowledge.api.routes.search.search_bm25_only", AsyncMock(return_value=[])), \
         patch("knowledge.api.routes.search.search_vector_only", AsyncMock(return_value=[])), \
         patch("knowledge.reranker.preload_reranker", AsyncMock()):
        yield TestClient(app)


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_returns_api_info(self, client: TestClient):
        """Test root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert data["name"] == "Knowledge Activation System API"


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_returns_status(self, client: TestClient):
        """Test health endpoint returns service statuses."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "components" in data
        assert isinstance(data["components"], list)
        # New health response includes version, uptime, and system metrics
        assert "version" in data
        assert "uptime_seconds" in data
        assert "system" in data

    def test_liveness_probe(self, client: TestClient):
        """Test Kubernetes liveness probe."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness_probe(self, client: TestClient, mock_db: MagicMock):
        """Test Kubernetes readiness probe."""
        with patch("knowledge.api.routes.health.get_db", AsyncMock(return_value=mock_db)):
            response = client.get("/health/ready")
            assert response.status_code == 200

            data = response.json()
            assert "status" in data
            assert "database" in data

    def test_stats_endpoint(self, client: TestClient, mock_db: MagicMock):
        """Test stats endpoint returns database statistics."""
        with patch("knowledge.api.routes.health.get_db", AsyncMock(return_value=mock_db)):
            response = client.get("/stats")
            assert response.status_code == 200

            data = response.json()
            assert "total_content" in data
            assert "total_chunks" in data
            assert "content_by_type" in data
            assert "review_active" in data
            assert "review_due" in data


class TestSearchEndpoints:
    """Tests for search endpoints."""

    def test_search_hybrid_empty_results(self, client: TestClient):
        """Test hybrid search with no results."""
        response = client.post("/search", json={
            "query": "test query",
            "limit": 10,
            "mode": "hybrid",
        })
        assert response.status_code == 200

        data = response.json()
        assert data["query"] == "test query"
        assert data["results"] == []
        assert data["total"] == 0
        assert data["mode"] == "hybrid"

    def test_search_bm25_mode(self, client: TestClient):
        """Test BM25-only search mode."""
        response = client.post("/search", json={
            "query": "test query",
            "limit": 10,
            "mode": "bm25",
        })
        assert response.status_code == 200

        data = response.json()
        assert data["mode"] == "bm25"

    def test_search_vector_mode(self, client: TestClient):
        """Test vector-only search mode."""
        response = client.post("/search", json={
            "query": "test query",
            "limit": 10,
            "mode": "vector",
        })
        assert response.status_code == 200

        data = response.json()
        assert data["mode"] == "vector"

    def test_search_with_results(self, client: TestClient, mock_embedding: list[float]):
        """Test search returning actual results."""
        from knowledge.search import SearchResult, HybridSearchResponse

        mock_results = [
            SearchResult(
                content_id=uuid4(),
                title="Test Result",
                content_type="youtube",
                score=0.85,
                chunk_text="This is a test chunk",
                bm25_rank=1,
                vector_rank=2,
            )
        ]
        mock_response = HybridSearchResponse(
            results=mock_results,
            degraded=False,
            search_mode="hybrid",
        )

        with patch("knowledge.api.routes.search.hybrid_search_with_status", AsyncMock(return_value=mock_response)):
            response = client.post("/search", json={
                "query": "test query",
                "limit": 10,
                "mode": "hybrid",
            })
            assert response.status_code == 200

            data = response.json()
            assert data["total"] == 1
            assert len(data["results"]) == 1
            assert data["results"][0]["title"] == "Test Result"
            assert data["results"][0]["score"] == 0.85
            assert data["degraded"] is False
            assert data["search_mode"] == "hybrid"


class TestContentEndpoints:
    """Tests for content management endpoints."""

    def test_list_content_empty(self, client: TestClient, mock_db: MagicMock):
        """Test listing content with no items."""
        with patch("knowledge.api.routes.content.get_db", AsyncMock(return_value=mock_db)):
            response = client.get("/content")
            assert response.status_code == 200

            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data
            assert data["items"] == []

    def test_list_content_with_pagination(self, client: TestClient, mock_db: MagicMock):
        """Test content listing with pagination parameters."""
        with patch("knowledge.api.routes.content.get_db", AsyncMock(return_value=mock_db)):
            response = client.get("/content?page=2&page_size=5")
            assert response.status_code == 200

            data = response.json()
            assert data["page"] == 2
            assert data["page_size"] == 5

    def test_list_content_with_type_filter(self, client: TestClient, mock_db: MagicMock):
        """Test content listing with type filter."""
        with patch("knowledge.api.routes.content.get_db", AsyncMock(return_value=mock_db)):
            response = client.get("/content?content_type=youtube")
            assert response.status_code == 200

    def test_get_content_not_found(self, client: TestClient, mock_db: MagicMock):
        """Test getting non-existent content."""
        mock_db.get_content_by_id = AsyncMock(return_value=None)

        with patch("knowledge.api.routes.content.get_db", AsyncMock(return_value=mock_db)):
            response = client.get(f"/content/{uuid4()}")
            assert response.status_code == 404

    def test_delete_content_not_found(self, client: TestClient, mock_db: MagicMock):
        """Test deleting non-existent content."""
        mock_db.get_content_by_id = AsyncMock(return_value=None)

        with patch("knowledge.api.routes.content.get_db", AsyncMock(return_value=mock_db)):
            response = client.delete(f"/content/{uuid4()}")
            assert response.status_code == 404


class TestReviewEndpoints:
    """Tests for review/spaced repetition endpoints."""

    def test_get_due_reviews(self, client: TestClient):
        """Test getting due reviews."""
        with patch("knowledge.api.routes.review.get_due_items", AsyncMock(return_value=[])):
            response = client.get("/review/due")
            assert response.status_code == 200

            data = response.json()
            assert "items" in data
            assert "total" in data
            assert data["total"] == 0

    def test_get_review_stats(self, client: TestClient):
        """Test getting review statistics."""
        mock_stats = {
            "total_active": 10,
            "due_now": 3,
            "new": 2,
            "learning": 1,
            "review": 7,
        }

        with patch("knowledge.api.routes.review.get_review_stats_simple", AsyncMock(return_value=mock_stats)):
            response = client.get("/review/stats")
            assert response.status_code == 200

            data = response.json()
            assert data["total_active"] == 10
            assert data["due_now"] == 3

    def test_add_to_review_queue(self, client: TestClient):
        """Test adding item to review queue."""
        content_id = uuid4()

        with patch("knowledge.api.routes.review.add_to_review_queue", AsyncMock(return_value=True)):
            response = client.post(f"/review/{content_id}/add")
            assert response.status_code == 200
            assert response.json()["status"] == "added"

    def test_add_to_queue_already_exists(self, client: TestClient):
        """Test adding item that's already in queue."""
        content_id = uuid4()

        with patch("knowledge.api.routes.review.add_to_review_queue", AsyncMock(return_value=False)):
            response = client.post(f"/review/{content_id}/add")
            assert response.status_code == 409  # Conflict

    def test_submit_review_not_found(self, client: TestClient):
        """Test submitting review for non-existent item."""
        content_id = uuid4()

        with patch("knowledge.api.routes.review.submit_review", AsyncMock(return_value=None)):
            response = client.post(
                f"/review/{content_id}",
                json={"rating": "good"}
            )
            assert response.status_code == 404


class TestCORSConfiguration:
    """Tests for CORS middleware configuration."""

    def test_cors_allows_localhost_3001(self, client: TestClient):
        """Test CORS allows LocalCrew dashboard origin."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3001",
                "Access-Control-Request-Method": "GET",
            }
        )
        # OPTIONS returns 200 for allowed origins
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3001"

    def test_cors_allows_localhost_3000(self, client: TestClient):
        """Test CORS allows KAS frontend origin."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_allows_credentials(self, client: TestClient):
        """Test CORS allows credentials."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3001",
                "Access-Control-Request-Method": "GET",
            }
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_allows_api_key_header(self, client: TestClient):
        """Test CORS allows custom API key header."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3001",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            }
        )
        assert response.status_code == 200
        allowed_headers = response.headers.get("access-control-allow-headers", "")
        # Either allows all (*) or specifically includes the header
        assert "*" in allowed_headers or "x-api-key" in allowed_headers.lower()


class TestErrorHandling:
    """Tests for API error handling."""

    def test_search_handles_internal_error(self, client: TestClient):
        """Test search endpoint handles internal errors gracefully."""
        with patch(
            "knowledge.api.routes.search.hybrid_search_with_status",
            AsyncMock(side_effect=Exception("Database connection failed"))
        ):
            response = client.post("/search", json={
                "query": "test",
                "limit": 10,
                "mode": "hybrid",
            })
            assert response.status_code == 500
            assert "Database connection failed" in response.json()["detail"]

    def test_invalid_search_mode(self, client: TestClient):
        """Test search with invalid mode."""
        response = client.post("/search", json={
            "query": "test",
            "limit": 10,
            "mode": "invalid_mode",
        })
        assert response.status_code == 422  # Validation error

    def test_invalid_pagination(self, client: TestClient, mock_db: MagicMock):
        """Test content list with invalid pagination."""
        with patch("knowledge.api.routes.content.get_db", AsyncMock(return_value=mock_db)):
            response = client.get("/content?page=0")  # page must be >= 1
            assert response.status_code == 422

    def test_invalid_uuid(self, client: TestClient):
        """Test endpoints with invalid UUID."""
        response = client.get("/content/not-a-uuid")
        assert response.status_code == 422


class TestIntegrationWithMockedServices:
    """Integration tests with fully mocked external services."""

    def test_full_search_flow(self, client: TestClient, mock_embedding: list[float]):
        """Test complete search flow: query -> search -> results."""
        from knowledge.search import SearchResult, HybridSearchResponse

        content_id = uuid4()
        mock_results = [
            SearchResult(
                content_id=content_id,
                title="Machine Learning Basics",
                content_type="youtube",
                score=0.92,
                chunk_text="Machine learning is a subset of AI that enables...",
                bm25_rank=1,
                vector_rank=1,
            ),
            SearchResult(
                content_id=uuid4(),
                title="Deep Learning Guide",
                content_type="bookmark",
                score=0.85,
                chunk_text="Deep learning uses neural networks with multiple layers...",
                bm25_rank=2,
                vector_rank=3,
            ),
        ]
        mock_response = HybridSearchResponse(
            results=mock_results,
            degraded=False,
            search_mode="hybrid",
        )

        with patch("knowledge.api.routes.search.hybrid_search_with_status", AsyncMock(return_value=mock_response)):
            response = client.post("/search", json={
                "query": "machine learning basics",
                "limit": 10,
                "mode": "hybrid",
            })

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 2
            assert data["results"][0]["title"] == "Machine Learning Basics"
            assert data["results"][0]["score"] == 0.92
            assert data["results"][0]["content_type"] == "youtube"

    def test_health_aggregates_service_status(
        self,
        client: TestClient,
        mock_db: MagicMock,
        mock_ollama_healthy: Any
    ):
        """Test health endpoint aggregates all service statuses."""
        with patch("knowledge.api.routes.health.get_db", AsyncMock(return_value=mock_db)), \
             patch("knowledge.api.routes.health._check_ollama", AsyncMock(return_value=mock_ollama_healthy)):
            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "healthy"

            # Should have database and ollama components
            component_names = [c["name"] for c in data["components"]]
            assert "database" in component_names
            assert "ollama" in component_names

            # All components should be healthy
            for component in data["components"]:
                assert component["status"] == "healthy"

    def test_health_reports_degraded_when_ollama_down(
        self,
        client: TestClient,
        mock_db: MagicMock
    ):
        """Test health endpoint reports degraded when Ollama is down.

        Note: Ollama being down is a degraded state, not unhealthy,
        because the system can still function with BM25-only search.
        """
        from knowledge.embeddings import OllamaStatus

        unhealthy_ollama = OllamaStatus(
            healthy=False,
            error="Connection refused",
            models_loaded=[],
        )

        with patch("knowledge.api.routes.health.get_db", AsyncMock(return_value=mock_db)), \
             patch("knowledge.api.routes.health._check_ollama", AsyncMock(return_value=unhealthy_ollama)):
            # Clear health cache to get fresh result
            import knowledge.api.routes.health as health_module
            health_module._health_cache = None

            response = client.get("/health")
            assert response.status_code == 200

            data = response.json()
            # Ollama down = degraded (not unhealthy) because system still works
            assert data["status"] == "degraded"

            # Find Ollama component
            ollama_component = next(c for c in data["components"] if c["name"] == "ollama")
            assert ollama_component["status"] == "degraded"


# =============================================================================
# Batch Operations Tests
# =============================================================================


class TestBatchSearchEndpoint:
    """Tests for batch search endpoint."""

    def test_batch_search_single_query(self, client: TestClient):
        """Test batch search with single query."""
        from knowledge.search import HybridSearchResponse

        mock_response = HybridSearchResponse(results=[], degraded=False, search_mode="hybrid")

        with patch("knowledge.api.routes.batch.hybrid_search_with_status", AsyncMock(return_value=mock_response)):
            response = client.post("/api/v1/batch/search", json={
                "queries": [
                    {"query": "test query", "limit": 10, "mode": "hybrid"}
                ]
            })
            assert response.status_code == 200

            data = response.json()
            assert data["total_queries"] == 1
            assert data["succeeded"] == 1
            assert data["failed"] == 0
            assert len(data["results"]) == 1

    def test_batch_search_multiple_queries(self, client: TestClient):
        """Test batch search with multiple queries."""
        from knowledge.search import HybridSearchResponse, SearchResult

        mock_response = HybridSearchResponse(
            results=[
                SearchResult(
                    content_id=uuid4(),
                    title="Test",
                    content_type="youtube",
                    score=0.8,
                )
            ],
            degraded=False,
            search_mode="hybrid",
        )

        with patch("knowledge.api.routes.batch.hybrid_search_with_status", AsyncMock(return_value=mock_response)), \
             patch("knowledge.api.routes.batch.search_bm25_only", AsyncMock(return_value=[])), \
             patch("knowledge.api.routes.batch.search_vector_only", AsyncMock(return_value=[])):
            response = client.post("/api/v1/batch/search", json={
                "queries": [
                    {"query": "python tutorial", "limit": 5, "mode": "hybrid"},
                    {"query": "fastapi guide", "limit": 5, "mode": "bm25"},
                    {"query": "machine learning", "limit": 5, "mode": "vector"},
                ]
            })
            assert response.status_code == 200

            data = response.json()
            assert data["total_queries"] == 3
            assert data["succeeded"] == 3
            assert data["failed"] == 0

    def test_batch_search_max_queries_limit(self, client: TestClient):
        """Test batch search respects max queries limit."""
        # More than 10 queries should fail validation
        queries = [{"query": f"test {i}", "limit": 5, "mode": "hybrid"} for i in range(11)]

        response = client.post("/api/v1/batch/search", json={"queries": queries})
        assert response.status_code == 422  # Validation error

    def test_batch_search_empty_queries(self, client: TestClient):
        """Test batch search with empty queries list."""
        response = client.post("/api/v1/batch/search", json={"queries": []})
        assert response.status_code == 422  # Validation error

    def test_batch_search_handles_partial_failure(self, client: TestClient):
        """Test batch search handles partial failures gracefully."""
        from knowledge.search import HybridSearchResponse

        call_count = [0]

        async def mock_search(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Search failed")
            return HybridSearchResponse(results=[], degraded=False, search_mode="hybrid")

        with patch("knowledge.api.routes.batch.hybrid_search_with_status", AsyncMock(side_effect=mock_search)):
            response = client.post("/api/v1/batch/search", json={
                "queries": [
                    {"query": "query1", "limit": 5, "mode": "hybrid"},
                    {"query": "query2", "limit": 5, "mode": "hybrid"},
                    {"query": "query3", "limit": 5, "mode": "hybrid"},
                ]
            })
            assert response.status_code == 200

            data = response.json()
            assert data["total_queries"] == 3
            assert data["succeeded"] == 2
            assert data["failed"] == 1
            assert len(data["errors"]) == 1


class TestBatchDeleteEndpoint:
    """Tests for batch delete endpoint."""

    def test_batch_delete_content(self, client: TestClient, mock_db: MagicMock):
        """Test batch delete content."""
        mock_db.delete_content = AsyncMock(return_value=True)

        with patch("knowledge.api.routes.batch.get_db", AsyncMock(return_value=mock_db)):
            content_ids = [str(uuid4()), str(uuid4())]
            response = client.request("DELETE", "/api/v1/batch/content", json={"ids": content_ids})
            assert response.status_code == 200

            data = response.json()
            assert data["total"] == 2
            assert data["deleted"] == 2
            assert data["not_found"] == 0

    def test_batch_delete_with_not_found(self, client: TestClient, mock_db: MagicMock):
        """Test batch delete handles not found items."""
        # First delete succeeds, second returns not found
        mock_db.delete_content = AsyncMock(side_effect=[True, False])

        with patch("knowledge.api.routes.batch.get_db", AsyncMock(return_value=mock_db)):
            content_ids = [str(uuid4()), str(uuid4())]
            response = client.request("DELETE", "/api/v1/batch/content", json={"ids": content_ids})
            assert response.status_code == 200

            data = response.json()
            assert data["total"] == 2
            assert data["deleted"] == 1
            assert data["not_found"] == 1

    def test_batch_delete_max_ids_limit(self, client: TestClient):
        """Test batch delete respects max IDs limit."""
        # More than 100 IDs should fail validation
        ids = [str(uuid4()) for _ in range(101)]

        response = client.request("DELETE", "/api/v1/batch/content", json={"ids": ids})
        assert response.status_code == 422


# =============================================================================
# Tuning API Tests
# =============================================================================


class TestTuningWeightsEndpoint:
    """Tests for search weight tuning endpoints."""

    def test_get_search_weights(self, client: TestClient):
        """Test getting current search weights."""
        # Reset runtime config first
        import knowledge.api.routes.tuning as tuning_module
        tuning_module._runtime_config.clear()

        response = client.get("/api/v1/tuning/weights")
        assert response.status_code == 200

        data = response.json()
        assert "bm25_weight" in data
        assert "vector_weight" in data
        assert "rrf_k" in data
        assert "query_expansion_enabled" in data
        # Check default values are reasonable
        assert 0 <= data["bm25_weight"] <= 1
        assert 0 <= data["vector_weight"] <= 1
        assert data["rrf_k"] >= 1

    def test_update_search_weights(self, client: TestClient):
        """Test updating search weights."""
        import knowledge.api.routes.tuning as tuning_module
        tuning_module._runtime_config.clear()

        response = client.patch("/api/v1/tuning/weights", json={
            "bm25_weight": 0.7,
            "vector_weight": 0.3,
        })
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "0.7" in data["message"] or "bm25_weight" in data["message"]
        assert data["current"]["bm25_weight"] == 0.7
        assert data["current"]["vector_weight"] == 0.3

    def test_update_weights_validation(self, client: TestClient):
        """Test weight update validation."""
        # Weight > 1 should fail
        response = client.patch("/api/v1/tuning/weights", json={
            "bm25_weight": 1.5,
        })
        assert response.status_code == 422

        # Weight < 0 should fail
        response = client.patch("/api/v1/tuning/weights", json={
            "vector_weight": -0.1,
        })
        assert response.status_code == 422

    def test_update_weights_no_changes(self, client: TestClient):
        """Test update with no changes specified."""
        response = client.patch("/api/v1/tuning/weights", json={})
        assert response.status_code == 400
        assert "No changes" in response.json()["detail"]

    def test_reset_search_weights(self, client: TestClient):
        """Test resetting search weights to defaults."""
        import knowledge.api.routes.tuning as tuning_module

        # First set some custom values
        tuning_module._runtime_config["search_bm25_weight"] = 0.9
        tuning_module._runtime_config["rrf_k"] = 30

        # Then reset
        response = client.post("/api/v1/tuning/weights/reset")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "reset" in data["message"].lower()

        # Config should be cleared
        assert "search_bm25_weight" not in tuning_module._runtime_config
        assert "rrf_k" not in tuning_module._runtime_config

    def test_update_rrf_k(self, client: TestClient):
        """Test updating RRF constant."""
        import knowledge.api.routes.tuning as tuning_module
        tuning_module._runtime_config.clear()

        response = client.patch("/api/v1/tuning/weights", json={
            "rrf_k": 80,
        })
        assert response.status_code == 200
        assert response.json()["current"]["rrf_k"] == 80

    def test_update_query_expansion(self, client: TestClient):
        """Test enabling/disabling query expansion."""
        import knowledge.api.routes.tuning as tuning_module
        tuning_module._runtime_config.clear()

        response = client.patch("/api/v1/tuning/weights", json={
            "query_expansion_enabled": False,
        })
        assert response.status_code == 200
        assert response.json()["current"]["query_expansion_enabled"] is False


class TestTuningCacheEndpoint:
    """Tests for cache TTL tuning endpoints."""

    def test_get_cache_ttl(self, client: TestClient):
        """Test getting cache TTL configuration."""
        import knowledge.api.routes.tuning as tuning_module
        tuning_module._runtime_config.clear()

        response = client.get("/api/v1/tuning/cache")
        assert response.status_code == 200

        data = response.json()
        assert "search_ttl" in data
        assert "embedding_ttl" in data
        assert "rerank_ttl" in data

    def test_update_cache_ttl(self, client: TestClient):
        """Test updating cache TTLs."""
        import knowledge.api.routes.tuning as tuning_module
        tuning_module._runtime_config.clear()

        response = client.patch("/api/v1/tuning/cache", json={
            "search_ttl": 600,
            "embedding_ttl": 43200,
        })
        assert response.status_code == 200

        data = response.json()
        assert data["search_ttl"] == 600
        assert data["embedding_ttl"] == 43200

    def test_update_cache_ttl_validation(self, client: TestClient):
        """Test cache TTL validation bounds."""
        # TTL > max should fail
        response = client.patch("/api/v1/tuning/cache", json={
            "search_ttl": 100000,  # > 86400
        })
        assert response.status_code == 422

    def test_get_all_tuning(self, client: TestClient):
        """Test getting all tunable configuration."""
        import knowledge.api.routes.tuning as tuning_module
        tuning_module._runtime_config.clear()

        response = client.get("/api/v1/tuning/all")
        assert response.status_code == 200

        data = response.json()
        assert "search" in data
        assert "cache" in data
        assert "bm25_weight" in data["search"]
        assert "search_ttl" in data["cache"]


# =============================================================================
# Export API Tests
# =============================================================================


class TestExportEndpoints:
    """Tests for export/import endpoints."""

    def test_export_json_format(self, client: TestClient, mock_db: MagicMock):
        """Test JSON export format."""
        # Mock iterate to return empty results
        async def mock_iterate(*args, **kwargs):
            return
            yield  # Make it an async generator

        mock_db.iterate = mock_iterate

        with patch("knowledge.api.routes.export.get_db", AsyncMock(return_value=mock_db)):
            response = client.post("/api/v1/export", json={
                "format": "json",
                "include_chunks": True,
            })
            assert response.status_code == 200
            assert "application/json" in response.headers["content-type"]

            data = response.json()
            assert "metadata" in data
            assert "items" in data
            assert data["metadata"]["version"] == "1.0"

    def test_export_jsonl_format(self, client: TestClient, mock_db: MagicMock):
        """Test JSONL export format."""
        async def mock_iterate(*args, **kwargs):
            return
            yield

        mock_db.iterate = mock_iterate

        with patch("knowledge.api.routes.export.get_db", AsyncMock(return_value=mock_db)):
            response = client.post("/api/v1/export", json={
                "format": "jsonl",
            })
            assert response.status_code == 200
            assert "ndjson" in response.headers["content-type"]

    def test_export_with_namespace_filter(self, client: TestClient, mock_db: MagicMock):
        """Test export with namespace filter."""
        async def mock_iterate(*args, **kwargs):
            return
            yield

        mock_db.iterate = mock_iterate

        with patch("knowledge.api.routes.export.get_db", AsyncMock(return_value=mock_db)):
            response = client.post("/api/v1/export", json={
                "format": "json",
                "namespace": "project-a",
            })
            assert response.status_code == 200

            data = response.json()
            assert data["metadata"]["namespace"] == "project-a"

    def test_import_json_file(self, client: TestClient, mock_db: MagicMock):
        """Test importing JSON backup file."""
        import io

        mock_db.fetchrow = AsyncMock(return_value=None)  # Item doesn't exist
        mock_db.execute = AsyncMock()

        export_data = {
            "metadata": {"version": "1.0", "total_items": 1},
            "items": [
                {
                    "id": str(uuid4()),
                    "title": "Test Item",
                    "content_type": "bookmark",
                    "namespace": "default",
                }
            ]
        }

        with patch("knowledge.api.routes.export.get_db", AsyncMock(return_value=mock_db)):
            response = client.post(
                "/api/v1/export/import",
                files={"file": ("backup.json", io.BytesIO(json.dumps(export_data).encode()), "application/json")},
            )
            assert response.status_code == 200

            data = response.json()
            assert data["total"] == 1

    def test_import_invalid_json(self, client: TestClient):
        """Test importing invalid JSON fails gracefully."""
        import io

        response = client.post(
            "/api/v1/export/import",
            files={"file": ("backup.json", io.BytesIO(b"not valid json"), "application/json")},
        )
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_import_skip_existing(self, client: TestClient, mock_db: MagicMock):
        """Test import skips existing items when skip_existing=true."""
        import io

        content_id = str(uuid4())

        # Item exists
        mock_db.fetchrow = AsyncMock(return_value={"id": content_id})

        export_data = {
            "items": [
                {"id": content_id, "title": "Existing", "content_type": "bookmark", "namespace": "default"}
            ]
        }

        with patch("knowledge.api.routes.export.get_db", AsyncMock(return_value=mock_db)):
            response = client.post(
                "/api/v1/export/import?skip_existing=true",
                files={"file": ("backup.json", io.BytesIO(json.dumps(export_data).encode()), "application/json")},
            )
            assert response.status_code == 200

            data = response.json()
            assert data["total"] == 1
            assert data["skipped"] == 1
            assert data["imported"] == 0


# =============================================================================
# Webhooks API Tests
# =============================================================================


class TestWebhooksEndpoints:
    """Tests for webhook management endpoints."""

    def setup_method(self):
        """Clear webhooks before each test."""
        import knowledge.api.routes.webhooks as webhooks_module
        webhooks_module._webhooks.clear()
        webhooks_module._deliveries.clear()

    def test_create_webhook(self, client: TestClient):
        """Test creating a new webhook."""
        response = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["content.created", "content.updated"],
            "secret": "my-secret-key-12345",
        })
        assert response.status_code == 200

        data = response.json()
        assert "id" in data
        assert data["url"] == "https://example.com/webhook"
        assert data["status"] == "active"
        assert "content.created" in data["events"]
        assert "content.updated" in data["events"]

    def test_create_webhook_invalid_url(self, client: TestClient):
        """Test creating webhook with invalid URL."""
        response = client.post("/api/v1/webhooks", json={
            "url": "not-a-valid-url",
            "events": ["content.created"],
        })
        assert response.status_code == 422

    def test_create_webhook_empty_events(self, client: TestClient):
        """Test creating webhook with no events fails."""
        response = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": [],
        })
        assert response.status_code == 422

    def test_list_webhooks(self, client: TestClient):
        """Test listing all webhooks."""
        # Create a webhook first
        client.post("/api/v1/webhooks", json={
            "url": "https://example.com/hook1",
            "events": ["content.created"],
        })

        response = client.get("/api/v1/webhooks")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["url"] == "https://example.com/hook1"

    def test_get_webhook_by_id(self, client: TestClient):
        """Test getting a specific webhook."""
        # Create first
        create_resp = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["content.created"],
        })
        webhook_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/webhooks/{webhook_id}")
        assert response.status_code == 200
        assert response.json()["id"] == webhook_id

    def test_get_webhook_not_found(self, client: TestClient):
        """Test getting non-existent webhook."""
        response = client.get("/api/v1/webhooks/nonexistent-id")
        assert response.status_code == 404

    def test_update_webhook(self, client: TestClient):
        """Test updating a webhook."""
        # Create first
        create_resp = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["content.created"],
        })
        webhook_id = create_resp.json()["id"]

        response = client.patch(f"/api/v1/webhooks/{webhook_id}", json={
            "url": "https://newurl.com/webhook",
            "events": ["content.deleted"],
        })
        assert response.status_code == 200

        data = response.json()
        assert data["url"] == "https://newurl.com/webhook"
        assert "content.deleted" in data["events"]

    def test_update_webhook_status(self, client: TestClient):
        """Test pausing a webhook."""
        create_resp = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["content.created"],
        })
        webhook_id = create_resp.json()["id"]

        response = client.patch(f"/api/v1/webhooks/{webhook_id}", json={
            "status": "paused",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

    def test_delete_webhook(self, client: TestClient):
        """Test deleting a webhook."""
        create_resp = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["content.created"],
        })
        webhook_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/webhooks/{webhook_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] is True

        # Verify it's gone
        get_resp = client.get(f"/api/v1/webhooks/{webhook_id}")
        assert get_resp.status_code == 404

    def test_delete_webhook_not_found(self, client: TestClient):
        """Test deleting non-existent webhook."""
        response = client.delete("/api/v1/webhooks/nonexistent-id")
        assert response.status_code == 404

    def test_test_webhook(self, client: TestClient):
        """Test sending test event to webhook."""
        import httpx

        create_resp = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["content.created"],
        })
        webhook_id = create_resp.json()["id"]

        # Mock the HTTP request
        with patch("knowledge.api.routes.webhooks.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            response = client.post(f"/api/v1/webhooks/{webhook_id}/test")
            assert response.status_code == 200

            data = response.json()
            assert data["success"] is True
            assert data["status_code"] == 200

    def test_get_webhook_deliveries(self, client: TestClient):
        """Test getting webhook delivery history."""
        create_resp = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["content.created"],
        })
        webhook_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/webhooks/{webhook_id}/deliveries")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_webhook_with_metadata(self, client: TestClient):
        """Test creating webhook with custom metadata."""
        response = client.post("/api/v1/webhooks", json={
            "url": "https://example.com/webhook",
            "events": ["content.created"],
            "metadata": {"project": "kas", "environment": "test"},
        })
        assert response.status_code == 200

        data = response.json()
        assert data["metadata"]["project"] == "kas"
        assert data["metadata"]["environment"] == "test"


# =============================================================================
# Import statement at module level for json
# =============================================================================
import json
