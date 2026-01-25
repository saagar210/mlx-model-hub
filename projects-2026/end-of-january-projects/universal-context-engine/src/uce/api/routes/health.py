"""
Health check and metrics endpoints.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
import asyncpg

from ...core.config import settings
from ..deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(
    db: asyncpg.Pool = Depends(get_db),
) -> dict:
    """Basic health check."""
    # Check database connection
    db_healthy = False
    try:
        async with db.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_healthy = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.app_version,
        "database": "connected" if db_healthy else "disconnected",
    }


@router.get("/health/ready")
async def readiness_check(
    db: asyncpg.Pool = Depends(get_db),
) -> dict:
    """Readiness check for Kubernetes."""
    async with db.acquire() as conn:
        await conn.fetchval("SELECT 1")

    return {"status": "ready"}


@router.get("/health/live")
async def liveness_check() -> dict:
    """Liveness check for Kubernetes."""
    return {"status": "alive"}


@router.get("/stats")
async def get_stats(
    db: asyncpg.Pool = Depends(get_db),
) -> dict:
    """Get system statistics."""
    async with db.acquire() as conn:
        # Context items stats
        context_stats = await conn.fetchrow(
            """
            SELECT
                count(*) as total,
                count(*) FILTER (WHERE t_expired IS NULL) as active,
                count(*) FILTER (WHERE source = 'kas') as kas_items,
                count(*) FILTER (WHERE source = 'git') as git_items,
                count(*) FILTER (WHERE source = 'browser') as browser_items,
                count(*) FILTER (WHERE embedding IS NOT NULL) as with_embeddings
            FROM context_items
            """
        )

        # Entity stats
        entity_stats = await conn.fetchrow(
            """
            SELECT
                count(*) as total,
                count(DISTINCT entity_type) as types,
                sum(mention_count) as total_mentions
            FROM entities
            """
        )

        # Sync stats
        sync_stats = await conn.fetch(
            """
            SELECT source, last_sync_at, items_synced, sync_status
            FROM sync_state
            ORDER BY source
            """
        )

    return {
        "context_items": {
            "total": context_stats["total"],
            "active": context_stats["active"],
            "by_source": {
                "kas": context_stats["kas_items"],
                "git": context_stats["git_items"],
                "browser": context_stats["browser_items"],
            },
            "with_embeddings": context_stats["with_embeddings"],
        },
        "entities": {
            "total": entity_stats["total"],
            "types": entity_stats["types"],
            "total_mentions": entity_stats["total_mentions"],
        },
        "sync": [
            {
                "source": s["source"],
                "last_sync": s["last_sync_at"].isoformat() if s["last_sync_at"] else None,
                "items_synced": s["items_synced"],
                "status": s["sync_status"],
            }
            for s in sync_stats
        ],
    }
