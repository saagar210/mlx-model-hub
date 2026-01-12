"""Chat service for text generation."""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator, Iterator

from ..cache import response_cache
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

    def generate(
        self,
        messages: list[dict],
        model_path: str,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        use_cache: bool = True,
    ) -> ChatResult:
        """Generate a chat completion (non-streaming)."""
        from mlx_lm import generate
        from mlx_lm.generate import make_sampler

        self._ensure_model(model_path)

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Check cache
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

        # Generate
        sampler = make_sampler(temp=temperature, top_p=top_p)
        result = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=sampler,
            verbose=False,
        )
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
    ) -> Iterator[StreamChunk]:
        """Stream chat completion tokens."""
        from mlx_lm import stream_generate
        from mlx_lm.generate import make_sampler

        self._ensure_model(model_path)

        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        sampler = make_sampler(temp=temperature, top_p=top_p)

        for response in stream_generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=sampler,
        ):
            yield StreamChunk(text=response.text)

        # Final chunk
        yield StreamChunk(text="", finish_reason="stop")


# Singleton instance
chat_service = ChatService()
