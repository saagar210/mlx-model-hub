"""LLM service with provider abstraction.

Supports:
- Ollama (FREE, local) - default
- Anthropic Claude (PAID, best quality) - upgrade path
- OpenRouter (MIXED, various models) - alternative
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from knowledge_engine.config import LLMProvider, Settings, get_settings

logger = logging.getLogger(__name__)

# RAG prompt template with citations
RAG_PROMPT_TEMPLATE = """Answer the question based on the context below. Use citations like [1], [2] to reference sources.
If the answer isn't clearly in the context, say "I don't have enough information to answer this question."

Context:
{context}

Question: {question}

Answer:"""


class BaseLLMService(ABC):
    """Abstract base for LLM services."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate text response."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate streaming text response."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get model name."""
        pass


class OllamaLLMService(BaseLLMService):
    """Ollama LLM service - FREE, local."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.ollama_base_url,
                timeout=120.0,  # LLM can be slow
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate text using Ollama."""
        client = await self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.post(
            "/api/chat",
            json={
                "model": self._settings.ollama_llm_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            },
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate streaming text using Ollama."""
        client = await self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with client.stream(
            "POST",
            "/api/chat",
            json={
                "model": self._settings.ollama_llm_model,
                "messages": messages,
                "stream": True,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            },
        ) as response:
            response.raise_for_status()
            import json as json_lib
            async for line in response.aiter_lines():
                if line:
                    data = json_lib.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]

    @property
    def model_name(self) -> str:
        return f"ollama/{self._settings.ollama_llm_model}"


class AnthropicLLMService(BaseLLMService):
    """Anthropic Claude LLM service - PAID, best quality."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import anthropic

            api_key = (
                self._settings.anthropic_api_key.get_secret_value()
                if self._settings.anthropic_api_key
                else None
            )
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY required for Anthropic LLM")
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate text using Claude."""
        client = await self._get_client()

        kwargs = {
            "model": self._settings.anthropic_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await client.messages.create(**kwargs)
        return response.content[0].text

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate streaming text using Claude."""
        client = await self._get_client()

        kwargs = {
            "model": self._settings.anthropic_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    @property
    def model_name(self) -> str:
        return f"anthropic/{self._settings.anthropic_model}"


class LLMService:
    """
    Unified LLM service with provider abstraction.

    Default: Ollama (FREE)
    Upgrade: Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._provider: BaseLLMService | None = None

    def _get_provider(self) -> BaseLLMService:
        """Get or create the LLM provider."""
        if self._provider is None:
            if self._settings.llm_provider == LLMProvider.ANTHROPIC:
                logger.info("Using Anthropic Claude LLM (PAID)")
                self._provider = AnthropicLLMService(self._settings)
            else:
                logger.info("Using Ollama LLM (FREE)")
                self._provider = OllamaLLMService(self._settings)
        return self._provider

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate text response."""
        return await self._get_provider().generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate streaming text response."""
        async for chunk in self._get_provider().generate_stream(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            yield chunk

    async def generate_rag_answer(
        self,
        question: str,
        context_chunks: list[dict],
        max_tokens: int = 2048,
    ) -> tuple[str, list[int]]:
        """
        Generate RAG answer with citations.

        Returns:
            tuple of (answer, list of cited indices)
        """
        # Build context with numbered citations
        context_parts = []
        for i, chunk in enumerate(context_chunks, 1):
            context_parts.append(f"[{i}] {chunk['content']}")

        context = "\n\n".join(context_parts)
        prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)

        system_prompt = (
            "You are a helpful assistant that answers questions based on provided context. "
            "Always cite your sources using [1], [2], etc. Be concise and accurate."
        )

        answer = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=0.3,  # Lower temperature for factual answers
        )

        # Extract citations from answer
        import re
        citations = list(set(int(m) for m in re.findall(r'\[(\d+)\]', answer)))

        return answer, citations

    @property
    def model_name(self) -> str:
        """Get current model name."""
        return self._get_provider().model_name
