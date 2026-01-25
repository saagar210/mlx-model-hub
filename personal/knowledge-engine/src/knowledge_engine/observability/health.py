"""Comprehensive health checking for all system components.

Provides detailed health status for:
- Liveness: Is the service alive?
- Readiness: Is the service ready to accept traffic?
- Component health: Individual component status

Health checks follow the Kubernetes health probe patterns.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

from knowledge_engine.config import get_settings
from knowledge_engine.logging_config import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Working but with issues
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status for a single component."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "details": self.details,
            "last_checked": self.last_checked.isoformat(),
        }


@dataclass
class SystemHealth:
    """Overall system health status."""

    status: HealthStatus
    components: list[ComponentHealth]
    uptime_seconds: float
    version: str = "0.1.0"
    environment: str = "development"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        """Check if system is healthy (ready for traffic)."""
        return self.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)

    @property
    def is_live(self) -> bool:
        """Check if system is alive (should not be restarted)."""
        # System is live as long as it's not completely unhealthy
        critical_components = ["postgres", "qdrant"]
        for component in self.components:
            if component.name in critical_components:
                if component.status == HealthStatus.UNHEALTHY:
                    return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "is_healthy": self.is_healthy,
            "is_live": self.is_live,
            "uptime_seconds": self.uptime_seconds,
            "version": self.version,
            "environment": self.environment,
            "timestamp": self.timestamp.isoformat(),
            "components": [c.to_dict() for c in self.components],
        }


class HealthChecker:
    """Comprehensive health checker for all system components."""

    def __init__(self, start_time: float | None = None) -> None:
        """Initialize health checker.

        Args:
            start_time: Application start timestamp (for uptime calculation)
        """
        self._start_time = start_time or time.time()
        self._settings = get_settings()
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    async def close(self) -> None:
        """Close resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def check_postgres(self) -> ComponentHealth:
        """Check PostgreSQL database health."""
        start = time.time()
        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(
                self._settings.database_url.get_secret_value(),
                pool_pre_ping=True,
            )

            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                result.fetchone()

            await engine.dispose()
            latency = (time.time() - start) * 1000

            return ComponentHealth(
                name="postgres",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                message="Connected successfully",
            )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error("PostgreSQL health check failed", error=str(e))
            return ComponentHealth(
                name="postgres",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=f"Connection failed: {e!s}",
            )

    async def check_qdrant(self) -> ComponentHealth:
        """Check Qdrant vector database health."""
        start = time.time()
        try:
            client = await self._get_http_client()
            response = await client.get(f"{self._settings.qdrant_url}/readyz")
            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                # Get collection info
                collections_response = await client.get(
                    f"{self._settings.qdrant_url}/collections"
                )
                collections = collections_response.json().get("result", {}).get("collections", [])

                return ComponentHealth(
                    name="qdrant",
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                    message="Connected successfully",
                    details={"collection_count": len(collections)},
                )
            else:
                return ComponentHealth(
                    name="qdrant",
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=latency,
                    message=f"Unhealthy status: {response.status_code}",
                )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error("Qdrant health check failed", error=str(e))
            return ComponentHealth(
                name="qdrant",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=f"Connection failed: {e!s}",
            )

    async def check_neo4j(self) -> ComponentHealth:
        """Check Neo4j graph database health."""
        if not self._settings.graph_enabled:
            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.UNKNOWN,
                message="Graph database disabled",
            )

        start = time.time()
        try:
            from neo4j import AsyncGraphDatabase

            driver = AsyncGraphDatabase.driver(
                self._settings.neo4j_uri,
                auth=(
                    self._settings.neo4j_user,
                    self._settings.neo4j_password.get_secret_value(),
                ),
            )

            async with driver.session(database=self._settings.neo4j_database) as session:
                result = await session.run("RETURN 1 AS n")
                await result.single()

            await driver.close()
            latency = (time.time() - start) * 1000

            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                message="Connected successfully",
            )

        except ImportError:
            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.UNKNOWN,
                message="Neo4j driver not installed",
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error("Neo4j health check failed", error=str(e))
            return ComponentHealth(
                name="neo4j",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=f"Connection failed: {e!s}",
            )

    async def check_redis(self) -> ComponentHealth:
        """Check Redis cache health."""
        if not self._settings.redis_enabled:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNKNOWN,
                message="Redis cache disabled",
            )

        start = time.time()
        try:
            import redis.asyncio as redis

            client = redis.from_url(self._settings.redis_url)
            await client.ping()

            info = await client.info("memory")
            await client.close()

            latency = (time.time() - start) * 1000

            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                message="Connected successfully",
                details={
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "maxmemory_human": info.get("maxmemory_human", "unknown"),
                },
            )

        except ImportError:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNKNOWN,
                message="Redis client not installed",
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error("Redis health check failed", error=str(e))
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=f"Connection failed: {e!s}",
            )

    async def check_ollama(self) -> ComponentHealth:
        """Check Ollama embedding/LLM service health."""
        start = time.time()
        try:
            client = await self._get_http_client()
            response = await client.get(f"{self._settings.ollama_base_url}/api/tags")
            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]

                # Check if required models are available
                embed_model_available = any(
                    self._settings.ollama_embed_model in name for name in model_names
                )

                status = HealthStatus.HEALTHY if embed_model_available else HealthStatus.DEGRADED
                message = (
                    "Connected successfully"
                    if embed_model_available
                    else f"Embedding model '{self._settings.ollama_embed_model}' not found"
                )

                return ComponentHealth(
                    name="ollama",
                    status=status,
                    latency_ms=latency,
                    message=message,
                    details={
                        "model_count": len(models),
                        "embed_model_available": embed_model_available,
                        "available_models": model_names[:5],  # First 5 only
                    },
                )
            else:
                return ComponentHealth(
                    name="ollama",
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=latency,
                    message=f"Unhealthy status: {response.status_code}",
                )

        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error("Ollama health check failed", error=str(e))
            return ComponentHealth(
                name="ollama",
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=f"Connection failed: {e!s}",
            )

    async def check_all(self, include_optional: bool = True) -> SystemHealth:
        """Run all health checks concurrently.

        Args:
            include_optional: Whether to include optional components (neo4j, redis)

        Returns:
            SystemHealth with all component statuses
        """
        # Core checks (always run)
        checks = [
            self.check_postgres(),
            self.check_qdrant(),
            self.check_ollama(),
        ]

        # Optional checks
        if include_optional:
            checks.extend([
                self.check_neo4j(),
                self.check_redis(),
            ])

        # Run all checks concurrently
        results = await asyncio.gather(*checks, return_exceptions=True)

        components: list[ComponentHealth] = []
        for result in results:
            if isinstance(result, Exception):
                components.append(
                    ComponentHealth(
                        name="unknown",
                        status=HealthStatus.UNKNOWN,
                        message=f"Check failed: {result!s}",
                    )
                )
            else:
                components.append(result)

        # Determine overall status
        overall_status = self._determine_overall_status(components)

        return SystemHealth(
            status=overall_status,
            components=components,
            uptime_seconds=time.time() - self._start_time,
            version="0.1.0",
            environment=self._settings.environment.value,
        )

    def _determine_overall_status(self, components: list[ComponentHealth]) -> HealthStatus:
        """Determine overall system status based on component health.

        Priority:
        1. If any critical component is unhealthy -> UNHEALTHY
        2. If any component is degraded -> DEGRADED
        3. Otherwise -> HEALTHY
        """
        critical_components = {"postgres", "qdrant"}
        has_unhealthy_critical = False
        has_degraded = False

        for component in components:
            if component.status == HealthStatus.UNHEALTHY:
                if component.name in critical_components:
                    has_unhealthy_critical = True
            elif component.status == HealthStatus.DEGRADED:
                has_degraded = True

        if has_unhealthy_critical:
            return HealthStatus.UNHEALTHY
        elif has_degraded:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    async def liveness_check(self) -> bool:
        """Quick liveness check - is the service alive?

        Returns:
            True if service should not be restarted
        """
        # Just check if we can respond - don't check external deps
        return True

    async def readiness_check(self) -> bool:
        """Readiness check - is the service ready for traffic?

        Returns:
            True if service is ready to accept requests
        """
        health = await self.check_all(include_optional=False)
        return health.is_healthy
