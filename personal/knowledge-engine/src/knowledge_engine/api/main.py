"""FastAPI application entry point."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

from knowledge_engine.api.middleware import add_production_middleware
from knowledge_engine.api.routes import health, ingest, memory, query, review, search
from knowledge_engine.config import get_settings
from knowledge_engine.core.engine import KnowledgeEngine
from knowledge_engine.logging_config import configure_logging, get_logger
from knowledge_engine.observability.metrics import get_metrics
from knowledge_engine.observability.tracing import get_tracer

# Configure logging on import
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup/shutdown."""
    # Record start time for uptime tracking
    start_time = time.time()
    app.state.start_time = start_time

    settings = get_settings()
    logger.info("Starting Knowledge Engine in %s mode", settings.environment.value)

    # Validate production security settings
    security_warnings = settings.validate_production_security()
    for warning in security_warnings:
        logger.warning(warning)

    # Initialize observability
    tracer = get_tracer()
    tracer.initialize()
    metrics = get_metrics()
    metrics.uptime_seconds.set(0)
    logger.info("Observability initialized")

    # Initialize engine
    engine = KnowledgeEngine(settings)
    await engine.initialize()
    app.state.engine = engine

    yield

    # Cleanup
    await engine.close()
    tracer.shutdown()
    logger.info("Knowledge Engine shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Knowledge Engine",
        description="Enterprise-grade knowledge infrastructure for AI applications",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # CORS
    if settings.is_development:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["https://your-domain.com"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["*"],
        )

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(ingest.router, prefix="/v1", tags=["Ingestion"])
    app.include_router(search.router, prefix="/v1", tags=["Search"])
    app.include_router(query.router, prefix="/v1", tags=["Query"])
    app.include_router(memory.router, prefix="/v1", tags=["Memory"])
    app.include_router(review.router, prefix="/v1", tags=["Review"])

    # Prometheus metrics endpoint
    @app.get("/metrics")
    async def metrics() -> JSONResponse:
        return JSONResponse(
            content=generate_latest(REGISTRY).decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        if settings.is_development:
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc), "type": type(exc).__name__},
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # Add production middleware (request timing, metrics)
    add_production_middleware(app, rate_limit=not settings.is_development)

    return app


app = create_app()
