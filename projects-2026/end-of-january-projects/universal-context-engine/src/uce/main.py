"""
Universal Context Engine - FastAPI Application.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.database import get_db_pool, close_db_pool
from .core.logging import setup_logging, get_logger
from .api.routes import search_router, context_router, entities_router, health_router
from .api.deps import cleanup_deps

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan management."""
    # Startup
    setup_logging()
    logger.info("Starting Universal Context Engine", version=settings.app_version)

    # Initialize database pool
    await get_db_pool()
    logger.info("Database connection pool initialized")

    yield

    # Shutdown
    logger.info("Shutting down Universal Context Engine")
    await cleanup_deps()
    await close_db_pool()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Unified context aggregation with temporal knowledge graph capabilities",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(search_router, prefix="/api/v1")
app.include_router(context_router, prefix="/api/v1")
app.include_router(entities_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


def main() -> None:
    """Run the application."""
    import uvicorn

    uvicorn.run(
        "uce.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
