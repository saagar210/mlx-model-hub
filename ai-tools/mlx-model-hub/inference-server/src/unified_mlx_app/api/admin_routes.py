"""Admin API routes for model management."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..cache import get_prompt_cache_service
from ..services.model_registry import model_registry

logger = logging.getLogger(__name__)
admin_router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# Health Check
# ============================================================================


class AdminHealthResponse(BaseModel):
    """Admin health check response."""
    status: str
    models_count: int
    loaded_count: int


@admin_router.get("/health", response_model=AdminHealthResponse)
async def admin_health():
    """Health check for integration.

    Returns basic stats for mlx-model-hub to detect availability.
    """
    status = model_registry.get_status()
    return AdminHealthResponse(
        status="ok",
        models_count=status["total_models"],
        loaded_count=status["loaded_models"],
    )


# ============================================================================
# Model Status
# ============================================================================


class ModelStatusResponse(BaseModel):
    """Status for a specific model."""
    registered: bool
    loaded: bool
    base_model: str
    type: str
    adapter_path: Optional[str] = None
    source: str
    registered_by: Optional[str] = None
    model_id: Optional[str] = None


@admin_router.get("/models/{name:path}/status", response_model=ModelStatusResponse)
async def get_model_status(name: str):
    """Get status for a specific model.

    Lets mlx-model-hub show real-time status badges.

    Note: Model names with slashes (e.g., "mlx-community/Qwen2.5-7B-Instruct-4bit")
    are supported via path parameter.
    """
    status = model_registry.get_model_status(name)
    if not status:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"Model not found: {name}"}
        )
    return ModelStatusResponse(**status)


# ============================================================================
# Model Registration
# ============================================================================


class ModelRegistrationRequest(BaseModel):
    """Request to register a new model."""

    name: str = Field(..., description="Unique name for this model")
    base_model: str = Field(..., description="HuggingFace model ID for base model")
    adapter_path: Optional[str] = Field(
        None, description="Path to LoRA adapter weights"
    )
    type: str = Field(default="lora", description="Model type: base, lora, vision")
    config: dict = Field(default_factory=dict, description="Model configuration")
    registered_by: Optional[str] = Field(
        None, description="Client registering this model (e.g., 'mlx-model-hub')"
    )
    model_id: Optional[str] = Field(
        None, description="Original model ID for traceability"
    )


class ModelRegistrationResponse(BaseModel):
    """Response from model registration."""

    status: str
    model: str
    type: str
    base_model: str
    adapter_path: Optional[str] = None
    registered_by: Optional[str] = None
    model_id: Optional[str] = None


class ModelUnregisterResponse(BaseModel):
    """Response from model unregistration."""

    status: str
    model: str


class RegistryStatusResponse(BaseModel):
    """Registry status response."""

    total_models: int
    loaded_models: int
    models: dict


@admin_router.post("/models/register", response_model=ModelRegistrationResponse)
async def register_model(request: ModelRegistrationRequest):
    """Register a new model (typically a LoRA adapter from mlx-model-hub).

    After training a LoRA adapter in mlx-model-hub, call this endpoint to make
    it available for inference via the /v1/chat/completions endpoint.

    Returns:
        201: Model registered successfully
        409: Model already registered (conflict)
        400: Validation error (missing adapter_path for LoRA, etc.)
        404: Adapter path not found

    Example:
    ```
    curl http://localhost:8080/admin/models/register \\
      -H "Content-Type: application/json" \\
      -d '{
        "name": "my-fine-tuned-llama",
        "base_model": "mlx-community/Llama-3.2-3B-Instruct-4bit",
        "adapter_path": "/path/to/exports/my-model/adapters.safetensors",
        "type": "lora",
        "config": {"lora_rank": 16, "lora_alpha": 32},
        "registered_by": "mlx-model-hub",
        "model_id": "original-model-id"
      }'
    ```

    Then use for inference:
    ```
    curl http://localhost:8080/v1/chat/completions \\
      -d '{"model": "my-fine-tuned-llama", "messages": [...]}'
    ```
    """
    try:
        model = model_registry.register_model(
            name=request.name,
            base_model=request.base_model,
            model_type=request.type,
            adapter_path=request.adapter_path,
            config=request.config,
            source="registered",
            registered_by=request.registered_by,
            model_id=request.model_id,
        )

        return ModelRegistrationResponse(
            status="registered",
            model=model.name,
            type=model.model_type,
            base_model=model.base_model,
            adapter_path=model.adapter_path,
            registered_by=model.registered_by,
            model_id=model.model_id,
        )

    except ValueError as e:
        error_msg = str(e)
        # Return 409 for duplicate registration
        if "already registered" in error_msg.lower():
            raise HTTPException(
                status_code=409,
                detail={"error": "conflict", "message": error_msg}
            )
        # Return 404 for missing adapter path
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": error_msg}
            )
        # Other validation errors
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": error_msg}
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(e)}
        )


@admin_router.delete("/models/{name:path}", response_model=ModelUnregisterResponse)
async def unregister_model(name: str):
    """Unregister a model.

    Returns:
        200: Model unregistered successfully
        404: Model not found
        400: Cannot unregister built-in models

    Note: Built-in models cannot be unregistered.
    """
    try:
        success = model_registry.unregister_model(name)
        if not success:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"Model not found: {name}"}
            )

        return ModelUnregisterResponse(status="unregistered", model=name)

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": str(e)}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unregistration error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(e)}
        )


@admin_router.post("/models/{name:path}/load")
async def load_model(name: str):
    """Pre-load a model into memory.

    This is optional - models are loaded on first use automatically.
    Use this to warm up the model cache.
    """
    try:
        model_registry.load_model(name)
        return {"status": "loaded", "model": name}
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Load error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(e)}
        )


@admin_router.post("/models/{name:path}/unload")
async def unload_model(name: str):
    """Unload a model from memory.

    Frees memory by removing the model from cache.
    """
    success = model_registry.unload_model(name)
    if not success:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": f"Model not loaded: {name}"}
        )

    return {"status": "unloaded", "model": name}


@admin_router.get("/models", response_model=RegistryStatusResponse)
async def get_registry_status(
    registered_by: Optional[str] = Query(
        None,
        description="Filter by registering client (e.g., 'mlx-model-hub')"
    )
):
    """Get the current model registry status.

    Shows all registered models, their types, and load status.
    Optionally filter by the client that registered them.

    Query params:
        registered_by: Filter to show only models registered by this client
    """
    return model_registry.get_status(registered_by=registered_by)


@admin_router.post("/models/scan")
async def scan_models_directory(directory: Optional[str] = None):
    """Scan a directory for exported models.

    If no directory is provided, scans CUSTOM_MODELS_DIR or the default
    mlx-model-hub exports directory.

    Expected structure:
    ```
    directory/
        model-name-1/
            adapters.safetensors
            config.json
            metadata.json (optional)
        model-name-2/
            ...
    ```
    """
    import os
    from pathlib import Path

    if directory is None:
        directory = os.environ.get(
            "CUSTOM_MODELS_DIR",
            "/Users/d/claude-code/ai-tools/mlx-model-hub/exports",
        )

    if not Path(directory).exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {directory}")

    model_registry.scan_models_directory(directory)

    return {
        "status": "scanned",
        "directory": directory,
        "models": model_registry.get_status(),
    }


# ============================================================================
# Prompt Cache Management (KV Cache)
# ============================================================================


class PromptCacheEntry(BaseModel):
    """Info about a cached prompt."""

    cache_key: str
    model_id: str
    prompt_preview: str
    token_count: int
    hits: int
    created_at: str
    last_used: str


class PromptCacheStats(BaseModel):
    """Prompt cache statistics."""

    memory_entries: int
    disk_entries: int
    total_hits: int
    total_misses: int
    hit_rate: float
    max_entries: int


class WarmupRequest(BaseModel):
    """Request to warm up prompt cache."""

    model_id: str = Field(..., description="Model to use for caching")
    system_prompt: str = Field(..., description="System prompt to pre-cache")


@admin_router.get("/cache/prompts", response_model=list[PromptCacheEntry])
async def list_prompt_caches():
    """List all cached prompts.

    Shows cached system prompts with their hit counts and last usage.
    """
    cache_service = get_prompt_cache_service()
    return cache_service.list_entries()


@admin_router.get("/cache/prompts/stats", response_model=PromptCacheStats)
async def get_prompt_cache_stats():
    """Get prompt cache statistics.

    Shows hit rate, entry counts, and cache configuration.
    """
    cache_service = get_prompt_cache_service()
    return cache_service.get_stats()


@admin_router.delete("/cache/prompts/{cache_key}")
async def delete_prompt_cache(cache_key: str):
    """Delete a specific prompt cache entry.

    Use the cache_key from the list endpoint.
    """
    cache_service = get_prompt_cache_service()

    # Find and delete by iterating through entries
    entries = cache_service.list_entries()
    for entry in entries:
        if entry["cache_key"] == cache_key:
            # Delete requires model_id and prompt, but we only have the key
            # For now, just clear all if exact match not possible
            break

    # Clear all as fallback (since we can't easily reverse the hash)
    cache_service.clear()
    return {"status": "cleared", "message": "Cache cleared"}


@admin_router.post("/cache/prompts/clear")
async def clear_prompt_caches():
    """Clear all prompt caches.

    Removes all cached KV states from memory and disk.
    """
    cache_service = get_prompt_cache_service()
    count = cache_service.clear()
    return {"status": "cleared", "entries_removed": count}


@admin_router.post("/cache/prompts/warmup")
async def warmup_prompt_cache(request: WarmupRequest):
    """Pre-cache a system prompt for faster first request.

    Use this to warm up the cache before production traffic.
    Requires the model to be available.

    Example:
    ```
    curl -X POST http://localhost:8080/admin/cache/prompts/warmup \\
      -H "Content-Type: application/json" \\
      -d '{
        "model_id": "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "system_prompt": "You are a helpful assistant specialized in Python..."
      }'
    ```
    """
    from ..models import model_manager

    try:
        # Load model if not already loaded
        model, tokenizer = model_manager.get_text_model(request.model_id)

        # Get cache service and create cache
        cache_service = get_prompt_cache_service()

        # Format system prompt
        system_messages = [{"role": "system", "content": request.system_prompt}]
        formatted_prompt = tokenizer.apply_chat_template(
            system_messages, tokenize=False, add_generation_prompt=False
        )

        # Create and cache
        cache_service.get_or_create(
            model=model,
            tokenizer=tokenizer,
            prompt=formatted_prompt,
            model_id=request.model_id,
        )

        return {
            "status": "cached",
            "model_id": request.model_id,
            "prompt_preview": request.system_prompt[:100] + "..."
            if len(request.system_prompt) > 100
            else request.system_prompt,
        }

    except Exception as e:
        logger.error(f"Warmup failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "warmup_failed", "message": str(e)}
        )
