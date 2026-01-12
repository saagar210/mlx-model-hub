"""FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mlx_hub.api import datasets, discover, health, inference, models, openai_compat, training
from mlx_hub.config import get_settings
from mlx_hub.observability import (
    PrometheusMiddleware,
    RequestIdMiddleware,
    configure_logging_with_trace_context,
    setup_tracing,
)

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

    # Setup tracing (optional - will work without OTLP endpoint)
    try:
        setup_tracing(app)
        configure_logging_with_trace_context()
        logger.info("OpenTelemetry tracing initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize tracing: {e}")

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="MLX Model Hub",
    description="Local-first MLX Model Hub for Apple Silicon",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware (order matters - first added is outermost)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(RequestIdMiddleware)

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
