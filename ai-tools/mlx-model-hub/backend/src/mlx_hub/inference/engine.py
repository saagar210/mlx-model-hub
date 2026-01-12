"""Inference engine for model serving."""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mlx.core as mx

from mlx_hub.config import Settings, get_settings
from mlx_hub.inference.cache import CachedModel, get_model_cache

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for text generation."""

    max_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    stop_sequences: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "GenerationConfig":
        """Create config from dictionary."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known_fields})


@dataclass
class GenerationResult:
    """Result of text generation."""

    text: str
    tokens_generated: int
    time_to_first_token: float  # TTFT in seconds
    total_time: float  # Total generation time in seconds
    tokens_per_second: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "tokens_generated": self.tokens_generated,
            "time_to_first_token": self.time_to_first_token,
            "total_time": self.total_time,
            "tokens_per_second": self.tokens_per_second,
        }


class InferenceEngine:
    """Engine for running model inference.

    Handles model loading, caching, and generation with support
    for both synchronous and streaming modes.
    """

    def __init__(self, settings: Settings | None = None):
        """Initialize the inference engine.

        Args:
            settings: Application settings (optional).
        """
        self.settings = settings or get_settings()
        self.cache = get_model_cache()
        self._generation_lock = asyncio.Lock()

    async def load_model(
        self,
        base_model: str,
        adapter_path: str | None = None,
    ) -> CachedModel:
        """Load a model (or retrieve from cache).

        Args:
            base_model: HuggingFace model ID or local path.
            adapter_path: Optional path to LoRA adapter weights.

        Returns:
            CachedModel with model and tokenizer.
        """
        # Create cache key
        cache_key = base_model
        if adapter_path:
            cache_key = f"{base_model}:{adapter_path}"

        # Check cache
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Load model
        logger.info(f"Loading model: {base_model}")
        start_time = time.time()

        try:
            from mlx_lm import load

            model, tokenizer = load(
                base_model,
                tokenizer_config={"trust_remote_code": True},
            )

            # Load adapter if provided
            if adapter_path:
                model = await self._load_adapter(model, adapter_path)

            load_time = time.time() - start_time
            logger.info(f"Model loaded in {load_time:.2f}s")

            # Estimate memory usage (rough estimate based on model size)
            estimated_memory_gb = self._estimate_memory(model)

            # Cache the model
            return self.cache.put(
                key=cache_key,
                model=model,
                tokenizer=tokenizer,
                adapter_path=adapter_path,
                estimated_memory_gb=estimated_memory_gb,
            )

        except Exception as e:
            logger.error(f"Failed to load model {base_model}: {e}")
            raise ValueError(f"Failed to load model: {e}") from e

    async def _load_adapter(self, model: Any, adapter_path: str) -> Any:
        """Load LoRA adapter weights into model.

        Args:
            model: Base MLX model.
            adapter_path: Path to adapter safetensors file.

        Returns:
            Model with adapter weights loaded.
        """
        adapter_file = Path(adapter_path)
        if not adapter_file.exists():
            raise ValueError(f"Adapter not found: {adapter_path}")

        logger.info(f"Loading adapter: {adapter_path}")

        try:
            # Load adapter weights
            adapter_weights = mx.load(str(adapter_file))

            # Apply weights to model (merge or keep separate)
            # This depends on how LoRA was applied during training
            from mlx_lm.tuner.utils import apply_lora_layers

            # The adapter config should be in the same directory
            config_path = adapter_file.parent / "config.json"
            if config_path.exists():
                import json

                with open(config_path) as f:
                    config = json.load(f)

                lora_rank = config.get("lora_rank", 16)
                lora_alpha = config.get("lora_alpha", 32)

                # Apply LoRA structure to model
                apply_lora_layers(
                    model,
                    num_lora_layers=-1,  # All layers
                    lora_parameters={
                        "rank": lora_rank,
                        "alpha": lora_alpha,
                        "dropout": 0.0,
                        "scale": lora_alpha / lora_rank,
                    },
                )

            # Load the actual weights
            model.load_weights(adapter_weights, strict=False)
            mx.eval(model.parameters())

            return model

        except Exception as e:
            logger.error(f"Failed to load adapter: {e}")
            raise ValueError(f"Failed to load adapter: {e}") from e

    def _estimate_memory(self, model: Any) -> float:
        """Estimate model memory usage in GB.

        Args:
            model: MLX model.

        Returns:
            Estimated memory in GB.
        """
        try:
            from mlx.utils import tree_flatten

            total_bytes = 0
            for _, param in tree_flatten(model.parameters()):
                total_bytes += param.nbytes

            return total_bytes / (1024**3)
        except Exception:
            # Default estimate for typical 7B 4-bit model
            return 4.0

    async def generate(
        self,
        cached_model: CachedModel,
        prompt: str,
        config: GenerationConfig | None = None,
    ) -> GenerationResult:
        """Generate text from a prompt.

        Args:
            cached_model: Cached model to use.
            prompt: Input prompt text.
            config: Generation configuration.

        Returns:
            GenerationResult with generated text and metrics.
        """
        config = config or GenerationConfig()
        cached_model.touch()

        # Single generation at a time (memory constraint)
        async with self._generation_lock:
            start_time = time.time()
            first_token_time: float | None = None
            generated_tokens = 0
            generated_text = ""

            try:
                from mlx_lm import generate

                # Tokenize prompt
                tokens = cached_model.tokenizer.encode(prompt)

                # Generate
                result = generate(
                    model=cached_model.model,
                    tokenizer=cached_model.tokenizer,
                    prompt=prompt,
                    max_tokens=config.max_tokens,
                    temp=config.temperature,
                    top_p=config.top_p,
                    repetition_penalty=config.repetition_penalty,
                )

                first_token_time = time.time()
                generated_text = result
                generated_tokens = len(cached_model.tokenizer.encode(result)) - len(
                    tokens
                )

            except Exception as e:
                logger.error(f"Generation failed: {e}")
                raise ValueError(f"Generation failed: {e}") from e

            total_time = time.time() - start_time
            ttft = (first_token_time - start_time) if first_token_time else total_time
            tokens_per_second = (
                generated_tokens / total_time if total_time > 0 else 0.0
            )

            return GenerationResult(
                text=generated_text,
                tokens_generated=generated_tokens,
                time_to_first_token=ttft,
                total_time=total_time,
                tokens_per_second=tokens_per_second,
            )

    async def generate_stream(
        self,
        cached_model: CachedModel,
        prompt: str,
        config: GenerationConfig | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Generate text with streaming output.

        Args:
            cached_model: Cached model to use.
            prompt: Input prompt text.
            config: Generation configuration.

        Yields:
            Dictionary with token text and metadata.
        """
        config = config or GenerationConfig()
        cached_model.touch()

        async with self._generation_lock:
            start_time = time.time()
            first_token_time: float | None = None
            total_tokens = 0

            try:
                from mlx_lm import stream_generate

                # Stream generation
                for token_text in stream_generate(
                    model=cached_model.model,
                    tokenizer=cached_model.tokenizer,
                    prompt=prompt,
                    max_tokens=config.max_tokens,
                    temp=config.temperature,
                    top_p=config.top_p,
                    repetition_penalty=config.repetition_penalty,
                ):
                    if first_token_time is None:
                        first_token_time = time.time()
                        ttft = first_token_time - start_time

                        # First yield includes TTFT
                        yield {
                            "token": token_text,
                            "ttft": ttft,
                            "index": total_tokens,
                        }
                    else:
                        yield {
                            "token": token_text,
                            "index": total_tokens,
                        }

                    total_tokens += 1

                    # Check stop sequences
                    # This is simplified - in practice need to check accumulated text
                    if config.stop_sequences and any(
                        seq in token_text for seq in config.stop_sequences
                    ):
                        break

                    # Allow other tasks to run
                    await asyncio.sleep(0)

            except Exception as e:
                logger.error(f"Stream generation failed: {e}")
                yield {"error": str(e)}
                return

            # Final summary
            total_time = time.time() - start_time
            yield {
                "done": True,
                "total_tokens": total_tokens,
                "total_time": total_time,
                "tokens_per_second": total_tokens / total_time if total_time > 0 else 0,
            }

    def unload_model(self, cache_key: str) -> bool:
        """Unload a model from cache.

        Args:
            cache_key: Cache key for the model.

        Returns:
            True if unloaded, False if not found.
        """
        return self.cache.remove(cache_key)

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        return self.cache.stats()


# Global engine instance
_inference_engine: InferenceEngine | None = None


def get_inference_engine() -> InferenceEngine:
    """Get the global inference engine instance."""
    global _inference_engine
    if _inference_engine is None:
        _inference_engine = InferenceEngine()
    return _inference_engine
