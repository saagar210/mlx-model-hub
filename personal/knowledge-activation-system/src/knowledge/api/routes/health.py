"""Health and stats routes."""

from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import APIRouter

from knowledge.api.schemas import (
    HealthResponse,
    ServiceHealth,
    StatsResponse,
)
from knowledge.db import get_db
from knowledge.embeddings import check_ollama_health

router = APIRouter(tags=["health"])

# Health check cache (reduces load from frequent polling)
HEALTH_CACHE_TTL = 30.0  # seconds


@dataclass
class CachedHealth:
    """Cached health response with timestamp."""

    response: HealthResponse
    timestamp: float


_health_cache: CachedHealth | None = None


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Check health of all services.

    Returns status of PostgreSQL and Ollama.
    Cached for 30 seconds to reduce polling load.
    """
    global _health_cache

    # Return cached response if still valid
    if _health_cache is not None:
        age = time.time() - _health_cache.timestamp
        if age < HEALTH_CACHE_TTL:
            return _health_cache.response

    # Perform actual health check
    response = await _perform_health_check()

    # Cache the result
    _health_cache = CachedHealth(response=response, timestamp=time.time())

    return response


async def _perform_health_check() -> HealthResponse:
    """Perform the actual health check (uncached)."""
    services = []
    all_healthy = True

    # Check PostgreSQL
    try:
        db = await get_db()
        db_health = await db.check_health()

        if db_health["status"] == "healthy":
            services.append(
                ServiceHealth(
                    name="PostgreSQL",
                    status="healthy",
                    details={
                        "extensions": db_health.get("extensions", []),
                        "content_count": db_health.get("content_count", 0),
                        "chunk_count": db_health.get("chunk_count", 0),
                    },
                )
            )
        else:
            services.append(
                ServiceHealth(
                    name="PostgreSQL",
                    status="unhealthy",
                    details={"error": db_health.get("error", "Unknown")},
                )
            )
            all_healthy = False
    except Exception as e:
        services.append(
            ServiceHealth(
                name="PostgreSQL",
                status="unhealthy",
                details={"error": str(e)},
            )
        )
        all_healthy = False

    # Check Ollama
    try:
        ollama_status = await check_ollama_health()

        if ollama_status.healthy:
            services.append(
                ServiceHealth(
                    name="Ollama",
                    status="healthy",
                    details={
                        "models_loaded": ollama_status.models_loaded[:5],
                    },
                )
            )
        else:
            services.append(
                ServiceHealth(
                    name="Ollama",
                    status="unhealthy",
                    details={"error": ollama_status.error or "Unknown"},
                )
            )
            all_healthy = False
    except Exception as e:
        services.append(
            ServiceHealth(
                name="Ollama",
                status="unhealthy",
                details={"error": str(e)},
            )
        )
        all_healthy = False

    return HealthResponse(
        status="healthy" if all_healthy else "unhealthy",
        services=services,
    )


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """
    Kubernetes liveness probe.

    Returns 200 if the service is running.
    Used by orchestrators to determine if the container should be restarted.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> dict[str, str | bool]:
    """
    Kubernetes readiness probe.

    Checks if the service is ready to accept traffic.
    Verifies database connectivity.
    """
    try:
        db = await get_db()
        async with db.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ready", "database": True}
    except Exception as e:
        return {"status": "not ready", "database": False, "error": str(e)}


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """
    Get database statistics.

    Returns content counts by type, total chunks, and review stats.
    """
    try:
        db = await get_db()
        stats = await db.get_stats()

        return StatsResponse(
            total_content=stats.get("total_content", 0),
            total_chunks=stats.get("total_chunks", 0),
            content_by_type=stats.get("content_by_type", {}),
            review_active=stats.get("review_active", 0),
            review_due=stats.get("review_due", 0),
        )
    except Exception:
        return StatsResponse(
            total_content=0,
            total_chunks=0,
            content_by_type={},
            review_active=0,
            review_due=0,
        )
