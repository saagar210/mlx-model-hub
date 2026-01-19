"""AI provider integration using OpenRouter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from knowledge.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AIResponse:
    """Response from AI provider."""

    content: str
    model: str
    usage: dict[str, int] | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        """Check if response was successful."""
        return self.error is None and bool(self.content)


@dataclass
class ModelConfig:
    """Configuration for an AI model."""

    model_id: str
    name: str
    cost_per_1m_input: float
    cost_per_1m_output: float
    max_tokens: int = 4096


# Available models via OpenRouter (in priority order)
MODELS = {
    "deepseek": ModelConfig(
        model_id="deepseek/deepseek-chat",
        name="DeepSeek Chat",
        cost_per_1m_input=0.14,
        cost_per_1m_output=0.28,
        max_tokens=8192,
    ),
    "claude": ModelConfig(
        model_id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet",
        cost_per_1m_input=3.0,
        cost_per_1m_output=15.0,
        max_tokens=8192,
    ),
    "deepseek-free": ModelConfig(
        model_id="deepseek/deepseek-r1:free",
        name="DeepSeek R1 (Free)",
        cost_per_1m_input=0.0,
        cost_per_1m_output=0.0,
        max_tokens=4096,
    ),
}

# Default model priority for fallback
MODEL_PRIORITY = ["deepseek", "claude", "deepseek-free"]


class AIProvider:
    """AI provider using OpenRouter API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 60.0,
    ):
        """
        Initialize AI provider.

        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            base_url: OpenRouter API base URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.base_url = base_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/knowledge-activation-system",
                    "X-Title": "Knowledge Activation System",
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str = "deepseek",
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> AIResponse:
        """
        Generate a response from the AI model.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Model key from MODELS dict
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Returns:
            AIResponse with content or error
        """
        if not self.api_key:
            error_msg = (
                "OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable."
            )
            logger.error(error_msg)
            return AIResponse(
                content="",
                model=model,
                error=error_msg,
            )

        model_config = MODELS.get(model)
        if not model_config:
            return AIResponse(
                content="",
                model=model,
                error=f"Unknown model: {model}",
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            client = await self._get_client()
            response = await client.post(
                "/chat/completions",
                json={
                    "model": model_config.model_id,
                    "messages": messages,
                    "max_tokens": max_tokens or model_config.max_tokens,
                    "temperature": temperature,
                },
            )

            if response.status_code != 200:
                error_text = response.text
                return AIResponse(
                    content="",
                    model=model,
                    error=f"API error ({response.status_code}): {error_text[:200]}",
                )

            data = response.json()

            # Extract content from response
            choices = data.get("choices", [])
            if not choices:
                return AIResponse(
                    content="",
                    model=model,
                    error="No response choices returned",
                )

            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage")

            return AIResponse(
                content=content,
                model=model,
                usage=usage,
            )

        except httpx.TimeoutException:
            return AIResponse(
                content="",
                model=model,
                error="Request timed out",
            )
        except Exception as e:
            return AIResponse(
                content="",
                model=model,
                error=f"Request failed: {str(e)}",
            )

    async def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: str | None = None,
        models: list[str] | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> AIResponse:
        """
        Generate with automatic fallback through model priority.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            models: Model priority list (defaults to MODEL_PRIORITY)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            AIResponse from first successful model
        """
        models = models or MODEL_PRIORITY
        last_error = None

        for model in models:
            response = await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            if response.success:
                return response

            last_error = response.error

        return AIResponse(
            content="",
            model=models[-1] if models else "unknown",
            error=f"All models failed. Last error: {last_error}",
        )


# Global provider instance
_provider: AIProvider | None = None


async def get_ai_provider() -> AIProvider:
    """Get or create global AI provider instance."""
    global _provider
    if _provider is None:
        _provider = AIProvider()
    return _provider


async def close_ai_provider() -> None:
    """Close global AI provider."""
    global _provider
    if _provider is not None:
        await _provider.close()
        _provider = None


async def generate_answer(
    query: str,
    context: list[dict[str, Any]],
    max_tokens: int = 1024,
) -> AIResponse:
    """
    Generate an answer to a query using context from search results.

    Args:
        query: User's question
        context: List of context chunks with 'text', 'title', 'source' keys
        max_tokens: Maximum tokens for response

    Returns:
        AIResponse with generated answer
    """
    provider = await get_ai_provider()

    # Format context for prompt
    context_text = ""
    for i, ctx in enumerate(context, 1):
        title = ctx.get("title", "Unknown")
        text = ctx.get("text", "")
        source = ctx.get("source", "")
        context_text += f"\n[{i}] {title}\n{text}\n"
        if source:
            context_text += f"Source: {source}\n"

    system_prompt = """You are a helpful assistant that answers questions based on the provided context.

Guidelines:
- Answer based ONLY on the provided context
- If the context doesn't contain enough information, say so
- Cite sources using [1], [2], etc. when referencing specific information
- Be concise but thorough
- If you're unsure, indicate your uncertainty"""

    user_prompt = f"""Context:
{context_text}

Question: {query}

Please answer the question based on the context above. Cite your sources."""

    return await provider.generate_with_fallback(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=0.3,  # Lower temperature for factual answers
    )


async def summarize_content(
    content: str,
    max_length: int = 200,
) -> AIResponse:
    """
    Generate a summary of content.

    Args:
        content: Content to summarize
        max_length: Target summary length in words

    Returns:
        AIResponse with summary
    """
    provider = await get_ai_provider()

    system_prompt = "You are a helpful assistant that creates concise summaries."

    user_prompt = f"""Please summarize the following content in approximately {max_length} words.
Focus on the key points and main ideas.

Content:
{content[:10000]}"""  # Limit content length

    return await provider.generate_with_fallback(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=512,
        temperature=0.5,
    )
