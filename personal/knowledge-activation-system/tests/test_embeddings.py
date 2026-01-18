"""Tests for embeddings module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from knowledge.config import Settings
from knowledge.embeddings import (
    EmbeddingService,
    OllamaStatus,
    check_ollama_health,
    embed_batch,
    embed_text,
)


class TestOllamaStatus:
    """Tests for OllamaStatus dataclass."""

    def test_healthy_status(self):
        """Test creating a healthy status."""
        status = OllamaStatus(
            healthy=True,
            models_loaded=["nomic-embed-text:latest"],
        )
        assert status.healthy is True
        assert status.error is None

    def test_unhealthy_status_with_error(self):
        """Test creating an unhealthy status with error."""
        status = OllamaStatus(
            healthy=False,
            models_loaded=[],
            error="Connection refused",
        )
        assert status.healthy is False
        assert status.error == "Connection refused"


class TestEmbeddingService:
    """Tests for EmbeddingService class."""

    @pytest.fixture
    def service(self, test_settings: Settings) -> EmbeddingService:
        """Create embedding service for testing."""
        return EmbeddingService(test_settings)

    @pytest.mark.asyncio
    async def test_check_health_success(self, service: EmbeddingService):
        """Test health check when Ollama is healthy."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "nomic-embed-text:latest"},
                {"name": "mxbai-rerank-base-v1:latest"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            status = await service.check_health()

            assert status.healthy is True
            assert "nomic-embed-text:latest" in status.models_loaded
            assert status.error is None

    @pytest.mark.asyncio
    async def test_check_health_model_not_found(self, service: EmbeddingService):
        """Test health check when embedding model is not loaded."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "llama2:latest"}]  # Different model
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            status = await service.check_health()

            assert status.healthy is False
            assert "not found" in status.error.lower()

    @pytest.mark.asyncio
    async def test_check_health_connection_error(self, service: EmbeddingService):
        """Test health check when Ollama is not running."""
        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_get_client.return_value = mock_client

            status = await service.check_health()

            assert status.healthy is False
            assert "cannot connect" in status.error.lower()

    @pytest.mark.asyncio
    async def test_embed_text_success(
        self, service: EmbeddingService, mock_embedding: list[float]
    ):
        """Test successful text embedding."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": mock_embedding}
        mock_response.raise_for_status = MagicMock()

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await service.embed_text("Test text")

            assert len(result) == 768
            assert result == mock_embedding
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_text_no_embedding_returned(self, service: EmbeddingService):
        """Test embed_text raises when no embedding returned."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}  # No embedding field
        mock_response.raise_for_status = MagicMock()

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with pytest.raises(RuntimeError, match="No embedding returned"):
                await service.embed_text("Test text")

    @pytest.mark.asyncio
    async def test_embed_text_http_error(self, service: EmbeddingService):
        """Test embed_text raises on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)
            mock_client.post = AsyncMock(side_effect=error)
            mock_get_client.return_value = mock_client

            with pytest.raises(RuntimeError, match="Ollama API error"):
                await service.embed_text("Test text")

    @pytest.mark.asyncio
    async def test_embed_text_timeout(self, service: EmbeddingService):
        """Test embed_text raises on timeout."""
        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_get_client.return_value = mock_client

            with pytest.raises(RuntimeError, match="timed out"):
                await service.embed_text("Test text")

    @pytest.mark.asyncio
    async def test_embed_batch_success(
        self, service: EmbeddingService, mock_embedding: list[float]
    ):
        """Test batch embedding."""
        texts = ["Text 1", "Text 2", "Text 3"]

        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": mock_embedding}
        mock_response.raise_for_status = MagicMock()

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            results = await service.embed_batch(texts, batch_size=2)

            assert len(results) == 3
            assert all(len(emb) == 768 for emb in results)

    @pytest.mark.asyncio
    async def test_embed_batch_retry_on_failure(self, service: EmbeddingService, mock_embedding: list[float]):
        """Test batch embedding retries on failure."""
        texts = ["Text 1"]

        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": mock_embedding}
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Temporary error")
            return mock_response

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=side_effect)
            mock_get_client.return_value = mock_client

            results = await service.embed_batch(texts)

            assert len(results) == 1
            assert call_count == 2  # One failure, one success

    @pytest.mark.asyncio
    async def test_close(self, service: EmbeddingService):
        """Test closing the service."""
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        service._client = mock_client

        await service.close()

        mock_client.aclose.assert_called_once()
        assert service._client is None


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_embed_text_convenience(self, mock_embedding: list[float]):
        """Test embed_text convenience function."""
        with patch("knowledge.embeddings.get_embedding_service") as mock_get:
            mock_service = AsyncMock()
            mock_service.embed_text = AsyncMock(return_value=mock_embedding)
            mock_get.return_value = mock_service

            # Use use_cache=False to bypass Redis cache and test the service call
            result = await embed_text("Test text for embedding", use_cache=False)

            assert result == mock_embedding
            mock_service.embed_text.assert_called_once_with("Test text for embedding")

    @pytest.mark.asyncio
    async def test_embed_batch_convenience(self, mock_embedding: list[float]):
        """Test embed_batch convenience function."""
        with patch("knowledge.embeddings.get_embedding_service") as mock_get:
            mock_service = AsyncMock()
            mock_service.embed_batch = AsyncMock(return_value=[mock_embedding])
            mock_get.return_value = mock_service

            result = await embed_batch(["Test"])

            assert result == [mock_embedding]

    @pytest.mark.asyncio
    async def test_check_ollama_health_convenience(self):
        """Test check_ollama_health convenience function."""
        expected_status = OllamaStatus(healthy=True, models_loaded=["nomic-embed-text"])

        with patch("knowledge.embeddings.get_embedding_service") as mock_get:
            mock_service = AsyncMock()
            mock_service.check_health = AsyncMock(return_value=expected_status)
            mock_get.return_value = mock_service

            result = await check_ollama_health()

            assert result.healthy is True


@pytest.mark.integration
class TestEmbeddingServiceIntegration:
    """Integration tests requiring actual Ollama."""

    @pytest.mark.asyncio
    async def test_real_embedding(self, test_settings: Settings):
        """Test generating real embeddings with Ollama."""
        service = EmbeddingService(test_settings)

        try:
            # Check health first
            status = await service.check_health()
            if not status.healthy:
                pytest.skip(f"Ollama not available: {status.error}")

            # Generate embedding
            embedding = await service.embed_text("Machine learning is fascinating")

            assert len(embedding) == 768
            assert all(isinstance(x, float) for x in embedding)

        finally:
            await service.close()

    @pytest.mark.asyncio
    async def test_real_batch_embedding(self, test_settings: Settings):
        """Test generating real batch embeddings with Ollama."""
        service = EmbeddingService(test_settings)

        try:
            status = await service.check_health()
            if not status.healthy:
                pytest.skip(f"Ollama not available: {status.error}")

            texts = [
                "First text about AI",
                "Second text about ML",
            ]

            embeddings = await service.embed_batch(texts, batch_size=2)

            assert len(embeddings) == 2
            assert all(len(emb) == 768 for emb in embeddings)

        finally:
            await service.close()
