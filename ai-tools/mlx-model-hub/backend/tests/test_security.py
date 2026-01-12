"""Tests for security middleware and utilities."""

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from mlx_hub.security import (
    APIKeyAuthMiddleware,
    is_public_endpoint,
    validate_model_id,
    validate_path_safety,
)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear settings cache before and after each test."""
    from mlx_hub.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestPublicEndpoints:
    """Tests for public endpoint detection."""

    def test_health_is_public(self):
        """Health endpoints should be public."""
        assert is_public_endpoint("/health") is True
        assert is_public_endpoint("/health/live") is True
        assert is_public_endpoint("/health/ready") is True

    def test_metrics_is_public(self):
        """Metrics endpoint should be public."""
        assert is_public_endpoint("/metrics") is True

    def test_docs_are_public(self):
        """Documentation endpoints should be public."""
        assert is_public_endpoint("/docs") is True
        assert is_public_endpoint("/redoc") is True
        assert is_public_endpoint("/openapi.json") is True

    def test_api_endpoints_not_public(self):
        """API endpoints should not be public."""
        assert is_public_endpoint("/api/models") is False
        assert is_public_endpoint("/api/training/jobs") is False
        assert is_public_endpoint("/v1/chat/completions") is False


class TestModelIdValidation:
    """Tests for model ID validation."""

    def test_valid_model_ids(self):
        """Valid model IDs should pass validation."""
        assert validate_model_id("mlx-community/Llama-3.2-3B-4bit") is True
        assert validate_model_id("meta-llama/Llama-2-7b-chat") is True
        assert validate_model_id("mistralai/Mistral-7B-v0.1") is True
        assert validate_model_id("Qwen/Qwen2.5-7B") is True
        assert validate_model_id("owner/model_name") is True
        assert validate_model_id("owner/model.name") is True

    def test_invalid_model_ids_no_slash(self):
        """Model IDs without slash should fail."""
        assert validate_model_id("justmodelname") is False
        assert validate_model_id("") is False

    def test_invalid_model_ids_multiple_slashes(self):
        """Model IDs with multiple slashes should fail."""
        assert validate_model_id("org/sub/model") is False
        assert validate_model_id("a/b/c") is False

    def test_invalid_model_ids_special_chars(self):
        """Model IDs with special characters should fail."""
        assert validate_model_id("owner/model;drop") is False
        assert validate_model_id("owner/model<script>") is False
        assert validate_model_id("owner/../model") is False
        assert validate_model_id("owner/model name") is False

    def test_invalid_model_ids_too_long(self):
        """Model IDs that are too long should fail."""
        long_id = "a" * 128 + "/" + "b" * 128
        assert validate_model_id(long_id) is False

    def test_none_and_empty(self):
        """None and empty strings should fail."""
        assert validate_model_id("") is False
        # Note: validate_model_id doesn't accept None, would raise TypeError


class TestPathSafety:
    """Tests for path safety validation."""

    def test_valid_path_under_base(self, tmp_path):
        """Paths under base directory should be valid."""
        base = tmp_path / "models"
        base.mkdir()
        target = base / "mymodel"

        assert validate_path_safety(str(target), str(base)) is True

    def test_valid_nested_path(self, tmp_path):
        """Nested paths under base should be valid."""
        base = tmp_path / "models"
        base.mkdir()
        target = base / "org" / "model" / "v1"

        assert validate_path_safety(str(target), str(base)) is True

    def test_invalid_path_traversal(self, tmp_path):
        """Path traversal attempts should be blocked."""
        base = tmp_path / "models"
        base.mkdir()
        target = base / ".." / "secrets"

        assert validate_path_safety(str(target), str(base)) is False

    def test_invalid_absolute_escape(self, tmp_path):
        """Absolute paths outside base should be blocked."""
        base = tmp_path / "models"
        base.mkdir()

        assert validate_path_safety("/etc/passwd", str(base)) is False
        assert validate_path_safety("/tmp/evil", str(base)) is False

    def test_same_directory_is_valid(self, tmp_path):
        """Base directory itself should be valid."""
        base = tmp_path / "models"
        base.mkdir()

        assert validate_path_safety(str(base), str(base)) is True


class TestAPIKeyAuthMiddleware:
    """Tests for API key authentication middleware."""

    @pytest.fixture
    def app_with_auth(self):
        """Create a test app with auth middleware."""
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware)

        @app.get("/api/test")
        async def protected_endpoint():
            return {"message": "success"}

        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}

        return app

    def test_public_endpoint_no_auth_required(self, app_with_auth, monkeypatch):
        """Public endpoints should not require authentication."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("API_KEY", "test-key-123")

        # Clear settings cache
        from mlx_hub.config import get_settings

        get_settings.cache_clear()

        client = TestClient(app_with_auth)
        response = client.get("/health")

        # Health is public, should work without API key
        assert response.status_code == status.HTTP_200_OK

    def test_auth_disabled_allows_all(self, app_with_auth, monkeypatch):
        """When auth is disabled, all requests should pass."""
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        from mlx_hub.config import get_settings

        get_settings.cache_clear()

        client = TestClient(app_with_auth)
        response = client.get("/api/test")

        assert response.status_code == status.HTTP_200_OK

    def test_missing_api_key_rejected(self, app_with_auth, monkeypatch):
        """Requests without API key should be rejected when auth enabled."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("API_KEY", "test-key-123")

        from mlx_hub.config import get_settings

        get_settings.cache_clear()

        client = TestClient(app_with_auth)
        response = client.get("/api/test")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing API key" in response.text

    def test_invalid_api_key_rejected(self, app_with_auth, monkeypatch):
        """Requests with invalid API key should be rejected."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("API_KEY", "correct-key")

        from mlx_hub.config import get_settings

        get_settings.cache_clear()

        client = TestClient(app_with_auth)
        response = client.get("/api/test", headers={"X-API-Key": "wrong-key"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid API key" in response.text

    def test_valid_api_key_accepted(self, app_with_auth, monkeypatch):
        """Requests with valid API key should be accepted."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("API_KEY", "correct-key")

        from mlx_hub.config import get_settings

        get_settings.cache_clear()

        client = TestClient(app_with_auth)
        response = client.get("/api/test", headers={"X-API-Key": "correct-key"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "success"}
