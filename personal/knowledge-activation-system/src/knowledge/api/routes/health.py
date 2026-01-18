"""Health and stats routes (P23: Enhanced Health Checks)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum

import psutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from knowledge.config import get_settings
from knowledge.db import get_db
from knowledge.embeddings import check_ollama_health as _check_ollama
from knowledge.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


# =============================================================================
# Health Status Types
# =============================================================================


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Partial functionality
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status for a single component."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    details: dict = {}


class SystemMetrics(BaseModel):
    """System resource metrics."""

    cpu_percent: float
    memory_percent: float
    memory_available_mb: int
    disk_percent: float
    disk_available_gb: float


class HealthResponse(BaseModel):
    """Full health check response."""

    status: HealthStatus
    version: str
    uptime_seconds: float
    components: list[ComponentHealth]
    system: SystemMetrics


class StatsResponse(BaseModel):
    """Statistics response."""

    total_content: int
    total_chunks: int
    content_by_type: dict[str, int]
    review_active: int
    review_due: int


# =============================================================================
# Service Start Time
# =============================================================================

_service_start_time = time.time()


# =============================================================================
# Component Health Checks
# =============================================================================


async def check_database_health() -> ComponentHealth:
    """Check database connectivity and pool status."""
    start = time.time()
    try:
        db = await get_db()
        health = await db.check_health()
        latency = (time.time() - start) * 1000

        pool_stats = db.get_pool_stats()
        pool_dict = pool_stats.to_dict() if pool_stats else {}

        if health["status"] == "healthy":
            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={
                    "pool_size": pool_dict.get("size", 0),
                    "pool_available": pool_dict.get("free_size", 0),
                    "pool_min": pool_dict.get("min_size", 0),
                    "pool_max": pool_dict.get("max_size", 0),
                    "content_count": health.get("content_count", 0),
                    "chunk_count": health.get("chunk_count", 0),
                    "extensions": health.get("extensions", []),
                },
            )
        else:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                details={"error": health.get("error", "Unknown error")},
            )
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            details={"error": str(e)},
        )


async def check_ollama_component_health() -> ComponentHealth:
    """Check Ollama connectivity and model availability."""
    settings = get_settings()
    start = time.time()
    try:
        ollama_status = await _check_ollama()
        latency = (time.time() - start) * 1000

        if ollama_status.healthy:
            return ComponentHealth(
                name="ollama",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={
                    "url": settings.ollama_url,
                    "models_available": len(ollama_status.models_loaded),
                    "models_loaded": ollama_status.models_loaded[:5],  # First 5
                },
            )
        else:
            # Ollama being down is DEGRADED, not UNHEALTHY
            # System can still function with fallback search
            return ComponentHealth(
                name="ollama",
                status=HealthStatus.DEGRADED,
                latency_ms=round(latency, 2) if latency else None,
                details={
                    "url": settings.ollama_url,
                    "error": ollama_status.error or "Unknown error",
                },
            )
    except Exception as e:
        logger.warning("ollama_health_check_failed", error=str(e))
        return ComponentHealth(
            name="ollama",
            status=HealthStatus.DEGRADED,
            details={"error": str(e)},
        )


def get_system_metrics() -> SystemMetrics:
    """Get current system resource metrics."""
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=memory.percent,
            memory_available_mb=int(memory.available / (1024 * 1024)),
            disk_percent=disk.percent,
            disk_available_gb=round(disk.free / (1024 * 1024 * 1024), 2),
        )
    except Exception as e:
        logger.warning("system_metrics_failed", error=str(e))
        return SystemMetrics(
            cpu_percent=0.0,
            memory_percent=0.0,
            memory_available_mb=0,
            disk_percent=0.0,
            disk_available_gb=0.0,
        )


def determine_overall_status(components: list[ComponentHealth]) -> HealthStatus:
    """Determine overall health status from component statuses."""
    statuses = [c.status for c in components]

    # If any critical component (database) is unhealthy, overall is unhealthy
    db_health = next((c for c in components if c.name == "database"), None)
    if db_health and db_health.status == HealthStatus.UNHEALTHY:
        return HealthStatus.UNHEALTHY

    # If all healthy, return healthy
    if all(s == HealthStatus.HEALTHY for s in statuses):
        return HealthStatus.HEALTHY

    # If any unhealthy (other than optional services), return unhealthy
    if any(s == HealthStatus.UNHEALTHY for s in statuses):
        return HealthStatus.UNHEALTHY

    # Otherwise degraded
    return HealthStatus.DEGRADED


# =============================================================================
# Health Check Cache
# =============================================================================

HEALTH_CACHE_TTL = 30.0  # seconds


@dataclass
class CachedHealth:
    """Cached health response with timestamp."""

    response: HealthResponse
    timestamp: float


_health_cache: CachedHealth | None = None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Comprehensive health check of all components.

    Returns status of:
    - Database (PostgreSQL + pgvector)
    - Ollama (embedding service)
    - System resources (CPU, memory, disk)

    Status levels:
    - healthy: All components functioning normally
    - degraded: Some non-critical components unavailable (e.g., Ollama)
    - unhealthy: Critical components (database) unavailable

    Cached for 30 seconds to reduce load from frequent polling.
    """
    global _health_cache

    # Return cached response if still valid
    if _health_cache is not None:
        age = time.time() - _health_cache.timestamp
        if age < HEALTH_CACHE_TTL:
            return _health_cache.response

    # Perform checks in parallel
    components = list(
        await asyncio.gather(
            check_database_health(),
            check_ollama_component_health(),
        )
    )

    system = get_system_metrics()
    uptime = time.time() - _service_start_time
    overall = determine_overall_status(components)

    settings = get_settings()
    response = HealthResponse(
        status=overall,
        version=settings.api_version,
        uptime_seconds=round(uptime, 2),
        components=components,
        system=system,
    )

    # Cache the result
    _health_cache = CachedHealth(response=response, timestamp=time.time())

    logger.debug(
        "health_check_completed",
        status=overall.value,
        components={c.name: c.status.value for c in components},
    )

    return response


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """
    Kubernetes liveness probe.

    Returns 200 if the service process is running.
    Used by orchestrators to determine if the container should be restarted.
    This is a lightweight check that doesn't test dependencies.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> dict[str, str | bool]:
    """
    Kubernetes readiness probe.

    Checks if the service is ready to accept traffic.
    Verifies database connectivity before returning ready.
    Used by load balancers to route traffic.
    """
    try:
        db = await get_db()
        if db._pool is None:
            raise HTTPException(status_code=503, detail="Database pool not initialized")

        async with db.acquire() as conn:
            await conn.fetchval("SELECT 1")

        return {"status": "ready", "database": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("readiness_check_failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Not ready: {str(e)}",
        ) from e


@router.get("/api/v1/health")
async def api_v1_health() -> dict[str, str]:
    """
    Simple health endpoint for API version 1.

    Returns basic status without detailed component checks.
    """
    return {"status": "ok", "version": "v1"}


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
    except Exception as e:
        logger.error("stats_fetch_failed", error=str(e))
        return StatsResponse(
            total_content=0,
            total_chunks=0,
            content_by_type={},
            review_active=0,
            review_due=0,
        )
