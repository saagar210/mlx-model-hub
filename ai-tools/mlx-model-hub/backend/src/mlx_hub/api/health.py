"""Health and metrics API endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, Response
from sqlalchemy import text
from sqlmodel import SQLModel

from mlx_hub.config import get_settings
from mlx_hub.db.session import SessionDep
from mlx_hub.observability import get_metrics, update_system_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(SQLModel):
    """Response schema for health check."""

    status: str
    timestamp: str
    version: str
    checks: dict


class ReadinessResponse(SQLModel):
    """Response schema for readiness check."""

    ready: bool
    checks: dict


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check - is the service running?"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="0.1.0",
        checks={},
    )


@router.get("/health/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe - is the process alive?"""
    return {"status": "alive"}


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(session: SessionDep) -> ReadinessResponse:
    """Kubernetes readiness probe - is the service ready to accept traffic?

    Checks:
    - Database connectivity
    - Storage accessibility
    """
    checks = {}
    all_ready = True

    # Check database
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        checks["database"] = {"status": "error", "message": str(e)}
        all_ready = False

    # Check storage
    settings = get_settings()
    try:
        if settings.storage_models_path.exists() and settings.storage_datasets_path.exists():
            checks["storage"] = {"status": "ok"}
        else:
            checks["storage"] = {"status": "error", "message": "Storage directories not found"}
            all_ready = False
    except Exception as e:
        logger.error(f"Storage check failed: {e}")
        checks["storage"] = {"status": "error", "message": str(e)}
        all_ready = False

    # Check MLflow (optional)
    try:
        import mlflow

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        client = mlflow.tracking.MlflowClient()
        client.search_experiments(max_results=1)
        checks["mlflow"] = {"status": "ok"}
    except Exception as e:
        # MLflow is optional, don't fail readiness
        checks["mlflow"] = {"status": "unavailable", "message": str(e)}

    return ReadinessResponse(
        ready=all_ready,
        checks=checks,
    )


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.
    """
    # Update system metrics before generating output
    try:
        update_system_metrics()
    except Exception as e:
        logger.warning(f"Failed to update system metrics: {e}")

    return Response(
        content=get_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/health/detailed")
async def detailed_health(session: SessionDep) -> dict:
    """Detailed health information for debugging."""
    settings = get_settings()

    health_info = {
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "environment": {
            "debug": settings.debug,
            "log_level": settings.log_level,
            "host": settings.host,
            "port": settings.port,
        },
        "storage": {
            "base_path": str(settings.storage_base_path),
            "models_path": str(settings.storage_models_path),
            "datasets_path": str(settings.storage_datasets_path),
            "models_exists": settings.storage_models_path.exists(),
            "datasets_exists": settings.storage_datasets_path.exists(),
        },
        "database": {},
        "mlx": {},
    }

    # Database info
    try:
        await session.execute(text("SELECT 1"))
        health_info["database"]["status"] = "connected"
    except Exception as e:
        health_info["database"]["status"] = "error"
        health_info["database"]["error"] = str(e)

    # MLX info
    try:
        import mlx.core as mx

        health_info["mlx"]["status"] = "available"
        health_info["mlx"]["default_device"] = str(mx.default_device())
    except ImportError:
        health_info["mlx"]["status"] = "not_available"
    except Exception as e:
        health_info["mlx"]["status"] = "error"
        health_info["mlx"]["error"] = str(e)

    # Memory info
    try:
        import psutil

        mem = psutil.virtual_memory()
        health_info["memory"] = {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_percent": mem.percent,
        }
    except ImportError:
        health_info["memory"] = {"status": "psutil not available"}

    return health_info
