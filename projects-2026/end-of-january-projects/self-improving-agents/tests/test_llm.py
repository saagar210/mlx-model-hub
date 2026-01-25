"""Tests for LLM module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sia.llm import (
    CircuitBreaker,
    CostCalculator,
    CostEstimate,
    EmbeddingService,
    LLMError,
    LLMResponse,
    LLMRouter,
    LLMTier,
    RateLimitConfig,
    RateLimiter,
    TokenCounter,
    format_messages,
    truncate_messages_to_fit,
)


# ============================================================================
# Token Counter Tests
# ============================================================================


class TestTokenCounter:
    """Tests for TokenCounter."""

    def test_count_tokens_simple(self):
        """Test basic token counting."""
        text = "Hello, world!"
        count = TokenCounter.count_tokens(text)
        assert count > 0
        assert count < 10  # Should be around 4 tokens

    def test_count_tokens_empty(self):
        """Test counting empty string."""
        assert TokenCounter.count_tokens("") == 0

    def test_count_tokens_long_text(self):
        """Test counting longer text."""
        text = "This is a longer piece of text that should have more tokens." * 10
        count = TokenCounter.count_tokens(text)
        assert count > 50

    def test_count_message_tokens(self):
        """Test counting tokens in messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ]
        count = TokenCounter.count_message_tokens(messages)
        assert count > 10  # Should include overhead

    def test_truncate_to_tokens(self):
        """Test truncating text to token limit."""
        text = "This is a test sentence that we will truncate to a smaller size."
        truncated = TokenCounter.truncate_to_tokens(text, 5)
        assert len(truncated) < len(text)
        assert TokenCounter.count_tokens(truncated) <= 5

    def test_truncate_short_text(self):
        """Test truncating text that's already short enough."""
        text = "Hi"
        truncated = TokenCounter.truncate_to_tokens(text, 100)
        assert truncated == text


# ============================================================================
# Cost Calculator Tests
# ============================================================================


class TestCostCalculator:
    """Tests for CostCalculator."""

    def test_get_cost_local(self):
        """Test cost for local models."""
        input_rate, output_rate = CostCalculator.get_cost_per_million("ollama")
        assert input_rate == 0
        assert output_rate == 0

    def test_get_cost_deepseek(self):
        """Test cost for DeepSeek models."""
        input_rate, output_rate = CostCalculator.get_cost_per_million("deepseek-chat")
        assert input_rate == 0.14
        assert output_rate == 0.28

    def test_get_cost_unknown(self):
        """Test cost for unknown models defaults to free."""
        input_rate, output_rate = CostCalculator.get_cost_per_million("unknown-model")
        assert input_rate == 0
        assert output_rate == 0

    def test_calculate_cost(self):
        """Test cost calculation."""
        estimate = CostCalculator.calculate_cost(
            input_tokens=1000,
            output_tokens=500,
            model="deepseek-chat",
            tier=LLMTier.DEEPSEEK,
        )

        assert isinstance(estimate, CostEstimate)
        assert estimate.input_tokens == 1000
        assert estimate.output_tokens == 500
        # 1000 * 0.14 / 1M = 0.00014
        assert abs(estimate.input_cost_usd - 0.00014) < 0.0001
        # 500 * 0.28 / 1M = 0.00014
        assert abs(estimate.output_cost_usd - 0.00014) < 0.0001

    def test_estimate_cost(self):
        """Test cost estimation from messages."""
        messages = [
            {"role": "user", "content": "Hello, how are you?"},
        ]
        estimate = CostCalculator.estimate_cost(
            messages=messages,
            expected_output_tokens=100,
            model="deepseek-chat",
            tier=LLMTier.DEEPSEEK,
        )

        assert estimate.input_tokens > 0
        assert estimate.output_tokens == 100


# ============================================================================
# Rate Limiter Tests
# ============================================================================


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """Test acquiring within rate limit."""
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=10))
        assert await limiter.acquire() is True

    @pytest.mark.asyncio
    async def test_acquire_exceeds_limit(self):
        """Test acquiring when limit exceeded."""
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=2))

        assert await limiter.acquire() is True
        assert await limiter.acquire() is True
        assert await limiter.acquire() is False  # Should be rate limited

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting rate limiter status."""
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=100))
        await limiter.acquire()
        await limiter.acquire()

        status = limiter.get_status()
        assert status["minute_requests"] == 2
        assert status["minute_requests_limit"] == 100


# ============================================================================
# Circuit Breaker Tests
# ============================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_closed_state(self):
        """Test circuit breaker in closed state."""
        cb = CircuitBreaker(failure_threshold=3)
        assert await cb.can_execute("test") is True

    @pytest.mark.asyncio
    async def test_opens_after_failures(self):
        """Test circuit breaker opens after failures."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

        for _ in range(3):
            await cb.record_failure("test")

        assert await cb.can_execute("test") is False

    @pytest.mark.asyncio
    async def test_resets_on_success(self):
        """Test circuit breaker resets on success."""
        cb = CircuitBreaker(failure_threshold=3)

        await cb.record_failure("test")
        await cb.record_failure("test")
        await cb.record_success("test")

        status = cb.get_status("test")
        assert status["failures"] == 0
        assert status["state"] == "closed"

    @pytest.mark.asyncio
    async def test_half_open_recovery(self):
        """Test circuit breaker half-open state."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        # Open the circuit
        await cb.record_failure("test")
        await cb.record_failure("test")
        assert await cb.can_execute("test") is False

        # Wait for recovery
        await asyncio.sleep(0.2)

        # Should be half-open now
        assert await cb.can_execute("test") is True
        await cb.record_success("test")

        # Should be closed now
        status = cb.get_status("test")
        assert status["state"] == "closed"


# ============================================================================
# Message Formatting Tests
# ============================================================================


class TestFormatMessages:
    """Tests for format_messages utility."""

    def test_format_with_system(self):
        """Test formatting with system message."""
        messages = format_messages(system="You are helpful", user="Hi")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_format_with_history(self):
        """Test formatting with history."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        messages = format_messages(
            system="You are helpful",
            history=history,
            user="How are you?",
        )
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"

    def test_format_minimal(self):
        """Test minimal formatting."""
        messages = format_messages(user="Hello")
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"


class TestTruncateMessages:
    """Tests for truncate_messages_to_fit utility."""

    def test_no_truncation_needed(self):
        """Test when messages fit within limit."""
        messages = [
            {"role": "user", "content": "Hi"},
        ]
        result = truncate_messages_to_fit(messages, max_tokens=100)
        assert result == messages

    def test_truncation_preserves_system(self):
        """Test that truncation preserves system message."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
        ]
        result = truncate_messages_to_fit(
            messages,
            max_tokens=30,
            preserve_system=True,
            preserve_last_n=1,
        )

        # Should have system and last message
        assert result[0]["role"] == "system"
        assert result[-1]["content"] == "Message 2"


# ============================================================================
# LLM Router Tests
# ============================================================================


class TestLLMRouter:
    """Tests for LLMRouter."""

    def test_router_init(self):
        """Test router initialization."""
        router = LLMRouter()
        assert LLMTier.LOCAL_OLLAMA in router._clients

    def test_get_tier_order(self):
        """Test tier ordering."""
        router = LLMRouter()
        tiers = router._get_tier_order()
        assert LLMTier.LOCAL_OLLAMA in tiers
        # Local should be first
        assert tiers[0] == LLMTier.LOCAL_OLLAMA

    def test_get_model_for_tier(self):
        """Test model selection for tiers."""
        router = LLMRouter()
        model = router._get_model_for_tier(LLMTier.LOCAL_OLLAMA)
        assert "qwen" in model.lower()

    def test_calculate_cost(self):
        """Test cost calculation."""
        router = LLMRouter()
        cost = router._calculate_cost(
            tier=LLMTier.DEEPSEEK,
            tokens_input=1000,
            tokens_output=500,
        )
        assert cost > 0


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_response_success(self):
        """Test successful response."""
        response = LLMResponse(
            content="Hello!",
            model="test-model",
            tier=LLMTier.LOCAL_OLLAMA,
        )
        assert response.success is True

    def test_response_empty(self):
        """Test empty response."""
        response = LLMResponse(
            content="",
            model="test-model",
            tier=LLMTier.LOCAL_OLLAMA,
        )
        assert response.success is False


# ============================================================================
# Integration Tests (require Ollama running)
# ============================================================================


@pytest.mark.skipif(
    True,  # Skip by default, enable when Ollama is available
    reason="Requires Ollama to be running",
)
class TestLLMIntegration:
    """Integration tests requiring actual LLM service."""

    @pytest.mark.asyncio
    async def test_complete_ollama(self):
        """Test completion with Ollama."""
        router = LLMRouter()
        response = await router.complete(
            messages=[{"role": "user", "content": "Say 'test' and nothing else"}],
            max_tokens=10,
        )
        assert response.success
        assert response.tier == LLMTier.LOCAL_OLLAMA

    @pytest.mark.asyncio
    async def test_embedding_ollama(self):
        """Test embedding generation with Ollama."""
        service = EmbeddingService()
        try:
            result = await service.embed("Hello, world!")
            assert len(result.embedding) == 768
            assert result.dimensions == 768
        finally:
            await service.close()

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        router = LLMRouter()
        health = await router.health_check()
        assert "local_ollama" in health
