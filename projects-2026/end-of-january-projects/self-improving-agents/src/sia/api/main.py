"""
SIA FastAPI Application

Main API server for the Self-Improving Agents framework.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sia import __version__
from sia.config import get_config
from sia.db.connection import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    config = get_config()
    await init_db(config)
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="SIA - Self-Improving Agents",
    description="Production-grade framework for AI agents that improve themselves",
    version=__version__,
    lifespan=lifespan,
)

# Configure CORS
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Check API and database health."""
    from sia.db import get_db_manager

    try:
        db = await get_db_manager()
        db_health = await db.health_check()
    except Exception as e:
        db_health = {"status": "unhealthy", "error": str(e)}

    return {
        "status": "healthy" if db_health.get("status") == "healthy" else "degraded",
        "version": __version__,
        "database": db_health,
    }


# Root endpoint
@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root endpoint with basic info."""
    return {
        "name": "SIA - Self-Improving Agents",
        "version": __version__,
        "docs": "/docs",
    }


# Import and include routers
from sia.api.routes import agents, executions, health, memory, skills

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(executions.router, prefix="/api/executions", tags=["Executions"])
app.include_router(skills.router, prefix="/api/skills", tags=["Skills"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory"])
