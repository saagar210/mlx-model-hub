"""Inference API endpoints with SSE streaming support."""

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel
from sse_starlette.sse import EventSourceResponse

from mlx_hub.db.models import Model, ModelVersion
from mlx_hub.db.session import SessionDep
from mlx_hub.inference import (
    GenerationConfig,
    InferenceEngine,
    get_inference_engine,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inference", tags=["inference"])


# Request/Response schemas
class InferenceRequest(SQLModel):
    """Request schema for inference."""

    model_id: UUID
    prompt: str
    version_id: UUID | None = None  # Use specific version, or latest if None
    max_tokens: int = 256
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    stop_sequences: list[str] = []
    stream: bool = False


class InferenceResponse(SQLModel):
    """Response schema for inference."""

    text: str
    model_id: UUID
    version_id: UUID | None
    tokens_generated: int
    time_to_first_token: float
    total_time: float
    tokens_per_second: float


class CacheStatsResponse(SQLModel):
    """Response schema for cache stats."""

    cached_models: int
    max_models: int
    total_memory_gb: float
    max_memory_gb: float
    models: list[str]


# Dependency injection
def get_engine() -> InferenceEngine:
    """Get inference engine dependency."""
    return get_inference_engine()


EngineDep = Annotated[InferenceEngine, Depends(get_engine)]


@router.post("", response_model=InferenceResponse)
async def generate(
    request: InferenceRequest,
    session: SessionDep,
    engine: EngineDep,
) -> InferenceResponse:
    """Generate text from a prompt.

    If stream=True is set, use the /inference/stream endpoint instead.
    """
    if request.stream:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="For streaming, use /inference/stream endpoint",
        )

    # Get model info
    model = await session.get(Model, request.model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {request.model_id} not found",
        )

    # Get adapter path if version specified
    adapter_path = None
    version_id = request.version_id
    if version_id:
        version = await session.get(ModelVersion, version_id)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model version {version_id} not found",
            )
        adapter_path = version.artifact_path

    try:
        # Load model (will use cache if available)
        cached_model = await engine.load_model(
            base_model=model.base_model,
            adapter_path=adapter_path,
        )

        # Create generation config
        gen_config = GenerationConfig(
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            repetition_penalty=request.repetition_penalty,
            stop_sequences=request.stop_sequences,
        )

        # Generate
        result = await engine.generate(
            cached_model=cached_model,
            prompt=request.prompt,
            config=gen_config,
        )

        return InferenceResponse(
            text=result.text,
            model_id=request.model_id,
            version_id=version_id,
            tokens_generated=result.tokens_generated,
            time_to_first_token=result.time_to_first_token,
            total_time=result.total_time,
            tokens_per_second=result.tokens_per_second,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.post("/stream")
async def generate_stream(
    request: InferenceRequest,
    session: SessionDep,
    engine: EngineDep,
):
    """Generate text with SSE streaming.

    Returns Server-Sent Events with tokens as they're generated.

    Event types:
    - data: Token data with index
    - done: Final summary with metrics
    - error: Error message if generation fails
    """
    # Get model info
    model = await session.get(Model, request.model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {request.model_id} not found",
        )

    # Get adapter path if version specified
    adapter_path = None
    version_id = request.version_id
    if version_id:
        version = await session.get(ModelVersion, version_id)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model version {version_id} not found",
            )
        adapter_path = version.artifact_path

    async def event_generator():
        """Generate SSE events."""
        try:
            # Load model
            cached_model = await engine.load_model(
                base_model=model.base_model,
                adapter_path=adapter_path,
            )

            # Create generation config
            gen_config = GenerationConfig(
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
                repetition_penalty=request.repetition_penalty,
                stop_sequences=request.stop_sequences,
            )

            # Stream tokens
            async for chunk in engine.generate_stream(
                cached_model=cached_model,
                prompt=request.prompt,
                config=gen_config,
            ):
                if "error" in chunk:
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": chunk["error"]}),
                    }
                    return

                if chunk.get("done"):
                    yield {
                        "event": "done",
                        "data": json.dumps({
                            "total_tokens": chunk["total_tokens"],
                            "total_time": chunk["total_time"],
                            "tokens_per_second": chunk["tokens_per_second"],
                            "model_id": str(request.model_id),
                            "version_id": str(version_id) if version_id else None,
                        }),
                    }
                else:
                    yield {
                        "event": "token",
                        "data": json.dumps({
                            "token": chunk["token"],
                            "index": chunk["index"],
                            "ttft": chunk.get("ttft"),
                        }),
                    }

        except ValueError as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
        except Exception as e:
            logger.error(f"Stream generation error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": "Internal server error"}),
            }

    return EventSourceResponse(event_generator())


@router.get("/cache", response_model=CacheStatsResponse)
async def get_cache_stats(
    engine: EngineDep,
) -> CacheStatsResponse:
    """Get model cache statistics."""
    stats = engine.get_cache_stats()
    return CacheStatsResponse(**stats)


@router.delete("/cache/{cache_key}")
async def unload_model(
    cache_key: str,
    engine: EngineDep,
) -> dict:
    """Unload a model from the cache.

    Args:
        cache_key: The cache key (typically model_id or model_id:adapter_path).

    Returns:
        Success status.
    """
    removed = engine.unload_model(cache_key)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {cache_key} not found in cache",
        )

    return {"message": f"Model {cache_key} unloaded from cache"}


@router.delete("/cache")
async def clear_cache(
    engine: EngineDep,
) -> dict:
    """Clear all models from the cache."""
    engine.cache.clear()
    return {"message": "Cache cleared"}
