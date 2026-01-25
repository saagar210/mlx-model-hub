"""Health check routes."""

from typing import Any

from fastapi import APIRouter

from sia import __version__
from sia.db import get_db_manager
from sia.llm import EmbeddingService, LLMRouter

router = APIRouter()


@router.get("/health/detailed")
async def detailed_health() -> dict[str, Any]:
    """Detailed health check of all services."""
    results: dict[str, Any] = {
        "version": __version__,
        "services": {},
    }

    # Database health
    try:
        db = await get_db_manager()
        results["services"]["database"] = await db.health_check()
    except Exception as e:
        results["services"]["database"] = {"status": "unhealthy", "error": str(e)}

    # LLM health
    try:
        llm = LLMRouter()
        results["services"]["llm"] = await llm.health_check()
    except Exception as e:
        results["services"]["llm"] = {"status": "unhealthy", "error": str(e)}

    # Embeddings health
    try:
        embeddings = EmbeddingService()
        results["services"]["embeddings"] = await embeddings.health_check()
        await embeddings.close()
    except Exception as e:
        results["services"]["embeddings"] = {"status": "unhealthy", "error": str(e)}

    # Overall status
    all_healthy = all(
        s.get("status") == "healthy"
        for s in results["services"].values()
    )
    results["status"] = "healthy" if all_healthy else "degraded"

    return results


@router.get("/stats")
async def system_stats() -> dict[str, Any]:
    """Get system statistics."""
    db = await get_db_manager()

    stats = {
        "agents": await db.fetchval("SELECT COUNT(*) FROM agents WHERE retired_at IS NULL"),
        "executions": await db.fetchval("SELECT COUNT(*) FROM executions"),
        "skills": await db.fetchval("SELECT COUNT(*) FROM skills WHERE status = 'active'"),
        "episodic_memories": await db.fetchval("SELECT COUNT(*) FROM episodic_memory"),
        "semantic_memories": await db.fetchval("SELECT COUNT(*) FROM semantic_memory WHERE deleted_at IS NULL"),
    }

    return stats
