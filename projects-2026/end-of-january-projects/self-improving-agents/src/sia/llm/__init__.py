"""
SIA LLM Module

Provides LLM routing, embeddings, reranking, and utilities.
"""

from sia.llm.embeddings import EmbeddingResult, EmbeddingService, embed
from sia.llm.reranking import RerankResponse, RerankResult, RerankService
from sia.llm.router import (
    LLMError,
    LLMRateLimitError,
    LLMResponse,
    LLMRouter,
    LLMTier,
    LLMTimeoutError,
    complete,
)
from sia.llm.utils import (
    CircuitBreaker,
    CostCalculator,
    CostEstimate,
    RateLimitConfig,
    RateLimiter,
    TokenCounter,
    format_messages,
    get_circuit_breaker,
    get_rate_limiter,
    retry_with_backoff,
    truncate_messages_to_fit,
)

__all__ = [
    # Router
    "LLMRouter",
    "LLMResponse",
    "LLMTier",
    "LLMError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "complete",
    # Embeddings
    "EmbeddingService",
    "EmbeddingResult",
    "embed",
    # Reranking
    "RerankService",
    "RerankResult",
    "RerankResponse",
    # Utilities
    "TokenCounter",
    "CostCalculator",
    "CostEstimate",
    "RateLimiter",
    "RateLimitConfig",
    "CircuitBreaker",
    "get_rate_limiter",
    "get_circuit_breaker",
    "retry_with_backoff",
    "format_messages",
    "truncate_messages_to_fit",
]
