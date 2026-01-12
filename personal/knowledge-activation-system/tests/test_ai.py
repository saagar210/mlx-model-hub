"""Tests for AI provider integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from knowledge.ai import (
    AIProvider,
    AIResponse,
    ModelConfig,
    MODELS,
    MODEL_PRIORITY,
    generate_answer,
)


class TestAIResponse:
    """Tests for AIResponse dataclass."""

    def test_success_with_content(self):
        """Test successful response."""
        response = AIResponse(content="Hello", model="deepseek")
        assert response.success is True

    def test_failure_with_error(self):
        """Test failed response with error."""
        response = AIResponse(content="", model="deepseek", error="API Error")
        assert response.success is False

    def test_failure_with_empty_content(self):
        """Test failed response with empty content."""
        response = AIResponse(content="", model="deepseek")
        assert response.success is False

    def test_usage_tracking(self):
        """Test usage information."""
        usage = {"prompt_tokens": 10, "completion_tokens": 20}
        response = AIResponse(content="Hi", model="deepseek", usage=usage)
        assert response.usage == usage


class TestModelConfig:
    """Tests for model configurations."""

    def test_deepseek_config(self):
        """Test DeepSeek model config."""
        config = MODELS["deepseek"]
        assert config.model_id == "deepseek/deepseek-chat"
        assert config.max_tokens > 0

    def test_claude_config(self):
        """Test Claude model config."""
        config = MODELS["claude"]
        assert "anthropic" in config.model_id
        assert config.cost_per_1m_input > 0

    def test_model_priority_order(self):
        """Test model priority list."""
        assert MODEL_PRIORITY[0] == "deepseek"  # Primary
        assert "claude" in MODEL_PRIORITY  # Fallback


class TestAIProvider:
    """Tests for AIProvider class."""

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Test generation fails gracefully without API key."""
        provider = AIProvider(api_key=None)
        # Ensure env var is not set for test
        with patch.dict("os.environ", {}, clear=True):
            provider.api_key = None
            response = await provider.generate("Hello")

        assert response.success is False
        assert "API key" in response.error

    @pytest.mark.asyncio
    async def test_generate_unknown_model(self):
        """Test generation with unknown model."""
        provider = AIProvider(api_key="test-key")
        response = await provider.generate("Hello", model="unknown-model")

        assert response.success is False
        assert "Unknown model" in response.error

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generation with mocked API."""
        provider = AIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello back!"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value = AsyncMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            response = await provider.generate("Hello")

        assert response.success is True
        assert response.content == "Hello back!"

    @pytest.mark.asyncio
    async def test_generate_api_error(self):
        """Test handling of API errors."""
        provider = AIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value = AsyncMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            response = await provider.generate("Hello")

        assert response.success is False
        assert "500" in response.error

    @pytest.mark.asyncio
    async def test_generate_with_fallback_first_success(self):
        """Test fallback stops at first successful model."""
        provider = AIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Success!"}}],
        }

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value = AsyncMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            response = await provider.generate_with_fallback("Hello")

        assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_with_fallback_all_fail(self):
        """Test fallback when all models fail."""
        provider = AIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Error"

        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value = AsyncMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            response = await provider.generate_with_fallback(
                "Hello", models=["deepseek", "claude"]
            )

        assert response.success is False
        assert "All models failed" in response.error


class TestGenerateAnswer:
    """Tests for generate_answer function."""

    @pytest.mark.asyncio
    async def test_formats_context_correctly(self):
        """Test that context is formatted properly."""
        context = [
            {"title": "Doc 1", "text": "Content 1", "source": "http://example.com"},
            {"title": "Doc 2", "text": "Content 2", "source": ""},
        ]

        with patch("knowledge.ai.get_ai_provider") as mock_provider:
            mock_instance = AsyncMock()
            mock_instance.generate_with_fallback = AsyncMock(
                return_value=AIResponse(content="Answer", model="test")
            )
            mock_provider.return_value = mock_instance

            await generate_answer("What is X?", context)

            # Verify generate was called
            mock_instance.generate_with_fallback.assert_called_once()

            # Check prompt contains context
            call_args = mock_instance.generate_with_fallback.call_args
            prompt = call_args.kwargs.get("prompt", "")
            assert "Doc 1" in prompt
            assert "Content 1" in prompt

    @pytest.mark.asyncio
    async def test_uses_low_temperature(self):
        """Test that factual answers use low temperature."""
        with patch("knowledge.ai.get_ai_provider") as mock_provider:
            mock_instance = AsyncMock()
            mock_instance.generate_with_fallback = AsyncMock(
                return_value=AIResponse(content="Answer", model="test")
            )
            mock_provider.return_value = mock_instance

            await generate_answer("Question?", [])

            call_args = mock_instance.generate_with_fallback.call_args
            temperature = call_args.kwargs.get("temperature", 1.0)
            assert temperature <= 0.5  # Should be low for factual answers
