"""FastAPI application setup."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from knowledge.ai import close_ai_provider
from knowledge.api.middleware import APIVersionMiddleware, MetricsMiddleware, SecurityMiddleware
from knowledge.api.routes import auth, batch, content, export, health, integration, metrics, namespaces, review, search, tuning, webhooks
from knowledge.config import get_settings
from knowledge.db import close_db
from knowledge.embeddings import close_embedding_service
from knowledge.rerank import close_reranker
from knowledge.reranker import close_local_reranker, preload_reranker
from knowledge.review import start_daily_scheduler, stop_daily_scheduler
from knowledge.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Configure tracing (if enabled)
    configure_tracing()

    # Startup - preload models in background to avoid cold-start delays
    await preload_reranker()  # Non-blocking, loads in background thread

    # Start daily review scheduler (if enabled)
    await start_daily_scheduler()

    yield

    # Shutdown - cleanup all resources
    await stop_daily_scheduler()
    await close_db()
    await close_embedding_service()
    await close_ai_provider()
    await close_reranker()
    await close_local_reranker()


app = FastAPI(
    title="Knowledge Activation System API",
    description="AI-powered personal knowledge management with hybrid search",
    version="0.1.0",
    lifespan=lifespan,
)

# API version middleware (adds X-API-Version header)
app.add_middleware(APIVersionMiddleware, version="v1")

# Metrics middleware (must be early to capture all requests)
app.add_middleware(MetricsMiddleware)

# Security middleware (rate limiting, API key validation)
app.add_middleware(SecurityMiddleware)

# CORS middleware for frontend and integrations
settings = get_settings()
allowed_origins = [
    "http://localhost:3000",  # Next.js dev server (KAS frontend)
    "http://127.0.0.1:3000",
    "http://localhost:3001",  # LocalCrew dashboard
    "http://127.0.0.1:3001",
    "http://localhost:3002",  # MLX Model Hub frontend (alt port)
    "http://127.0.0.1:3002",
    "http://localhost:3005",  # MLX Model Hub frontend
    "http://127.0.0.1:3005",
    "http://localhost:7860",  # Unified MLX Gradio UI
    "http://127.0.0.1:7860",
    "http://localhost:8001",  # LocalCrew API
    "http://127.0.0.1:8001",
    "http://localhost:8080",  # Unified MLX API
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Explicit methods
    allow_headers=["*", settings.api_key_header],  # Include API key header
)

# Include routers
app.include_router(auth.router)  # Authentication (/auth)
app.include_router(search.router)
app.include_router(content.router)
app.include_router(health.router)
app.include_router(metrics.router)  # Prometheus metrics (/metrics)
app.include_router(review.router)
app.include_router(integration.router)  # External integration API (/api/v1/*)
app.include_router(namespaces.router)  # Namespace management (/api/v1/namespaces)
app.include_router(batch.router)  # Batch operations (/api/v1/batch)
app.include_router(export.router)  # Export/Import (/api/v1/export)
app.include_router(webhooks.router)  # Webhooks (/api/v1/webhooks)
app.include_router(tuning.router)  # Search tuning (/api/v1/tuning)


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "name": "Knowledge Activation System API",
        "version": "0.1.0",
        "docs": "/docs",
    }
