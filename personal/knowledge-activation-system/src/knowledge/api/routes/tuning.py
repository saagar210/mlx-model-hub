"""Search Weight Tuning API.

Provides endpoints for dynamically adjusting search parameters
without requiring application restart.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from knowledge.config import get_settings
from knowledge.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/tuning", tags=["tuning"])


# =============================================================================
# Schemas
# =============================================================================


class SearchWeights(BaseModel):
    """Current search weight configuration."""

    bm25_weight: float = Field(ge=0.0, le=1.0, description="Weight for BM25 scoring (0-1)")
    vector_weight: float = Field(ge=0.0, le=1.0, description="Weight for vector scoring (0-1)")
    rrf_k: int = Field(ge=1, le=100, description="RRF fusion constant (typically 60)")
    query_expansion_enabled: bool = Field(description="Whether query expansion is enabled")


class SearchWeightsUpdate(BaseModel):
    """Request to update search weights."""

    bm25_weight: float | None = Field(
        default=None, ge=0.0, le=1.0, description="New BM25 weight"
    )
    vector_weight: float | None = Field(
        default=None, ge=0.0, le=1.0, description="New vector weight"
    )
    rrf_k: int | None = Field(default=None, ge=1, le=100, description="New RRF constant")
    query_expansion_enabled: bool | None = Field(
        default=None, description="Enable/disable query expansion"
    )


class TuningResponse(BaseModel):
    """Response from tuning operations."""

    success: bool
    message: str
    current: SearchWeights


class CacheTTL(BaseModel):
    """Cache TTL configuration."""

    search_ttl: int = Field(ge=0, le=86400, description="Search results TTL (seconds)")
    embedding_ttl: int = Field(ge=0, le=604800, description="Embedding cache TTL (seconds)")
    rerank_ttl: int = Field(ge=0, le=86400, description="Rerank results TTL (seconds)")


class CacheTTLUpdate(BaseModel):
    """Request to update cache TTLs."""

    search_ttl: int | None = Field(default=None, ge=0, le=86400)
    embedding_ttl: int | None = Field(default=None, ge=0, le=604800)
    rerank_ttl: int | None = Field(default=None, ge=0, le=86400)


# =============================================================================
# Runtime Configuration Store
# =============================================================================

# Runtime-adjustable settings (not persisted to file)
_runtime_config: dict = {}


def _get_runtime_value(key: str, default: Any) -> Any:
    """Get runtime config value, falling back to settings."""
    return _runtime_config.get(key, default)


def _set_runtime_value(key: str, value: Any) -> None:
    """Set runtime config value."""
    _runtime_config[key] = value


# =============================================================================
# Search Weights Endpoints
# =============================================================================


@router.get("/weights", response_model=SearchWeights)
async def get_search_weights() -> SearchWeights:
    """
    Get current search weight configuration.

    Returns the current weights used for hybrid search scoring.
    These can be adjusted in real-time without restart.
    """
    settings = get_settings()
    return SearchWeights(
        bm25_weight=_get_runtime_value("search_bm25_weight", settings.search_bm25_weight),
        vector_weight=_get_runtime_value("search_vector_weight", settings.search_vector_weight),
        rrf_k=_get_runtime_value("rrf_k", settings.rrf_k),
        query_expansion_enabled=_get_runtime_value(
            "search_enable_query_expansion", settings.search_enable_query_expansion
        ),
    )


@router.patch("/weights", response_model=TuningResponse)
async def update_search_weights(update: SearchWeightsUpdate) -> TuningResponse:
    """
    Update search weight configuration.

    Changes take effect immediately for new searches.
    Changes are NOT persisted and will reset on application restart.

    For permanent changes, update environment variables or config files.
    """
    changes = []

    if update.bm25_weight is not None:
        _set_runtime_value("search_bm25_weight", update.bm25_weight)
        changes.append(f"bm25_weight={update.bm25_weight}")

    if update.vector_weight is not None:
        _set_runtime_value("search_vector_weight", update.vector_weight)
        changes.append(f"vector_weight={update.vector_weight}")

    if update.rrf_k is not None:
        _set_runtime_value("rrf_k", update.rrf_k)
        changes.append(f"rrf_k={update.rrf_k}")

    if update.query_expansion_enabled is not None:
        _set_runtime_value("search_enable_query_expansion", update.query_expansion_enabled)
        changes.append(f"query_expansion={update.query_expansion_enabled}")

    if not changes:
        raise HTTPException(status_code=400, detail="No changes specified")

    logger.info("search_weights_updated", changes=changes)

    return TuningResponse(
        success=True,
        message=f"Updated: {', '.join(changes)}",
        current=await get_search_weights(),
    )


@router.post("/weights/reset", response_model=TuningResponse)
async def reset_search_weights() -> TuningResponse:
    """
    Reset search weights to default configuration.

    Clears all runtime overrides and uses values from settings/env.
    """
    # Clear runtime overrides for search weights
    keys_to_clear = [
        "search_bm25_weight",
        "search_vector_weight",
        "rrf_k",
        "search_enable_query_expansion",
    ]
    for key in keys_to_clear:
        _runtime_config.pop(key, None)

    logger.info("search_weights_reset")

    return TuningResponse(
        success=True,
        message="Search weights reset to defaults",
        current=await get_search_weights(),
    )


# =============================================================================
# Cache TTL Endpoints
# =============================================================================


@router.get("/cache", response_model=CacheTTL)
async def get_cache_ttl() -> CacheTTL:
    """
    Get current cache TTL configuration.
    """
    settings = get_settings()
    return CacheTTL(
        search_ttl=_get_runtime_value("cache_ttl_search", settings.cache_ttl_search),
        embedding_ttl=_get_runtime_value("cache_ttl_embedding", settings.cache_ttl_embedding),
        rerank_ttl=_get_runtime_value("cache_ttl_rerank", settings.cache_ttl_rerank),
    )


@router.patch("/cache", response_model=CacheTTL)
async def update_cache_ttl(update: CacheTTLUpdate) -> CacheTTL:
    """
    Update cache TTL configuration.

    Changes affect new cache entries only.
    Existing cached entries retain their original TTL.
    """
    changes = []

    if update.search_ttl is not None:
        _set_runtime_value("cache_ttl_search", update.search_ttl)
        changes.append(f"search_ttl={update.search_ttl}s")

    if update.embedding_ttl is not None:
        _set_runtime_value("cache_ttl_embedding", update.embedding_ttl)
        changes.append(f"embedding_ttl={update.embedding_ttl}s")

    if update.rerank_ttl is not None:
        _set_runtime_value("cache_ttl_rerank", update.rerank_ttl)
        changes.append(f"rerank_ttl={update.rerank_ttl}s")

    if not changes:
        raise HTTPException(status_code=400, detail="No changes specified")

    logger.info("cache_ttl_updated", changes=changes)

    return await get_cache_ttl()


# =============================================================================
# Full Configuration Endpoint
# =============================================================================


class FullTuningConfig(BaseModel):
    """Complete tuning configuration."""

    search: SearchWeights
    cache: CacheTTL


@router.get("/all", response_model=FullTuningConfig)
async def get_all_tuning() -> FullTuningConfig:
    """
    Get all tunable configuration.

    Returns both search weights and cache TTL settings.
    """
    return FullTuningConfig(
        search=await get_search_weights(),
        cache=await get_cache_ttl(),
    )


# =============================================================================
# Helper Functions for Search Module
# =============================================================================


def get_effective_bm25_weight() -> float:
    """Get the effective BM25 weight (runtime or default)."""
    settings = get_settings()
    return _get_runtime_value("search_bm25_weight", settings.search_bm25_weight)


def get_effective_vector_weight() -> float:
    """Get the effective vector weight (runtime or default)."""
    settings = get_settings()
    return _get_runtime_value("search_vector_weight", settings.search_vector_weight)


def get_effective_rrf_k() -> int:
    """Get the effective RRF constant (runtime or default)."""
    settings = get_settings()
    return _get_runtime_value("rrf_k", settings.rrf_k)


def is_query_expansion_enabled() -> bool:
    """Check if query expansion is enabled (runtime or default)."""
    settings = get_settings()
    return _get_runtime_value("search_enable_query_expansion", settings.search_enable_query_expansion)
