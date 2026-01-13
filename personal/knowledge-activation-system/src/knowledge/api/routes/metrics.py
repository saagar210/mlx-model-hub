"""Prometheus Metrics Endpoint (P24: Observability)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from knowledge.logging import get_logger
from knowledge.metrics import PROMETHEUS_AVAILABLE

logger = get_logger(__name__)

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns application metrics in Prometheus exposition format.
    Use this endpoint for scraping by Prometheus or compatible systems.

    Metrics include:
    - HTTP request counts and durations
    - Search operation metrics
    - Embedding generation metrics
    - Database pool statistics
    - Content counts
    - Circuit breaker states
    - Rate limiting events
    """
    if not PROMETHEUS_AVAILABLE:
        return PlainTextResponse(
            content="# Prometheus client not installed\n",
            media_type="text/plain",
            status_code=503,
        )

    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
    except Exception as e:
        logger.error("metrics_generation_failed", error=str(e))
        return PlainTextResponse(
            content=f"# Error generating metrics: {e}\n",
            media_type="text/plain",
            status_code=500,
        )
