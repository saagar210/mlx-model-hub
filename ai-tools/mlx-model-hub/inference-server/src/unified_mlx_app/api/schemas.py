"""OpenAI-compatible API schemas."""

from typing import Literal

from pydantic import BaseModel, Field


# Chat Completions
class ChatMessage(BaseModel):
    """A single chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str = "mlx-community/Qwen2.5-7B-Instruct-4bit"
    messages: list[ChatMessage]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    stream: bool = False


class ChatCompletionChoice(BaseModel):
    """A single completion choice."""

    index: int
    message: ChatMessage
    finish_reason: str | None = None


class Usage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage


class ChatCompletionChunk(BaseModel):
    """Streaming chunk for chat completions."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[dict]


# Audio Speech
class SpeechRequest(BaseModel):
    """OpenAI-compatible TTS request."""

    model: str = "mlx-community/Kokoro-82M-bf16"
    input: str
    voice: str = "a"  # American English
    response_format: Literal["wav", "mp3"] = "wav"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


# Models
class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str
    object: str = "model"
    created: int
    owned_by: str = "mlx-community"


class ModelList(BaseModel):
    """List of available models."""

    object: str = "list"
    data: list[ModelInfo]


# Vision
class VisionRequest(BaseModel):
    """Vision analysis request."""

    model: str = "mlx-community/Qwen2-VL-2B-Instruct-4bit"
    prompt: str = "Describe this image in detail."
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class VisionResponse(BaseModel):
    """Vision analysis response."""

    text: str
    prompt_tokens: int
    generation_tokens: int


# Health
class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    models: dict
