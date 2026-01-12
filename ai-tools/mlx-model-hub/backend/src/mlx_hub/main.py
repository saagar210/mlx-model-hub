"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from mlx_hub.api import datasets, discover, health, inference, models, openai_compat, training
from mlx_hub.config import get_settings
from mlx_hub.observability import (
    PrometheusMiddleware,
    RequestIdMiddleware,
    configure_logging_with_trace_context,
    setup_tracing,
)
from mlx_hub.security import APIKeyAuthMiddleware, limiter
from mlx_hub.services.huggingface import get_huggingface_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Debug mode: {settings.debug}")

    # Log production warnings
    warnings = settings.validate_production_settings()
    for warning in warnings:
        logger.warning(f"Production warning: {warning}")

    # Setup tracing (optional - will work without OTLP endpoint)
    try:
        setup_tracing(app)
        configure_logging_with_trace_context()
        logger.info("OpenTelemetry tracing initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize tracing: {e}")

    yield

    # Cleanup resources
    logger.info("Shutting down...")

    # Close HuggingFace HTTP client
    hf_service = get_huggingface_service()
    await hf_service.close()
    logger.info("HuggingFace client closed")


settings = get_settings()

app = FastAPI(
    title="MLX Model Hub",
    description="Local-first MLX Model Hub for Apple Silicon",
    version="0.1.0",
    lifespan=lifespan,
    # Disable docs in production if needed
    docs_url="/docs" if settings.debug else "/docs",
    redoc_url="/redoc" if settings.debug else "/redoc",
)

# Setup rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add middleware (order matters - first added is outermost)
# 1. Prometheus metrics (outermost - tracks all requests)
app.add_middleware(PrometheusMiddleware)

# 2. Request ID tracking
app.add_middleware(RequestIdMiddleware)

# 3. API key authentication
app.add_middleware(APIKeyAuthMiddleware)

# 4. CORS (must be after auth to allow preflight requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Include routers
app.include_router(health.router)  # /health, /metrics at root level
app.include_router(openai_compat.router)  # /v1/... OpenAI-compatible endpoints
app.include_router(discover.router)  # /api/discover/... Model discovery
app.include_router(models.router, prefix="/api")
app.include_router(datasets.router, prefix="/api")
app.include_router(training.router, prefix="/api")
app.include_router(inference.router, prefix="/api")


def main() -> None:
    """Run the application."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "mlx_hub.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
