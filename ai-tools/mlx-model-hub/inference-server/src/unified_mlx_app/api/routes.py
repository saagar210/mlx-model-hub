"""FastAPI routes for OpenAI-compatible API."""

import logging
import os
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from ..config import settings
from ..models import model_manager
from ..services import (
    chat_service,
    stt_service,
    tts_service,
    vision_service,
    ollama_vision_service,
)
from ..services.model_registry import model_registry
from .schemas import (
    ChatCompletionChoice,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    HealthResponse,
    ModelInfo,
    ModelList,
    SpeechRequest,
    Usage,
    VisionRequest,
    VisionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", models=model_manager.get_status())


@router.get("/v1/models")
async def list_models() -> ModelList:
    """List available models.

    Includes both built-in models and registered LoRA adapters.
    """
    now = int(time.time())
    models = []

    # Add all models from the registry
    for registered_model in model_registry.list_models():
        models.append(
            ModelInfo(
                id=registered_model.name,
                created=now,
                owned_by=(
                    "mlx-model-hub"
                    if registered_model.source in ("registered", "scanned")
                    else "mlx-community"
                ),
            )
        )

    # Add speech model (not in registry)
    models.append(ModelInfo(id=settings.speech_model, created=now))

    return ModelList(data=models)


@router.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint."""
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    if request.stream:
        return StreamingResponse(
            _stream_chat_response(messages, request),
            media_type="text/event-stream",
        )

    # Non-streaming response
    try:
        result = chat_service.generate(
            messages=messages,
            model_path=request.model,
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
        )

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=result.text),
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.prompt_tokens + result.completion_tokens,
            ),
        )

    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_chat_response(
    messages: list[dict], request: ChatCompletionRequest
) -> AsyncGenerator[str, None]:
    """Stream chat response tokens."""
    response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    created = int(time.time())

    try:
        for chunk in chat_service.stream_generate(
            messages=messages,
            model_path=request.model,
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
        ):
            response_chunk = ChatCompletionChunk(
                id=response_id,
                created=created,
                model=request.model,
                choices=[
                    {
                        "index": 0,
                        "delta": {"content": chunk.text} if chunk.text else {},
                        "finish_reason": chunk.finish_reason,
                    }
                ],
            )
            yield f"data: {response_chunk.model_dump_json()}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {{'error': '{str(e)}'}}\n\n"


@router.post("/v1/audio/speech")
async def create_speech(request: SpeechRequest):
    """OpenAI-compatible text-to-speech endpoint."""
    try:
        result = tts_service.generate(
            text=request.input,
            model_path=request.model,
            voice=request.voice,
            speed=request.speed,
        )

        return Response(
            content=result.audio_data,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=speech.wav"},
        )

    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(default="mlx-community/whisper-large-v3-turbo"),
):
    """OpenAI-compatible audio transcription endpoint."""
    # Get file suffix
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".wav"

    try:
        content = await file.read()
        result = stt_service.transcribe_bytes(
            audio_data=content,
            model_path=model,
            file_suffix=suffix,
        )

        return {"text": result.text}

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/vision/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    model: str = Form(default="mlx-community/Qwen2-VL-2B-Instruct-4bit"),
    prompt: str = Form(default="Describe this image in detail."),
    max_tokens: int = Form(default=512),
    temperature: float = Form(default=0.7),
) -> VisionResponse:
    """Analyze an image with a vision model."""
    import tempfile
    from pathlib import Path

    # Get file suffix for temp file
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".png"

    try:
        content = await file.read()

        # Save to temp file for mlx_vlm
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = vision_service.analyze_image(
                image_path=temp_path,
                prompt=prompt,
                model_path=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            return VisionResponse(
                text=result.text,
                prompt_tokens=result.prompt_tokens,
                generation_tokens=result.generation_tokens,
            )
        finally:
            Path(temp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Vision error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Ollama Vision Endpoints (Alternative to MLX - no PyTorch dependency)
# ============================================================================


@router.post("/v1/vision/ollama")
async def analyze_image_ollama(
    file: UploadFile = File(...),
    model: str = Form(default="llama3.2-vision:11b"),
    prompt: str = Form(default="Describe this image in detail."),
):
    """Analyze an image using Ollama's vision model.

    This endpoint uses Ollama instead of MLX, avoiding PyTorch dependency issues.
    Requires: Ollama server running with llama3.2-vision model installed.
    """
    import tempfile
    from pathlib import Path

    suffix = os.path.splitext(file.filename)[1] if file.filename else ".png"

    try:
        content = await file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = ollama_vision_service.analyze_image(
                image_path=temp_path,
                prompt=prompt,
                model=model,
            )

            return {
                "text": result.text,
                "model": result.model,
                "eval_count": result.eval_count,
            }
        finally:
            Path(temp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Ollama vision error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/vision/caption")
async def generate_lora_caption(
    file: UploadFile = File(...),
    trigger_word: str = Form(default=""),
    style: str = Form(default="detailed"),
    model: str = Form(default="llama3.2-vision:11b"),
):
    """Generate a caption for LoRA training.

    Args:
        file: Image file to caption
        trigger_word: Trigger word to prepend (e.g., "sks person")
        style: Caption style - "detailed", "tags", or "booru"
        model: Ollama vision model

    Returns:
        Caption formatted for LoRA training
    """
    import tempfile
    from pathlib import Path

    suffix = os.path.splitext(file.filename)[1] if file.filename else ".png"

    try:
        content = await file.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            temp_path = f.name

        try:
            result = ollama_vision_service.generate_lora_caption(
                image_path=temp_path,
                trigger_word=trigger_word,
                style=style,
                model=model,
            )

            return {
                "caption": result.text,
                "model": result.model,
                "style": style,
                "trigger_word": trigger_word,
            }
        finally:
            Path(temp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Caption generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/vision/status")
async def vision_status():
    """Check vision service availability.

    Returns status of both MLX and Ollama vision backends.
    """
    ollama_available = ollama_vision_service.is_available()
    mlx_status = model_manager.get_status().get("vision", {})

    return {
        "ollama": {
            "available": ollama_available,
            "model": "llama3.2-vision:11b" if ollama_available else None,
        },
        "mlx": {
            "available": mlx_status.get("loaded", False),
            "model": mlx_status.get("model_path"),
        },
        "recommended": "ollama" if ollama_available else "mlx",
    }
