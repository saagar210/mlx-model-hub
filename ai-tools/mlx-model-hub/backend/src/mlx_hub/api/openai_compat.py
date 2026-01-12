"""OpenAI-compatible API endpoints.

Provides drop-in replacement endpoints for OpenAI API, enabling
use with existing tools like LangChain, LlamaIndex, and OpenAI SDK.

Endpoints:
- POST /v1/chat/completions - Chat completion (streaming and non-streaming)
- POST /v1/completions - Text completion (legacy)
- GET /v1/models - List available models
"""

import json
import logging
import time
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from mlx_hub.db.models import Model
from mlx_hub.db.session import SessionDep
from mlx_hub.inference import (
    GenerationConfig,
    InferenceEngine,
    get_inference_engine,
)
from mlx_hub.templates import detect_model_family, format_chat_prompt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["openai-compatible"])


# ============== Request/Response Schemas (OpenAI-compatible) ==============


class ChatMessage(BaseModel):
    """OpenAI-compatible chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str
    messages: list[ChatMessage]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=1)
    stream: bool = False
    stop: list[str] | str | None = None
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    n: int = Field(default=1, ge=1, le=1)  # Only support n=1 for now
    user: str | None = None


class CompletionRequest(BaseModel):
    """OpenAI-compatible text completion request."""

    model: str
    prompt: str | list[str]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=256, ge=1)
    stream: bool = False
    stop: list[str] | str | None = None
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    n: int = Field(default=1, ge=1, le=1)
    echo: bool = False
    user: str | None = None


class ChatCompletionChoice(BaseModel):
    """Choice in a chat completion response."""

    index: int
    message: ChatMessage
    finish_reason: str | None = "stop"


class ChatCompletionChunkChoice(BaseModel):
    """Choice in a streaming chat completion response."""

    index: int
    delta: dict
    finish_reason: str | None = None


class Usage(BaseModel):
    """Token usage information."""

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
    """OpenAI-compatible streaming chat completion chunk."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionChunkChoice]


class CompletionChoice(BaseModel):
    """Choice in a completion response."""

    text: str
    index: int
    finish_reason: str | None = "stop"


class CompletionResponse(BaseModel):
    """OpenAI-compatible completion response."""

    id: str
    object: str = "text_completion"
    created: int
    model: str
    choices: list[CompletionChoice]
    usage: Usage


class ModelInfo(BaseModel):
    """OpenAI-compatible model information."""

    id: str
    object: str = "model"
    created: int
    owned_by: str = "mlx-hub"
    permission: list = []
    root: str | None = None
    parent: str | None = None


class ModelList(BaseModel):
    """OpenAI-compatible model list response."""

    object: str = "list"
    data: list[ModelInfo]


# ============== Dependencies ==============


def get_engine() -> InferenceEngine:
    """Get inference engine dependency."""
    return get_inference_engine()


EngineDep = Annotated[InferenceEngine, Depends(get_engine)]


# ============== Helper Functions ==============


async def resolve_model(
    session: SessionDep,
    model_id: str,
) -> tuple[Model | None, str]:
    """Resolve model ID to model object or base_model string.

    Supports:
    - UUID: Look up in database
    - Model name: Look up by name in database
    - HuggingFace ID: Use directly as base_model

    Returns:
        Tuple of (Model or None, base_model_string)
    """
    # Try UUID first
    try:
        from uuid import UUID as UUIDType

        model_uuid = UUIDType(model_id)
        model = await session.get(Model, model_uuid)
        if model:
            return model, model.base_model
    except ValueError:
        pass

    # Try by name
    result = await session.execute(select(Model).where(Model.name == model_id))
    model = result.scalars().first()
    if model:
        return model, model.base_model

    # Try by base_model
    result = await session.execute(select(Model).where(Model.base_model == model_id))
    model = result.scalars().first()
    if model:
        return model, model.base_model

    # Use as direct HuggingFace ID
    return None, model_id


def normalize_stop_sequences(
    stop: list[str] | str | None,
    template_stops: list[str],
) -> list[str]:
    """Normalize stop sequences from request and template."""
    result = list(template_stops)

    if stop is None:
        return result
    elif isinstance(stop, str):
        result.append(stop)
    else:
        result.extend(stop)

    return list(set(result))  # Deduplicate


# ============== Endpoints ==============


@router.get("/models", response_model=ModelList)
async def list_models(session: SessionDep) -> ModelList:
    """List available models (OpenAI-compatible).

    Returns models registered in the hub in OpenAI API format.
    """
    result = await session.execute(select(Model).order_by(Model.created_at.desc()))
    models = result.scalars().all()

    data = []
    for model in models:
        created_ts = int(model.created_at.timestamp()) if model.created_at else 0
        data.append(
            ModelInfo(
                id=model.name,  # Use name as ID for easier use
                created=created_ts,
                owned_by="mlx-hub",
                root=model.base_model,
            )
        )

    return ModelList(data=data)


@router.get("/models/{model_id}", response_model=ModelInfo)
async def get_model_info(
    model_id: str,
    session: SessionDep,
) -> ModelInfo:
    """Get model information (OpenAI-compatible)."""
    model, base_model = await resolve_model(session, model_id)

    if model:
        created_ts = int(model.created_at.timestamp()) if model.created_at else 0
        return ModelInfo(
            id=model.name,
            created=created_ts,
            owned_by="mlx-hub",
            root=model.base_model,
        )

    # Return info for unregistered model
    return ModelInfo(
        id=model_id,
        created=int(time.time()),
        owned_by="huggingface",
        root=base_model,
    )


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    session: SessionDep,
    engine: EngineDep,
):
    """Create chat completion (OpenAI-compatible).

    Supports both streaming and non-streaming modes.
    """
    # Resolve model
    model, base_model = await resolve_model(session, request.model)

    # Detect model family for correct prompt formatting
    family = detect_model_family(base_model)

    # Format messages into prompt
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    prompt, template_stops = format_chat_prompt(
        messages=messages,
        family=family,
        add_generation_prompt=True,
    )

    # Combine stop sequences
    stop_sequences = normalize_stop_sequences(request.stop, template_stops)

    # Set max tokens (default varies by model, use 2048 as sensible default)
    max_tokens = request.max_tokens or 2048

    # Load model
    try:
        cached_model = await engine.load_model(base_model=base_model)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to load model: {e}",
        ) from e

    # Create generation config
    # Map frequency_penalty to repetition_penalty (approximation)
    repetition_penalty = 1.0 + request.frequency_penalty * 0.5

    gen_config = GenerationConfig(
        max_tokens=max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        repetition_penalty=repetition_penalty,
        stop_sequences=stop_sequences,
    )

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_name = model.name if model else base_model

    if request.stream:
        return await _stream_chat_completion(
            engine=engine,
            cached_model=cached_model,
            prompt=prompt,
            config=gen_config,
            completion_id=completion_id,
            created=created,
            model_name=model_name,
        )
    else:
        return await _generate_chat_completion(
            engine=engine,
            cached_model=cached_model,
            prompt=prompt,
            config=gen_config,
            completion_id=completion_id,
            created=created,
            model_name=model_name,
        )


async def _generate_chat_completion(
    engine: InferenceEngine,
    cached_model,
    prompt: str,
    config: GenerationConfig,
    completion_id: str,
    created: int,
    model_name: str,
) -> ChatCompletionResponse:
    """Generate non-streaming chat completion."""
    result = await engine.generate(
        cached_model=cached_model,
        prompt=prompt,
        config=config,
    )

    # Estimate prompt tokens (rough approximation)
    prompt_tokens = len(prompt.split()) * 4 // 3

    return ChatCompletionResponse(
        id=completion_id,
        created=created,
        model=model_name,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=result.text),
                finish_reason="stop",
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=result.tokens_generated,
            total_tokens=prompt_tokens + result.tokens_generated,
        ),
    )


async def _stream_chat_completion(
    engine: InferenceEngine,
    cached_model,
    prompt: str,
    config: GenerationConfig,
    completion_id: str,
    created: int,
    model_name: str,
):
    """Generate streaming chat completion."""

    async def event_generator():
        accumulated_text = ""

        async for chunk in engine.generate_stream(
            cached_model=cached_model,
            prompt=prompt,
            config=config,
        ):
            if "error" in chunk:
                # Send error as final chunk
                error_chunk = ChatCompletionChunk(
                    id=completion_id,
                    created=created,
                    model=model_name,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta={},
                            finish_reason="error",
                        )
                    ],
                )
                yield {
                    "data": error_chunk.model_dump_json(),
                }
                yield {"data": "[DONE]"}
                return

            if chunk.get("done"):
                # Final chunk with finish reason
                final_chunk = ChatCompletionChunk(
                    id=completion_id,
                    created=created,
                    model=model_name,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta={},
                            finish_reason="stop",
                        )
                    ],
                )
                yield {
                    "data": final_chunk.model_dump_json(),
                }
                yield {"data": "[DONE]"}
            else:
                token = chunk.get("token", "")
                accumulated_text += token

                token_chunk = ChatCompletionChunk(
                    id=completion_id,
                    created=created,
                    model=model_name,
                    choices=[
                        ChatCompletionChunkChoice(
                            index=0,
                            delta={"content": token},
                            finish_reason=None,
                        )
                    ],
                )
                yield {
                    "data": token_chunk.model_dump_json(),
                }

    return EventSourceResponse(event_generator())


@router.post("/completions")
async def completions(
    request: CompletionRequest,
    session: SessionDep,
    engine: EngineDep,
):
    """Create text completion (OpenAI-compatible, legacy endpoint).

    This is the older completion API. For chat-based models, use
    /v1/chat/completions instead.
    """
    # Handle single prompt or list
    prompt = request.prompt if isinstance(request.prompt, str) else request.prompt[0]

    # Resolve model
    model, base_model = await resolve_model(session, request.model)

    # Set max tokens
    max_tokens = request.max_tokens or 256

    # Stop sequences
    stop_sequences = []
    if request.stop:
        if isinstance(request.stop, str):
            stop_sequences = [request.stop]
        else:
            stop_sequences = list(request.stop)

    # Load model
    try:
        cached_model = await engine.load_model(base_model=base_model)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to load model: {e}",
        ) from e

    # Create generation config
    repetition_penalty = 1.0 + request.frequency_penalty * 0.5

    gen_config = GenerationConfig(
        max_tokens=max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
        repetition_penalty=repetition_penalty,
        stop_sequences=stop_sequences,
    )

    completion_id = f"cmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model_name = model.name if model else base_model

    if request.stream:
        return await _stream_completion(
            engine=engine,
            cached_model=cached_model,
            prompt=prompt,
            config=gen_config,
            completion_id=completion_id,
            created=created,
            model_name=model_name,
            echo=request.echo,
        )
    else:
        return await _generate_completion(
            engine=engine,
            cached_model=cached_model,
            prompt=prompt,
            config=gen_config,
            completion_id=completion_id,
            created=created,
            model_name=model_name,
            echo=request.echo,
        )


async def _generate_completion(
    engine: InferenceEngine,
    cached_model,
    prompt: str,
    config: GenerationConfig,
    completion_id: str,
    created: int,
    model_name: str,
    echo: bool,
) -> CompletionResponse:
    """Generate non-streaming completion."""
    result = await engine.generate(
        cached_model=cached_model,
        prompt=prompt,
        config=config,
    )

    text = (prompt + result.text) if echo else result.text
    prompt_tokens = len(prompt.split()) * 4 // 3

    return CompletionResponse(
        id=completion_id,
        created=created,
        model=model_name,
        choices=[
            CompletionChoice(
                text=text,
                index=0,
                finish_reason="stop",
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=result.tokens_generated,
            total_tokens=prompt_tokens + result.tokens_generated,
        ),
    )


async def _stream_completion(
    engine: InferenceEngine,
    cached_model,
    prompt: str,
    config: GenerationConfig,
    completion_id: str,
    created: int,
    model_name: str,
    echo: bool,
):
    """Generate streaming completion."""

    async def event_generator():
        # Echo prompt first if requested
        if echo:
            echo_chunk = {
                "id": completion_id,
                "object": "text_completion",
                "created": created,
                "model": model_name,
                "choices": [{"text": prompt, "index": 0, "finish_reason": None}],
            }
            yield {"data": json.dumps(echo_chunk)}

        async for chunk in engine.generate_stream(
            cached_model=cached_model,
            prompt=prompt,
            config=config,
        ):
            if "error" in chunk:
                yield {"data": "[DONE]"}
                return

            if chunk.get("done"):
                final_chunk = {
                    "id": completion_id,
                    "object": "text_completion",
                    "created": created,
                    "model": model_name,
                    "choices": [{"text": "", "index": 0, "finish_reason": "stop"}],
                }
                yield {"data": json.dumps(final_chunk)}
                yield {"data": "[DONE]"}
            else:
                token = chunk.get("token", "")
                token_chunk = {
                    "id": completion_id,
                    "object": "text_completion",
                    "created": created,
                    "model": model_name,
                    "choices": [{"text": token, "index": 0, "finish_reason": None}],
                }
                yield {"data": json.dumps(token_chunk)}

    return EventSourceResponse(event_generator())
