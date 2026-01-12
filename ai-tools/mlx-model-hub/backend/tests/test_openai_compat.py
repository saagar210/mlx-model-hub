"""Tests for OpenAI-compatible API endpoints."""

import urllib.parse

import pytest
from httpx import AsyncClient


@pytest.fixture
async def test_model(async_client: AsyncClient):
    """Create a test model via API."""
    response = await async_client.post(
        "/api/models",
        json={
            "name": "test-model-openai",
            "base_model": "mlx-community/Llama-3.2-1B-Instruct-4bit",
            "task_type": "text-generation",
            "description": "Test model for OpenAI compat",
            "tags": {"test": "true"},
        },
    )
    assert response.status_code == 201
    return response.json()


class TestOpenAIModelsEndpoint:
    """Tests for /v1/models endpoint."""

    @pytest.mark.asyncio
    async def test_list_models(self, async_client: AsyncClient, test_model):
        """Test listing models in OpenAI format."""
        response = await async_client.get("/v1/models")
        assert response.status_code == 200

        data = response.json()
        assert data["object"] == "list"
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1

        # Check model format
        model_info = data["data"][0]
        assert "id" in model_info
        assert model_info["object"] == "model"
        assert "created" in model_info
        assert "owned_by" in model_info

    @pytest.mark.asyncio
    async def test_get_model_by_name(self, async_client: AsyncClient, test_model):
        """Test getting a specific model by name."""
        response = await async_client.get(f"/v1/models/{test_model['name']}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == test_model["name"]
        assert data["object"] == "model"
        assert data["owned_by"] == "mlx-hub"

    @pytest.mark.asyncio
    async def test_get_unknown_model(self, async_client: AsyncClient):
        """Test getting an unknown model returns generic info."""
        response = await async_client.get("/v1/models/some-unknown-model")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == "some-unknown-model"
        assert data["owned_by"] == "huggingface"


class TestChatCompletionsEndpoint:
    """Tests for /v1/chat/completions endpoint."""

    @pytest.mark.asyncio
    async def test_chat_completion_request_validation(self, async_client: AsyncClient):
        """Test chat completion request validation."""
        # Missing required fields
        response = await async_client.post(
            "/v1/chat/completions",
            json={},
        )
        assert response.status_code == 422

        # Missing messages
        response = await async_client.post(
            "/v1/chat/completions",
            json={"model": "test"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires MLX hardware for inference")
    async def test_chat_completion_valid_request_shape(
        self, async_client: AsyncClient, test_model
    ):
        """Test that a valid request has the right shape.

        Note: This test requires actual MLX hardware to run inference.
        """
        response = await async_client.post(
            "/v1/chat/completions",
            json={
                "model": test_model["name"],
                "messages": [{"role": "user", "content": "Hello!"}],
                "max_tokens": 10,
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_completion_temperature_range(
        self, async_client: AsyncClient, test_model
    ):
        """Test temperature validation."""
        # Temperature too high
        response = await async_client.post(
            "/v1/chat/completions",
            json={
                "model": test_model["name"],
                "messages": [{"role": "user", "content": "Hi"}],
                "temperature": 3.0,  # Max is 2.0
            },
        )
        assert response.status_code == 422

        # Temperature too low
        response = await async_client.post(
            "/v1/chat/completions",
            json={
                "model": test_model["name"],
                "messages": [{"role": "user", "content": "Hi"}],
                "temperature": -0.5,  # Min is 0.0
            },
        )
        assert response.status_code == 422


class TestCompletionsEndpoint:
    """Tests for /v1/completions endpoint."""

    @pytest.mark.asyncio
    async def test_completion_request_validation(self, async_client: AsyncClient):
        """Test completion request validation."""
        # Missing required fields
        response = await async_client.post(
            "/v1/completions",
            json={},
        )
        assert response.status_code == 422

        # Missing prompt
        response = await async_client.post(
            "/v1/completions",
            json={"model": "test"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires MLX hardware for inference")
    async def test_completion_valid_request_shape(
        self, async_client: AsyncClient, test_model
    ):
        """Test that a valid request has the right shape."""
        response = await async_client.post(
            "/v1/completions",
            json={
                "model": test_model["name"],
                "prompt": "Once upon a time",
                "max_tokens": 10,
            },
        )
        assert response.status_code == 200


class TestModelResolution:
    """Tests for model ID resolution."""

    @pytest.mark.asyncio
    async def test_resolve_by_uuid(self, async_client: AsyncClient, test_model):
        """Test resolving model by UUID."""
        response = await async_client.get(f"/v1/models/{str(test_model["id"])}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_model["name"]

    @pytest.mark.asyncio
    async def test_resolve_by_name(self, async_client: AsyncClient, test_model):
        """Test resolving model by name."""
        response = await async_client.get(f"/v1/models/{test_model["name"]}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_model["name"]

    @pytest.mark.asyncio
    async def test_resolve_unknown_model(self, async_client: AsyncClient):
        """Test resolving an unknown model returns HuggingFace placeholder."""
        # Unknown models return a placeholder pointing to HuggingFace
        response = await async_client.get("/v1/models/some-model-not-in-db")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "some-model-not-in-db"
        assert data["owned_by"] == "huggingface"
