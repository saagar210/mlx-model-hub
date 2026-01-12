"""Chat service for text generation."""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Iterator

from ..cache import response_cache, get_prompt_cache_service
from ..config import settings
from ..models import model_manager
from .model_registry import model_registry

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    """Result from a chat completion."""
    text: str
    prompt_tokens: int
    completion_tokens: int
    cached: bool = False


@dataclass
class StreamChunk:
    """A chunk from streaming generation."""
    text: str
    finish_reason: str | None = None


class ChatService:
    """Service for chat completions using MLX LM models."""

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._current_model_path = None

    def _ensure_model(self, model_path: str, force_reload: bool = False):
        """Ensure model is loaded.

        Checks the model registry first for registered LoRA models,
        then falls back to the default model manager.
        """
        # Check if this is a registered model (e.g., LoRA from mlx-model-hub)
        registered = model_registry.get_model(model_path)
        if registered and registered.model_type == "lora":
            logger.info(f"Using registered LoRA model: {model_path}")
            self._model, self._tokenizer = model_registry.load_model(model_path)
        else:
            # Fall back to standard model loading
            self._model, self._tokenizer = model_manager.get_text_model(
                model_path, force_reload=force_reload
            )
        self._current_model_path = model_path

    def _extract_system_prompt(self, messages: list[dict]) -> str | None:
        """Extract system prompt from messages if present."""
        for msg in messages:
            if msg.get("role") == "system":
                return msg.get("content", "")
        return None

    def _get_prompt_cache(self, model_path: str, system_prompt: str | None) -> Any:
        """Get or create a prompt cache for the system prompt.

        Returns a prompt cache pre-filled with the system prompt KV states,
        or None if prompt caching is disabled or no system prompt.
        """
        if not settings.prompt_cache_enabled or not system_prompt:
            return None

        try:
            cache_service = get_prompt_cache_service()

            # Format system prompt the same way it will appear in the full prompt
            system_messages = [{"role": "system", "content": system_prompt}]
            formatted_system = self._tokenizer.apply_chat_template(
                system_messages, tokenize=False, add_generation_prompt=False
            )

            # Get or create cache for this system prompt
            return cache_service.get_or_create(
                model=self._model,
                tokenizer=self._tokenizer,
                prompt=formatted_system,
                model_id=model_path,
            )
        except Exception as e:
            logger.warning(f"Failed to get prompt cache: {e}")
            return None

    def generate(
        self,
        messages: list[dict],
        model_path: str,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        use_cache: bool = True,
        use_prompt_cache: bool = True,
    ) -> ChatResult:
        """Generate a chat completion (non-streaming).

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model_path: Model identifier.
            temperature: Sampling temperature.
            top_p: Nucleus sampling threshold.
            max_tokens: Maximum tokens to generate.
            use_cache: Whether to use response caching (full response).
            use_prompt_cache: Whether to use KV cache for system prompts.
        """
        from mlx_lm import generate
        from mlx_lm.generate import make_sampler

        self._ensure_model(model_path)

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Check response cache (full response)
        if use_cache:
            cache_params = {"temperature": temperature, "max_tokens": max_tokens}
            cached = response_cache.get(prompt, model_path, **cache_params)
            if cached:
                logger.info("Returning cached response")
                return ChatResult(
                    text=cached,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cached=True,
                )

        # Get prompt cache for system prompt (KV cache)
        prompt_cache = None
        if use_prompt_cache:
            system_prompt = self._extract_system_prompt(messages)
            prompt_cache = self._get_prompt_cache(model_path, system_prompt)
            if prompt_cache:
                logger.info("Using KV cache for system prompt")

        # Generate
        sampler = make_sampler(temp=temperature, top_p=top_p)
        generate_kwargs = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "sampler": sampler,
            "verbose": False,
        }

        # Add prompt_cache if available
        if prompt_cache is not None:
            generate_kwargs["prompt_cache"] = prompt_cache

        result = generate(self._model, self._tokenizer, **generate_kwargs)
        response_text = result.text if hasattr(result, "text") else str(result)

        # Cache result
        if use_cache:
            response_cache.set(prompt, model_path, response_text, **cache_params)

        # Count tokens
        prompt_tokens = len(self._tokenizer.encode(prompt))
        completion_tokens = len(self._tokenizer.encode(response_text))

        return ChatResult(
            text=response_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def stream_generate(
        self,
        messages: list[dict],
        model_path: str,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        use_prompt_cache: bool = True,
    ) -> Iterator[StreamChunk]:
        """Stream chat completion tokens.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model_path: Model identifier.
            temperature: Sampling temperature.
            top_p: Nucleus sampling threshold.
            max_tokens: Maximum tokens to generate.
            use_prompt_cache: Whether to use KV cache for system prompts.
        """
        from mlx_lm import stream_generate
        from mlx_lm.generate import make_sampler

        self._ensure_model(model_path)

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Get prompt cache for system prompt (KV cache)
        prompt_cache = None
        if use_prompt_cache:
            system_prompt = self._extract_system_prompt(messages)
            prompt_cache = self._get_prompt_cache(model_path, system_prompt)
            if prompt_cache:
                logger.info("Using KV cache for streaming generation")

        sampler = make_sampler(temp=temperature, top_p=top_p)

        stream_kwargs = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "sampler": sampler,
        }

        # Add prompt_cache if available
        if prompt_cache is not None:
            stream_kwargs["prompt_cache"] = prompt_cache

        for response in stream_generate(
            self._model,
            self._tokenizer,
            **stream_kwargs,
        ):
            yield StreamChunk(text=response.text)

        # Final chunk
        yield StreamChunk(text="", finish_reason="stop")


# Singleton instance
chat_service = ChatService()
