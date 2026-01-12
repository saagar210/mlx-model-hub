"""Prompt templates for different model families.

Each model family has specific prompt formatting requirements.
This module provides templates and utilities for formatting prompts
correctly based on the model being used.
"""

from dataclasses import dataclass
from enum import Enum


class ModelFamily(str, Enum):
    """Supported model families with distinct prompt formats."""

    LLAMA = "llama"
    MISTRAL = "mistral"
    QWEN = "qwen"
    GEMMA = "gemma"
    PHI = "phi"
    CHATML = "chatml"  # Generic ChatML format
    RAW = "raw"  # No special formatting


@dataclass
class PromptTemplate:
    """Template for formatting prompts for a specific model family."""

    family: ModelFamily
    system_prefix: str
    system_suffix: str
    user_prefix: str
    user_suffix: str
    assistant_prefix: str
    assistant_suffix: str
    bos_token: str = ""
    eos_token: str = ""
    stop_sequences: list[str] | None = None

    def format_message(self, role: str, content: str) -> str:
        """Format a single message."""
        if role == "system":
            return f"{self.system_prefix}{content}{self.system_suffix}"
        elif role == "user":
            return f"{self.user_prefix}{content}{self.user_suffix}"
        elif role == "assistant":
            return f"{self.assistant_prefix}{content}{self.assistant_suffix}"
        else:
            return content

    def format_chat(
        self,
        messages: list[dict[str, str]],
        add_generation_prompt: bool = True,
    ) -> str:
        """Format a list of chat messages into a prompt string.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            add_generation_prompt: Whether to add the assistant prefix at the end.

        Returns:
            Formatted prompt string.
        """
        formatted = self.bos_token

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            formatted += self.format_message(role, content)

        if add_generation_prompt:
            formatted += self.assistant_prefix

        return formatted


# Template definitions for each model family
TEMPLATES: dict[ModelFamily, PromptTemplate] = {
    ModelFamily.LLAMA: PromptTemplate(
        family=ModelFamily.LLAMA,
        bos_token="<|begin_of_text|>",
        system_prefix="<|start_header_id|>system<|end_header_id|>\n\n",
        system_suffix="<|eot_id|>",
        user_prefix="<|start_header_id|>user<|end_header_id|>\n\n",
        user_suffix="<|eot_id|>",
        assistant_prefix="<|start_header_id|>assistant<|end_header_id|>\n\n",
        assistant_suffix="<|eot_id|>",
        eos_token="<|end_of_text|>",
        stop_sequences=["<|eot_id|>", "<|end_of_text|>"],
    ),
    ModelFamily.MISTRAL: PromptTemplate(
        family=ModelFamily.MISTRAL,
        bos_token="<s>",
        system_prefix="[INST] ",
        system_suffix="\n\n",
        user_prefix="",
        user_suffix=" [/INST]",
        assistant_prefix="",
        assistant_suffix="</s>",
        eos_token="</s>",
        stop_sequences=["</s>", "[/INST]"],
    ),
    ModelFamily.QWEN: PromptTemplate(
        family=ModelFamily.QWEN,
        bos_token="",
        system_prefix="<|im_start|>system\n",
        system_suffix="<|im_end|>\n",
        user_prefix="<|im_start|>user\n",
        user_suffix="<|im_end|>\n",
        assistant_prefix="<|im_start|>assistant\n",
        assistant_suffix="<|im_end|>\n",
        eos_token="<|im_end|>",
        stop_sequences=["<|im_end|>", "<|endoftext|>"],
    ),
    ModelFamily.GEMMA: PromptTemplate(
        family=ModelFamily.GEMMA,
        bos_token="<bos>",
        system_prefix="",  # Gemma doesn't have system role, prepend to user
        system_suffix="",
        user_prefix="<start_of_turn>user\n",
        user_suffix="<end_of_turn>\n",
        assistant_prefix="<start_of_turn>model\n",
        assistant_suffix="<end_of_turn>\n",
        eos_token="<eos>",
        stop_sequences=["<end_of_turn>", "<eos>"],
    ),
    ModelFamily.PHI: PromptTemplate(
        family=ModelFamily.PHI,
        bos_token="",
        system_prefix="<|system|>\n",
        system_suffix="<|end|>\n",
        user_prefix="<|user|>\n",
        user_suffix="<|end|>\n",
        assistant_prefix="<|assistant|>\n",
        assistant_suffix="<|end|>\n",
        eos_token="<|endoftext|>",
        stop_sequences=["<|end|>", "<|endoftext|>"],
    ),
    ModelFamily.CHATML: PromptTemplate(
        family=ModelFamily.CHATML,
        bos_token="",
        system_prefix="<|im_start|>system\n",
        system_suffix="<|im_end|>\n",
        user_prefix="<|im_start|>user\n",
        user_suffix="<|im_end|>\n",
        assistant_prefix="<|im_start|>assistant\n",
        assistant_suffix="<|im_end|>\n",
        eos_token="<|im_end|>",
        stop_sequences=["<|im_end|>"],
    ),
    ModelFamily.RAW: PromptTemplate(
        family=ModelFamily.RAW,
        bos_token="",
        system_prefix="",
        system_suffix="\n\n",
        user_prefix="User: ",
        user_suffix="\n\n",
        assistant_prefix="Assistant: ",
        assistant_suffix="\n\n",
        eos_token="",
        stop_sequences=["User:", "\n\nUser"],
    ),
}


# Model name patterns for auto-detection
MODEL_FAMILY_PATTERNS: list[tuple[list[str], ModelFamily]] = [
    # Llama family
    (["llama-3", "llama3", "llama-2", "llama2", "meta-llama"], ModelFamily.LLAMA),
    # Mistral family
    (["mistral", "mixtral", "zephyr"], ModelFamily.MISTRAL),
    # Qwen family
    (["qwen", "qwen2", "qwen1.5", "qwen-vl"], ModelFamily.QWEN),
    # Gemma family
    (["gemma", "gemma-2", "codegemma"], ModelFamily.GEMMA),
    # Phi family
    (["phi-3", "phi-2", "phi3", "phi2"], ModelFamily.PHI),
    # ChatML (default for many fine-tuned models)
    (["chatml", "dolphin", "hermes", "openhermes"], ModelFamily.CHATML),
]


def detect_model_family(model_name: str) -> ModelFamily:
    """Detect the model family from the model name.

    Args:
        model_name: HuggingFace model ID or local path.

    Returns:
        Detected ModelFamily, defaults to CHATML if unknown.
    """
    model_lower = model_name.lower()

    for patterns, family in MODEL_FAMILY_PATTERNS:
        for pattern in patterns:
            if pattern in model_lower:
                return family

    # Default to ChatML for unknown models (widely compatible)
    return ModelFamily.CHATML


def get_template(family: ModelFamily) -> PromptTemplate:
    """Get the prompt template for a model family.

    Args:
        family: The model family.

    Returns:
        PromptTemplate for the specified family.
    """
    return TEMPLATES.get(family, TEMPLATES[ModelFamily.CHATML])


def format_chat_prompt(
    messages: list[dict[str, str]],
    model_name: str | None = None,
    family: ModelFamily | None = None,
    add_generation_prompt: bool = True,
) -> tuple[str, list[str]]:
    """Format chat messages into a prompt string with stop sequences.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        model_name: Model name for auto-detection (optional if family provided).
        family: Explicit model family (takes precedence over model_name).
        add_generation_prompt: Whether to add assistant prefix at end.

    Returns:
        Tuple of (formatted_prompt, stop_sequences).
    """
    if family is None:
        if model_name:
            family = detect_model_family(model_name)
        else:
            family = ModelFamily.CHATML

    template = get_template(family)
    prompt = template.format_chat(messages, add_generation_prompt)
    stop_sequences = template.stop_sequences or []

    return prompt, stop_sequences


def get_default_system_message(family: ModelFamily | None = None) -> str:
    """Get a sensible default system message.

    Args:
        family: Model family for family-specific defaults.

    Returns:
        Default system message string.
    """
    return (
        "You are a helpful AI assistant. You provide accurate, helpful, "
        "and harmless responses to user queries."
    )
