"""Tests for prompt templates module."""

import pytest

from mlx_hub.templates import (
    ModelFamily,
    PromptTemplate,
    detect_model_family,
    format_chat_prompt,
    get_template,
)


class TestModelFamilyDetection:
    """Tests for model family detection."""

    def test_detect_llama_family(self):
        """Test detecting Llama family models."""
        assert detect_model_family("meta-llama/Llama-3.1-8B-Instruct") == ModelFamily.LLAMA
        assert detect_model_family("mlx-community/Llama-3.2-3B-4bit") == ModelFamily.LLAMA
        assert detect_model_family("mlx-community/llama-3-8b") == ModelFamily.LLAMA

    def test_detect_mistral_family(self):
        """Test detecting Mistral family models."""
        assert detect_model_family("mistralai/Mistral-7B-Instruct-v0.2") == ModelFamily.MISTRAL
        assert detect_model_family("mlx-community/Mixtral-8x7B-4bit") == ModelFamily.MISTRAL
        assert detect_model_family("HuggingFaceH4/zephyr-7b-beta") == ModelFamily.MISTRAL

    def test_detect_qwen_family(self):
        """Test detecting Qwen family models."""
        assert detect_model_family("Qwen/Qwen2.5-7B-Instruct") == ModelFamily.QWEN
        assert detect_model_family("mlx-community/Qwen-VL-Chat") == ModelFamily.QWEN

    def test_detect_gemma_family(self):
        """Test detecting Gemma family models."""
        assert detect_model_family("google/gemma-2-9b-it") == ModelFamily.GEMMA
        assert detect_model_family("mlx-community/codegemma-7b") == ModelFamily.GEMMA

    def test_detect_phi_family(self):
        """Test detecting Phi family models."""
        assert detect_model_family("microsoft/Phi-3-mini-4k-instruct") == ModelFamily.PHI
        assert detect_model_family("mlx-community/phi-2") == ModelFamily.PHI

    def test_detect_chatml_family(self):
        """Test detecting ChatML family models."""
        assert detect_model_family("cognitivecomputations/dolphin-2.9") == ModelFamily.CHATML
        assert detect_model_family("NousResearch/Hermes-2-Pro") == ModelFamily.CHATML

    def test_unknown_model_defaults_to_chatml(self):
        """Test that unknown models default to ChatML."""
        assert detect_model_family("some-random-model") == ModelFamily.CHATML
        assert detect_model_family("unknown/model-name") == ModelFamily.CHATML


class TestPromptTemplate:
    """Tests for prompt template formatting."""

    def test_llama_template_format(self):
        """Test Llama prompt formatting."""
        template = get_template(ModelFamily.LLAMA)
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ]
        prompt = template.format_chat(messages)

        assert "<|begin_of_text|>" in prompt
        assert "system" in prompt
        assert "You are helpful." in prompt
        assert "user" in prompt
        assert "Hello!" in prompt
        assert "<|start_header_id|>assistant<|end_header_id|>" in prompt

    def test_mistral_template_format(self):
        """Test Mistral prompt formatting."""
        template = get_template(ModelFamily.MISTRAL)
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ]
        prompt = template.format_chat(messages)

        assert "<s>" in prompt
        assert "[INST]" in prompt
        assert "Hello!" in prompt
        assert "[/INST]" in prompt

    def test_qwen_template_format(self):
        """Test Qwen prompt formatting."""
        template = get_template(ModelFamily.QWEN)
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
        ]
        prompt = template.format_chat(messages)

        assert "<|im_start|>system" in prompt
        assert "<|im_start|>user" in prompt
        assert "<|im_start|>assistant" in prompt
        assert "<|im_end|>" in prompt

    def test_format_without_generation_prompt(self):
        """Test formatting without generation prompt."""
        template = get_template(ModelFamily.LLAMA)
        messages = [
            {"role": "user", "content": "Hello!"},
        ]
        prompt = template.format_chat(messages, add_generation_prompt=False)

        # Should not end with assistant header
        assert not prompt.endswith("<|start_header_id|>assistant<|end_header_id|>\n\n")


class TestFormatChatPrompt:
    """Tests for the format_chat_prompt convenience function."""

    def test_format_with_model_name(self):
        """Test formatting with model name auto-detection."""
        messages = [{"role": "user", "content": "Hi"}]
        prompt, stops = format_chat_prompt(
            messages=messages,
            model_name="meta-llama/Llama-3.1-8B",
        )

        assert "<|begin_of_text|>" in prompt
        assert "<|eot_id|>" in stops

    def test_format_with_explicit_family(self):
        """Test formatting with explicit family."""
        messages = [{"role": "user", "content": "Hi"}]
        prompt, stops = format_chat_prompt(
            messages=messages,
            family=ModelFamily.QWEN,
        )

        assert "<|im_start|>" in prompt
        assert "<|im_end|>" in stops

    def test_format_returns_stop_sequences(self):
        """Test that stop sequences are returned."""
        messages = [{"role": "user", "content": "Hi"}]
        _, stops = format_chat_prompt(
            messages=messages,
            family=ModelFamily.LLAMA,
        )

        assert isinstance(stops, list)
        assert len(stops) > 0
        assert "<|eot_id|>" in stops


class TestStopSequences:
    """Tests for stop sequences in templates."""

    def test_llama_stop_sequences(self):
        """Test Llama stop sequences."""
        template = get_template(ModelFamily.LLAMA)
        assert "<|eot_id|>" in template.stop_sequences
        assert "<|end_of_text|>" in template.stop_sequences

    def test_qwen_stop_sequences(self):
        """Test Qwen stop sequences."""
        template = get_template(ModelFamily.QWEN)
        assert "<|im_end|>" in template.stop_sequences

    def test_mistral_stop_sequences(self):
        """Test Mistral stop sequences."""
        template = get_template(ModelFamily.MISTRAL)
        assert "</s>" in template.stop_sequences
