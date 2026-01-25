"""Health check endpoints following Kubernetes patterns.

Provides:
- /health: Quick service status
- /health/detailed: Comprehensive component health
- /ready: Kubernetes readiness probe
- /live: Kubernetes liveness probe
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from knowledge_engine.observability.health import HealthChecker, HealthStatus

router = APIRouter()

# Store health checker instance at module level
_health_checker: HealthChecker | None = None


def get_health_checker(request: Request) -> HealthChecker:
    """Get or create health checker from app state."""
    global _health_checker
    if _health_checker is None:
        # Get start time from app state if available
        start_time = getattr(request.app.state, "start_time", None)
        _health_checker = HealthChecker(start_time=start_time)
    return _health_checker


@router.get("/health")
async def health_check(request: Request) -> dict[str, Any]:
    """Quick health check for load balancers.

    Returns basic service info without checking dependencies.
    Use /health/detailed for comprehensive health status.
    """
    checker = get_health_checker(request)
    return {
        "status": "healthy",
        "service": "knowledge-engine",
        "version": "0.1.0",
        "uptime_seconds": checker._start_time,
    }


@router.get("/health/detailed")
async def detailed_health_check(request: Request) -> dict[str, Any]:
    """Comprehensive health check including all dependencies.

    Returns:
        Detailed status of all system components including:
        - PostgreSQL database
        - Qdrant vector database
        - Neo4j graph database (if enabled)
        - Redis cache (if enabled)
        - Ollama embedding service
    """
    checker = get_health_checker(request)
    health = await checker.check_all(include_optional=True)
    return health.to_dict()


@router.get("/ready")
async def readiness_check(request: Request, response: Response) -> dict[str, Any]:
    """Kubernetes readiness probe.

    Returns 200 if the service is ready to accept traffic.
    Returns 503 if critical dependencies are unavailable.

    Checked dependencies:
    - PostgreSQL (critical)
    - Qdrant (critical)
    - Ollama (non-critical, degraded is OK)
    """
    checker = get_health_checker(request)
    health = await checker.check_all(include_optional=False)

    if not health.is_healthy:
        # Return 503 but still include health details
        response.status_code = 503
        return {
            "status": "not_ready",
            "components": {c.name: c.status.value for c in health.components},
        }

    return {
        "status": "ready",
        "components": {c.name: c.status.value for c in health.components},
    }


@router.get("/live")
async def liveness_check(request: Request) -> dict[str, str]:
    """Kubernetes liveness probe.

    Returns 200 if the service is alive and should not be restarted.
    This is a lightweight check that doesn't verify external dependencies.

    The service is considered alive as long as it can respond to requests.
    Kubernetes will restart the pod if this endpoint fails repeatedly.
    """
    checker = get_health_checker(request)
    is_live = await checker.liveness_check()

    if not is_live:
        raise HTTPException(
            status_code=503,
            detail="Service is not alive",
        )

    return {"status": "alive"}


@router.get("/health/component/{component_name}")
async def component_health_check(
    request: Request,
    component_name: str,
) -> dict[str, Any]:
    """Check health of a specific component.

    Args:
        component_name: One of: postgres, qdrant, neo4j, redis, ollama

    Returns:
        Detailed health status for the specified component.
    """
    checker = get_health_checker(request)

    # Map component names to check functions
    check_functions = {
        "postgres": checker.check_postgres,
        "qdrant": checker.check_qdrant,
        "neo4j": checker.check_neo4j,
        "redis": checker.check_redis,
        "ollama": checker.check_ollama,
    }

    if component_name not in check_functions:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown component: {component_name}. Valid: {list(check_functions.keys())}",
        )

    result = await check_functions[component_name]()
    return result.to_dict()
