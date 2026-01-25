"""FastAPI dashboard for Universal Context Engine observability."""

from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..adapters import kas_adapter, localcrew_adapter
from ..config import settings
from ..context_store import context_store
from ..embedding import embedding_client
from ..feedback import feedback_tracker, get_metrics
from ..models import ContextType

app = FastAPI(
    title="Universal Context Engine Dashboard",
    description="Observability API for the Universal Context Engine",
    version="0.1.0",
)

# Add CORS for frontend access (restricted to localhost by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,  # Disabled unless explicitly needed
    allow_methods=["GET"],  # Dashboard is read-only
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint for all services."""
    services = {}

    # Check Ollama
    try:
        ollama_ok = await embedding_client.health_check()
        services["ollama"] = {
            "status": "healthy" if ollama_ok else "unhealthy",
            "url": settings.ollama_base_url,
        }
    except Exception as e:
        services["ollama"] = {"status": "unhealthy", "error": str(e)}

    # Check KAS
    kas_health = await kas_adapter.health()
    services["kas"] = {
        "status": kas_health["status"],
        "url": settings.kas_base_url,
    }
    if kas_health["status"] != "healthy":
        services["kas"]["error"] = kas_health.get("error")

    # Check LocalCrew
    localcrew_health = await localcrew_adapter.health()
    services["localcrew"] = {
        "status": localcrew_health["status"],
        "url": settings.localcrew_base_url,
    }
    if localcrew_health["status"] != "healthy":
        services["localcrew"]["error"] = localcrew_health.get("error")

    # Check Redis
    try:
        redis_client = aioredis.from_url(settings.redis_url)
        await redis_client.ping()
        services["redis"] = {"status": "healthy", "url": settings.redis_url}
        await redis_client.aclose()
    except Exception as e:
        services["redis"] = {"status": "unhealthy", "url": settings.redis_url, "error": str(e)}

    # Check ChromaDB (context store)
    try:
        stats = await context_store.get_stats()
        services["chromadb"] = {
            "status": "healthy",
            "path": str(settings.chromadb_path),
            "items": sum(stats.values()),
        }
    except Exception as e:
        services["chromadb"] = {"status": "unhealthy", "error": str(e)}

    # Overall status
    all_healthy = all(s["status"] == "healthy" for s in services.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "services": services,
    }


@app.get("/stats")
async def stats() -> dict[str, Any]:
    """Get usage statistics."""
    context_stats = await context_store.get_stats()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "context": {
            "by_type": context_stats,
            "total": sum(context_stats.values()),
        },
        "storage_path": str(settings.chromadb_path),
    }


@app.get("/quality")
async def quality() -> dict[str, Any]:
    """Get quality metrics from feedback."""
    metrics = get_metrics()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_interactions": metrics.total_interactions,
        "feedback": {
            "helpful": metrics.helpful_count,
            "not_helpful": metrics.not_helpful_count,
            "rate_percent": round(metrics.feedback_rate * 100, 1),
            "helpful_rate_percent": round(metrics.helpful_rate * 100, 1),
        },
        "performance": {
            "avg_latency_ms": round(metrics.avg_latency_ms, 1),
            "error_rate_percent": round(metrics.error_rate * 100, 1),
        },
        "by_tool": metrics.by_tool or {},
    }


@app.get("/sessions")
async def sessions(limit: int = 10) -> dict[str, Any]:
    """Get recent sessions."""
    recent_sessions = await context_store.get_recent(
        hours=168,  # 1 week
        context_type=ContextType.SESSION,
        limit=limit,
    )

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "sessions": [
            {
                "id": s.id,
                "project": s.project,
                "branch": s.branch,
                "content": s.content[:300],
                "timestamp": s.timestamp.isoformat(),
            }
            for s in recent_sessions
        ],
        "count": len(recent_sessions),
    }


@app.get("/decisions")
async def decisions(project: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Get recent decisions."""
    recent_decisions = await context_store.get_recent(
        project=project,
        hours=720,  # 30 days
        context_type=ContextType.DECISION,
        limit=limit,
    )

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "decisions": [
            {
                "id": d.id,
                "project": d.project,
                "content": d.content,
                "category": d.metadata.get("category"),
                "timestamp": d.timestamp.isoformat(),
            }
            for d in recent_decisions
        ],
        "count": len(recent_decisions),
    }


@app.get("/blockers")
async def blockers(include_resolved: bool = False) -> dict[str, Any]:
    """Get active blockers."""
    recent_blockers = await context_store.get_recent(
        hours=168,  # 1 week
        context_type=ContextType.BLOCKER,
        limit=50,
    )

    filtered = []
    for b in recent_blockers:
        is_resolved = b.metadata.get("resolved", False)
        if include_resolved or not is_resolved:
            filtered.append({
                "id": b.id,
                "project": b.project,
                "content": b.content,
                "severity": b.metadata.get("severity", "medium"),
                "resolved": is_resolved,
                "timestamp": b.timestamp.isoformat(),
            })

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "blockers": filtered,
        "count": len(filtered),
        "active_count": sum(1 for b in filtered if not b["resolved"]),
    }


def main():
    """Run the dashboard server.

    WARNING: The dashboard binds to 127.0.0.1 by default for security.
    To expose externally, set UCE_DASHBOARD_HOST=0.0.0.0 - this is NOT
    recommended without additional authentication.
    """
    import uvicorn
    uvicorn.run(app, host=settings.dashboard_host, port=settings.dashboard_port)


if __name__ == "__main__":
    main()
