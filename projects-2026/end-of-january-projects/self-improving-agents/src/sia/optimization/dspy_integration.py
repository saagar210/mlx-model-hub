"""
DSPy Integration Module.

Configures DSPy to work with SIA's LLM routing.
"""

from __future__ import annotations

import os
from typing import Any

import dspy

from sia.config import get_config


class SIALanguageModel(dspy.LM):
    """
    Custom DSPy Language Model that uses SIA's LLM infrastructure.

    Routes through Ollama by default, with cloud fallback.
    """

    def __init__(
        self,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ):
        """
        Initialize SIA language model for DSPy.

        Args:
            model: Model name (default: from config)
            api_base: API base URL (default: Ollama)
            api_key: API key if needed
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments for dspy.LM
        """
        config = get_config()

        # Default to Ollama
        self.model = model or config.ollama.model
        self.api_base = api_base or config.ollama.base_url
        self.api_key = api_key or "ollama"  # Ollama doesn't need a key

        # For Ollama, use the OpenAI-compatible endpoint
        if "ollama" in self.api_base.lower() or "11434" in self.api_base:
            # Ollama's OpenAI-compatible endpoint
            provider = "openai"
            model_path = f"openai/{self.model}"
        else:
            provider = "openai"
            model_path = self.model

        super().__init__(
            model=model_path,
            api_base=self.api_base,
            api_key=self.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


def configure_dspy(
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    use_cloud: bool = False,
) -> dspy.LM:
    """
    Configure DSPy with SIA's LLM settings.

    Args:
        model: Override model name
        temperature: Sampling temperature
        max_tokens: Maximum tokens
        use_cloud: Use cloud provider instead of local

    Returns:
        Configured DSPy language model
    """
    config = get_config()

    if use_cloud:
        # Use DeepSeek or other cloud provider
        lm = dspy.LM(
            model=f"deepseek/{config.cloud.deepseek_model}",
            api_base=config.cloud.deepseek_base_url,
            api_key=config.cloud.deepseek_api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        # Use local Ollama
        lm = dspy.LM(
            model=f"ollama_chat/{model or config.ollama.model}",
            api_base=config.ollama.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    dspy.configure(lm=lm)
    return lm


def get_default_lm() -> dspy.LM:
    """Get the default configured language model."""
    config = get_config()
    return dspy.LM(
        model=f"ollama_chat/{config.ollama.model}",
        api_base=config.ollama.base_url,
        temperature=0.7,
        max_tokens=4096,
    )


class DSPyTracer:
    """
    Traces DSPy calls for debugging and metrics.
    """

    def __init__(self):
        self.traces: list[dict[str, Any]] = []

    def record(
        self,
        signature: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        latency_ms: float,
        tokens: int | None = None,
    ) -> None:
        """Record a DSPy call."""
        self.traces.append({
            "signature": signature,
            "inputs": inputs,
            "outputs": outputs,
            "latency_ms": latency_ms,
            "tokens": tokens,
        })

    def clear(self) -> None:
        """Clear recorded traces."""
        self.traces = []

    def get_stats(self) -> dict[str, Any]:
        """Get statistics from traces."""
        if not self.traces:
            return {"count": 0}

        latencies = [t["latency_ms"] for t in self.traces]
        return {
            "count": len(self.traces),
            "avg_latency_ms": sum(latencies) / len(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "total_tokens": sum(t.get("tokens", 0) or 0 for t in self.traces),
        }


# Global tracer instance
_tracer = DSPyTracer()


def get_tracer() -> DSPyTracer:
    """Get the global DSPy tracer."""
    return _tracer
