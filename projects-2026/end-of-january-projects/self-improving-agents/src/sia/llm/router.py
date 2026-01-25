"""
LLM Router - Tiered routing with automatic failover.

Routes LLM calls through a tiered system:
1. Local (Ollama/MLX) - Primary, free
2. OpenRouter (free tier) - Cloud fallback 1
3. DeepSeek - Cloud fallback 2 ($0.28/M tokens)
4. Claude - Cloud fallback 3 (Claude Max)
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

import httpx
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from sia.config import SIAConfig, get_config


class LLMTier(str, Enum):
    """LLM tier enumeration."""
    LOCAL_OLLAMA = "local_ollama"
    LOCAL_MLX = "local_mlx"
    OPENROUTER = "openrouter"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    GATEWAY = "gateway"


@dataclass
class LLMResponse:
    """Response from LLM call."""
    content: str
    model: str
    tier: LLMTier
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    raw_response: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return bool(self.content)


class LLMError(Exception):
    """Base LLM error."""
    pass


class LLMTimeoutError(LLMError):
    """LLM call timed out."""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""
    pass


class LLMRouter:
    """
    Routes LLM calls through tiered providers with automatic failover.

    Usage:
        router = LLMRouter()
        response = await router.complete(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
        )
    """

    # Cost per 1M tokens (input/output)
    COSTS = {
        LLMTier.LOCAL_OLLAMA: (0, 0),
        LLMTier.LOCAL_MLX: (0, 0),
        LLMTier.OPENROUTER: (0, 0),  # Free tier
        LLMTier.DEEPSEEK: (0.14, 0.28),  # DeepSeek chat
        LLMTier.ANTHROPIC: (0.25, 1.25),  # Claude Haiku
        LLMTier.GATEWAY: (0, 0),  # Cost tracked by gateway
    }

    def __init__(self, config: SIAConfig | None = None):
        self.config = config or get_config()
        self._clients: dict[LLMTier, AsyncOpenAI] = {}
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize OpenAI-compatible clients for each tier."""
        # Local Ollama
        self._clients[LLMTier.LOCAL_OLLAMA] = AsyncOpenAI(
            base_url=f"{self.config.ollama.base_url}/v1",
            api_key="ollama",  # Ollama doesn't need a key
            timeout=self.config.ollama.timeout,
        )

        # OpenRouter
        if self.config.cloud_llm.openrouter_api_key:
            self._clients[LLMTier.OPENROUTER] = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.config.cloud_llm.openrouter_api_key,
                timeout=120,
            )

        # DeepSeek
        if self.config.cloud_llm.deepseek_api_key:
            self._clients[LLMTier.DEEPSEEK] = AsyncOpenAI(
                base_url="https://api.deepseek.com/v1",
                api_key=self.config.cloud_llm.deepseek_api_key,
                timeout=120,
            )

        # Anthropic (via OpenAI-compatible proxy or direct)
        if self.config.cloud_llm.anthropic_api_key:
            self._clients[LLMTier.ANTHROPIC] = AsyncOpenAI(
                base_url="https://api.anthropic.com/v1",
                api_key=self.config.cloud_llm.anthropic_api_key,
                timeout=120,
                default_headers={
                    "anthropic-version": "2023-06-01",
                },
            )

        # LLM Gateway (AI Command Center)
        if self.config.cloud_llm.use_llm_gateway:
            self._clients[LLMTier.GATEWAY] = AsyncOpenAI(
                base_url=self.config.cloud_llm.llm_gateway_url,
                api_key="gateway",  # Gateway handles auth
                timeout=120,
            )

    def _get_tier_order(self) -> list[LLMTier]:
        """Get ordered list of tiers to try."""
        if self.config.cloud_llm.use_llm_gateway:
            return [LLMTier.GATEWAY]

        tiers = [LLMTier.LOCAL_OLLAMA]

        if self.config.cloud_llm.openrouter_api_key:
            tiers.append(LLMTier.OPENROUTER)

        if self.config.cloud_llm.deepseek_api_key:
            tiers.append(LLMTier.DEEPSEEK)

        if self.config.cloud_llm.anthropic_api_key:
            tiers.append(LLMTier.ANTHROPIC)

        return tiers

    def _get_model_for_tier(self, tier: LLMTier) -> str:
        """Get model name for a tier."""
        if tier == LLMTier.LOCAL_OLLAMA:
            return self.config.ollama.model
        elif tier == LLMTier.OPENROUTER:
            return self.config.cloud_llm.openrouter_model
        elif tier == LLMTier.DEEPSEEK:
            return self.config.cloud_llm.deepseek_model
        elif tier == LLMTier.ANTHROPIC:
            return self.config.cloud_llm.anthropic_model
        elif tier == LLMTier.GATEWAY:
            return self.config.ollama.model  # Gateway routes to best
        else:
            return self.config.ollama.model

    def _calculate_cost(
        self,
        tier: LLMTier,
        tokens_input: int,
        tokens_output: int,
    ) -> float:
        """Calculate cost in USD."""
        input_cost, output_cost = self.COSTS.get(tier, (0, 0))
        return (tokens_input * input_cost + tokens_output * output_cost) / 1_000_000

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _call_tier(
        self,
        tier: LLMTier,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Make a single call to a specific tier."""
        client = self._clients.get(tier)
        if not client:
            raise LLMError(f"Tier {tier} not configured")

        model = model or self._get_model_for_tier(tier)
        temperature = temperature if temperature is not None else self.config.execution.default_temperature
        max_tokens = max_tokens or self.config.execution.default_max_tokens

        start_time = time.time()

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            tokens_input = response.usage.prompt_tokens if response.usage else 0
            tokens_output = response.usage.completion_tokens if response.usage else 0

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                tier=tier,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                tokens_total=tokens_input + tokens_output,
                latency_ms=latency_ms,
                cost_usd=self._calculate_cost(tier, tokens_input, tokens_output),
                raw_response=response.model_dump(),
            )

        except Exception as e:
            raise LLMError(f"Tier {tier} failed: {str(e)}") from e

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        preferred_tier: LLMTier | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Complete a chat request with automatic tier failover.

        Args:
            messages: List of chat messages
            model: Override model selection
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            preferred_tier: Start with this tier if available
            **kwargs: Additional parameters passed to the API

        Returns:
            LLMResponse with completion result

        Raises:
            LLMError: If all tiers fail
        """
        tiers = self._get_tier_order()

        # If preferred tier is specified and available, try it first
        if preferred_tier and preferred_tier in tiers:
            tiers.remove(preferred_tier)
            tiers.insert(0, preferred_tier)

        errors = []

        for tier in tiers:
            try:
                return await self._call_tier(
                    tier=tier,
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except Exception as e:
                errors.append(f"{tier}: {str(e)}")
                continue

        raise LLMError(f"All LLM tiers failed: {'; '.join(errors)}")

    async def stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        preferred_tier: LLMTier | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream a chat completion.

        Yields chunks of the response as they arrive.
        Note: Streaming only tries the first available tier.
        """
        tiers = self._get_tier_order()

        if preferred_tier and preferred_tier in tiers:
            tier = preferred_tier
        else:
            tier = tiers[0]

        client = self._clients.get(tier)
        if not client:
            raise LLMError(f"Tier {tier} not configured")

        model = model or self._get_model_for_tier(tier)
        temperature = temperature if temperature is not None else self.config.execution.default_temperature
        max_tokens = max_tokens or self.config.execution.default_max_tokens

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> dict[str, Any]:
        """Check health of all configured tiers."""
        results = {}

        for tier in self._get_tier_order():
            try:
                response = await self._call_tier(
                    tier=tier,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=5,
                )
                results[tier.value] = {
                    "status": "healthy",
                    "model": response.model,
                    "latency_ms": response.latency_ms,
                }
            except Exception as e:
                results[tier.value] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        return results


# Convenience function for one-off calls
async def complete(
    messages: list[dict[str, str]],
    **kwargs: Any,
) -> LLMResponse:
    """Convenience function for one-off completions."""
    router = LLMRouter()
    return await router.complete(messages, **kwargs)
