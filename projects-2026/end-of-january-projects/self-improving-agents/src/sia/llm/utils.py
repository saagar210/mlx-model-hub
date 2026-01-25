"""
LLM Utilities

Token counting, cost calculation, rate limiting, and retry helpers.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, TypeVar

import tiktoken

from sia.llm.router import LLMTier

T = TypeVar("T")


# ============================================================================
# Token Counting
# ============================================================================


class TokenCounter:
    """
    Count tokens for different models.

    Uses tiktoken for accurate counting with model-specific encodings.
    """

    # Model to encoding mapping
    MODEL_ENCODINGS = {
        # OpenAI models
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        # Claude models (approximate with cl100k)
        "claude": "cl100k_base",
        "claude-3": "cl100k_base",
        # Qwen models (approximate with cl100k)
        "qwen": "cl100k_base",
        "qwen2.5": "cl100k_base",
        # DeepSeek (approximate with cl100k)
        "deepseek": "cl100k_base",
        # Default
        "default": "cl100k_base",
    }

    _encodings: dict[str, tiktoken.Encoding] = {}

    @classmethod
    def _get_encoding(cls, model: str) -> tiktoken.Encoding:
        """Get tiktoken encoding for a model."""
        # Find matching encoding
        encoding_name = cls.MODEL_ENCODINGS.get("default")
        for prefix, enc in cls.MODEL_ENCODINGS.items():
            if model.lower().startswith(prefix):
                encoding_name = enc
                break

        # Cache encoding
        if encoding_name not in cls._encodings:
            cls._encodings[encoding_name] = tiktoken.get_encoding(encoding_name)

        return cls._encodings[encoding_name]

    @classmethod
    def count_tokens(cls, text: str, model: str = "default") -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count tokens for
            model: Model name for encoding selection

        Returns:
            Number of tokens
        """
        encoding = cls._get_encoding(model)
        return len(encoding.encode(text))

    @classmethod
    def count_message_tokens(
        cls,
        messages: list[dict[str, str]],
        model: str = "default",
    ) -> int:
        """
        Count tokens in a list of chat messages.

        Accounts for message formatting overhead.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name for encoding selection

        Returns:
            Estimated token count
        """
        encoding = cls._get_encoding(model)
        tokens = 0

        # Each message has overhead (~4 tokens for formatting)
        for message in messages:
            tokens += 4  # Message overhead
            tokens += len(encoding.encode(message.get("role", "")))
            tokens += len(encoding.encode(message.get("content", "")))

        tokens += 2  # Conversation overhead

        return tokens

    @classmethod
    def truncate_to_tokens(
        cls,
        text: str,
        max_tokens: int,
        model: str = "default",
    ) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
            model: Model name for encoding selection

        Returns:
            Truncated text
        """
        encoding = cls._get_encoding(model)
        tokens = encoding.encode(text)

        if len(tokens) <= max_tokens:
            return text

        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)


# ============================================================================
# Cost Calculation
# ============================================================================


@dataclass
class CostEstimate:
    """Cost estimate for an LLM call."""

    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    tier: LLMTier
    model: str


class CostCalculator:
    """
    Calculate costs for LLM calls.

    Maintains cost tables for different providers and models.
    """

    # Cost per 1M tokens (input, output)
    COST_TABLE: dict[str, tuple[float, float]] = {
        # Local (free)
        "ollama": (0, 0),
        "mlx": (0, 0),
        # OpenRouter free tier
        "qwen/qwen-2.5-7b-instruct:free": (0, 0),
        # DeepSeek
        "deepseek-chat": (0.14, 0.28),
        "deepseek-coder": (0.14, 0.28),
        # Anthropic
        "claude-3-haiku-20240307": (0.25, 1.25),
        "claude-3-sonnet-20240229": (3.0, 15.0),
        "claude-3-opus-20240229": (15.0, 75.0),
        "claude-3-5-sonnet-20241022": (3.0, 15.0),
        # OpenAI (for reference)
        "gpt-4-turbo": (10.0, 30.0),
        "gpt-4o": (5.0, 15.0),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-3.5-turbo": (0.50, 1.50),
    }

    @classmethod
    def get_cost_per_million(cls, model: str) -> tuple[float, float]:
        """Get cost per million tokens for a model."""
        # Exact match
        if model in cls.COST_TABLE:
            return cls.COST_TABLE[model]

        # Partial match
        model_lower = model.lower()
        for key, costs in cls.COST_TABLE.items():
            if key in model_lower or model_lower in key:
                return costs

        # Default to free (local models)
        return (0, 0)

    @classmethod
    def calculate_cost(
        cls,
        input_tokens: int,
        output_tokens: int,
        model: str,
        tier: LLMTier = LLMTier.LOCAL_OLLAMA,
    ) -> CostEstimate:
        """
        Calculate cost for an LLM call.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name
            tier: LLM tier

        Returns:
            CostEstimate with detailed breakdown
        """
        input_rate, output_rate = cls.get_cost_per_million(model)

        input_cost = (input_tokens / 1_000_000) * input_rate
        output_cost = (output_tokens / 1_000_000) * output_rate

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=input_cost + output_cost,
            tier=tier,
            model=model,
        )

    @classmethod
    def estimate_cost(
        cls,
        messages: list[dict[str, str]],
        expected_output_tokens: int,
        model: str,
        tier: LLMTier = LLMTier.LOCAL_OLLAMA,
    ) -> CostEstimate:
        """
        Estimate cost before making an LLM call.

        Args:
            messages: Input messages
            expected_output_tokens: Expected output token count
            model: Model name
            tier: LLM tier

        Returns:
            CostEstimate with estimated costs
        """
        input_tokens = TokenCounter.count_message_tokens(messages, model)
        return cls.calculate_cost(input_tokens, expected_output_tokens, model, tier)


# ============================================================================
# Rate Limiting
# ============================================================================


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    requests_per_day: int = 10000
    tokens_per_day: int = 1000000


class RateLimiter:
    """
    Token bucket rate limiter for LLM calls.

    Supports both request count and token-based limiting.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()

        # Request tracking (sliding window)
        self._minute_requests: deque[float] = deque()
        self._day_requests: deque[float] = deque()

        # Token tracking (sliding window)
        self._minute_tokens: deque[tuple[float, int]] = deque()
        self._day_tokens: deque[tuple[float, int]] = deque()

        self._lock = asyncio.Lock()

    def _clean_window(
        self,
        window: deque,
        max_age_seconds: float,
    ) -> None:
        """Remove entries older than max_age_seconds."""
        now = time.time()
        while window and (now - window[0] if isinstance(window[0], float) else now - window[0][0]) > max_age_seconds:
            window.popleft()

    def _get_token_sum(self, window: deque[tuple[float, int]]) -> int:
        """Sum tokens in window."""
        return sum(tokens for _, tokens in window)

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire rate limit slot.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if acquired, False if rate limited
        """
        async with self._lock:
            now = time.time()

            # Clean old entries
            self._clean_window(self._minute_requests, 60)
            self._clean_window(self._day_requests, 86400)
            self._clean_window(self._minute_tokens, 60)
            self._clean_window(self._day_tokens, 86400)

            # Check request limits
            if len(self._minute_requests) >= self.config.requests_per_minute:
                return False
            if len(self._day_requests) >= self.config.requests_per_day:
                return False

            # Check token limits
            minute_tokens = self._get_token_sum(self._minute_tokens)
            if minute_tokens + tokens > self.config.tokens_per_minute:
                return False

            day_tokens = self._get_token_sum(self._day_tokens)
            if day_tokens + tokens > self.config.tokens_per_day:
                return False

            # Record this request
            self._minute_requests.append(now)
            self._day_requests.append(now)
            self._minute_tokens.append((now, tokens))
            self._day_tokens.append((now, tokens))

            return True

    async def wait_and_acquire(self, tokens: int = 1, timeout: float = 60) -> bool:
        """
        Wait until rate limit slot is available.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait in seconds

        Returns:
            True if acquired, False if timed out
        """
        start = time.time()

        while time.time() - start < timeout:
            if await self.acquire(tokens):
                return True
            await asyncio.sleep(0.5)

        return False

    def get_status(self) -> dict[str, Any]:
        """Get current rate limit status."""
        return {
            "minute_requests": len(self._minute_requests),
            "minute_requests_limit": self.config.requests_per_minute,
            "day_requests": len(self._day_requests),
            "day_requests_limit": self.config.requests_per_day,
            "minute_tokens": self._get_token_sum(self._minute_tokens),
            "minute_tokens_limit": self.config.tokens_per_minute,
            "day_tokens": self._get_token_sum(self._day_tokens),
            "day_tokens_limit": self.config.tokens_per_day,
        }


# Global rate limiter instances per tier
_rate_limiters: dict[LLMTier, RateLimiter] = {}


def get_rate_limiter(tier: LLMTier) -> RateLimiter:
    """Get rate limiter for a tier."""
    if tier not in _rate_limiters:
        # Default configs per tier
        configs = {
            LLMTier.LOCAL_OLLAMA: RateLimitConfig(
                requests_per_minute=1000,
                tokens_per_minute=1000000,
            ),
            LLMTier.OPENROUTER: RateLimitConfig(
                requests_per_minute=50,
                tokens_per_minute=100000,
            ),
            LLMTier.DEEPSEEK: RateLimitConfig(
                requests_per_minute=60,
                tokens_per_minute=100000,
            ),
            LLMTier.ANTHROPIC: RateLimitConfig(
                requests_per_minute=50,
                tokens_per_minute=100000,
            ),
        }
        _rate_limiters[tier] = RateLimiter(configs.get(tier))

    return _rate_limiters[tier]


# ============================================================================
# Retry Decorators
# ============================================================================


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for delay after each retry
        retryable_exceptions: Tuple of exceptions that trigger retry

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        raise

            raise last_exception  # type: ignore

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        raise

            raise last_exception  # type: ignore

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


# ============================================================================
# Circuit Breaker
# ============================================================================


@dataclass
class CircuitBreakerState:
    """Circuit breaker state."""

    failures: int = 0
    last_failure_time: float = 0
    state: str = "closed"  # closed, open, half-open


class CircuitBreaker:
    """
    Circuit breaker for LLM calls.

    Prevents cascading failures by temporarily disabling calls
    to failing services.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._states: dict[str, CircuitBreakerState] = {}
        self._half_open_calls: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def _get_state(self, key: str) -> CircuitBreakerState:
        """Get or create state for a key."""
        if key not in self._states:
            self._states[key] = CircuitBreakerState()
        return self._states[key]

    async def can_execute(self, key: str) -> bool:
        """
        Check if execution is allowed.

        Args:
            key: Circuit breaker key (e.g., tier name)

        Returns:
            True if execution is allowed
        """
        async with self._lock:
            state = self._get_state(key)
            now = time.time()

            if state.state == "closed":
                return True

            if state.state == "open":
                # Check if recovery timeout has passed
                if now - state.last_failure_time >= self.recovery_timeout:
                    state.state = "half-open"
                    self._half_open_calls[key] = 0
                    return True
                return False

            if state.state == "half-open":
                # Allow limited calls in half-open state
                calls = self._half_open_calls.get(key, 0)
                if calls < self.half_open_max_calls:
                    self._half_open_calls[key] = calls + 1
                    return True
                return False

            return False

    async def record_success(self, key: str) -> None:
        """Record a successful execution."""
        async with self._lock:
            state = self._get_state(key)

            if state.state == "half-open":
                # Reset to closed on success in half-open
                state.state = "closed"
                state.failures = 0

            elif state.state == "closed":
                # Reset failure count on success
                state.failures = 0

    async def record_failure(self, key: str) -> None:
        """Record a failed execution."""
        async with self._lock:
            state = self._get_state(key)
            now = time.time()

            state.failures += 1
            state.last_failure_time = now

            if state.state == "half-open":
                # Immediately open on failure in half-open
                state.state = "open"

            elif state.state == "closed":
                if state.failures >= self.failure_threshold:
                    state.state = "open"

    def get_status(self, key: str) -> dict[str, Any]:
        """Get circuit breaker status for a key."""
        state = self._get_state(key)
        return {
            "state": state.state,
            "failures": state.failures,
            "last_failure_time": state.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


# Global circuit breaker
_circuit_breaker: CircuitBreaker | None = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get global circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker


# ============================================================================
# Prompt Utilities
# ============================================================================


def format_messages(
    system: str | None = None,
    user: str | None = None,
    assistant: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """
    Format messages for chat completion.

    Args:
        system: System message
        user: User message
        assistant: Assistant message (for few-shot)
        history: Previous conversation history

    Returns:
        Formatted message list
    """
    messages = []

    if system:
        messages.append({"role": "system", "content": system})

    if history:
        messages.extend(history)

    if user:
        messages.append({"role": "user", "content": user})

    if assistant:
        messages.append({"role": "assistant", "content": assistant})

    return messages


def truncate_messages_to_fit(
    messages: list[dict[str, str]],
    max_tokens: int,
    model: str = "default",
    preserve_system: bool = True,
    preserve_last_n: int = 2,
) -> list[dict[str, str]]:
    """
    Truncate message history to fit within token limit.

    Preserves system message and most recent messages.

    Args:
        messages: List of messages
        max_tokens: Maximum total tokens
        model: Model for token counting
        preserve_system: Keep system message if present
        preserve_last_n: Number of recent messages to always keep

    Returns:
        Truncated message list
    """
    if not messages:
        return messages

    # Check if already fits
    current_tokens = TokenCounter.count_message_tokens(messages, model)
    if current_tokens <= max_tokens:
        return messages

    result = []

    # Preserve system message
    if preserve_system and messages[0].get("role") == "system":
        result.append(messages[0])
        messages = messages[1:]

    # Preserve last N messages
    preserved = messages[-preserve_last_n:] if preserve_last_n else []
    middle = messages[:-preserve_last_n] if preserve_last_n else messages

    # Add messages from middle until we run out of space
    result_tokens = TokenCounter.count_message_tokens(result + preserved, model)

    for msg in middle:
        msg_tokens = TokenCounter.count_message_tokens([msg], model)
        if result_tokens + msg_tokens <= max_tokens:
            result.append(msg)
            result_tokens += msg_tokens
        else:
            break

    result.extend(preserved)
    return result
