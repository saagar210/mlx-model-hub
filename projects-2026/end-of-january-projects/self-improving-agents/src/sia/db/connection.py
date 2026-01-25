"""
Database Connection Management

Provides async connection pool and session management using asyncpg and SQLAlchemy.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sia.config import SIAConfig, get_config


class DatabaseManager:
    """
    Manages database connections and provides session factories.

    Supports both raw asyncpg connections for performance-critical operations
    and SQLAlchemy sessions for ORM operations.
    """

    def __init__(self, config: SIAConfig | None = None):
        self.config = config or get_config()
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._pool: asyncpg.Pool | None = None

    @property
    def database_url(self) -> str:
        """Get the database URL with async driver."""
        url = self.config.database.url
        # Ensure we're using asyncpg driver
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def raw_database_url(self) -> str:
        """Get the database URL without SQLAlchemy driver prefix."""
        url = self.config.database.url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url

    async def init(self) -> None:
        """Initialize database connections."""
        # Create SQLAlchemy async engine
        self._engine = create_async_engine(
            self.database_url,
            pool_size=self.config.database.pool_size,
            max_overflow=self.config.database.pool_max_overflow,
            echo=self.config.database.echo,
            pool_pre_ping=True,
        )

        # Create session factory
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        # Create asyncpg pool for raw queries
        self._pool = await asyncpg.create_pool(
            self.raw_database_url,
            min_size=2,
            max_size=self.config.database.pool_size,
        )

    async def close(self) -> None:
        """Close all database connections."""
        if self._pool:
            await self._pool.close()
            self._pool = None

        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async session for ORM operations.

        Usage:
            async with db_manager.session() as session:
                result = await session.execute(select(Agent))
        """
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call init() first.")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Get a raw asyncpg connection for performance-critical operations.

        Usage:
            async with db_manager.connection() as conn:
                result = await conn.fetch("SELECT * FROM agents")
        """
        if not self._pool:
            raise RuntimeError("Database not initialized. Call init() first.")

        async with self._pool.acquire() as conn:
            yield conn

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return status."""
        async with self.connection() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute a query and return all results."""
        async with self.connection() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Execute a query and return a single row."""
        async with self.connection() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single value."""
        async with self.connection() as conn:
            return await conn.fetchval(query, *args)

    async def health_check(self) -> dict[str, Any]:
        """
        Check database health.

        Returns:
            dict with health status and details.
        """
        try:
            async with self.connection() as conn:
                # Basic connectivity
                version = await conn.fetchval("SELECT version()")

                # Check extensions
                extensions = await conn.fetch(
                    "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm')"
                )
                ext_names = [r["extname"] for r in extensions]

                # Check tables exist
                tables = await conn.fetch(
                    """
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                    """
                )
                table_names = [r["tablename"] for r in tables]

                # Pool stats
                pool_stats = {
                    "size": self._pool.get_size() if self._pool else 0,
                    "free": self._pool.get_idle_size() if self._pool else 0,
                    "min": self._pool.get_min_size() if self._pool else 0,
                    "max": self._pool.get_max_size() if self._pool else 0,
                }

                return {
                    "status": "healthy",
                    "version": version,
                    "extensions": ext_names,
                    "tables": table_names,
                    "pool": pool_stats,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Global database manager instance
_db_manager: DatabaseManager | None = None


async def get_db_manager() -> DatabaseManager:
    """Get the global database manager, initializing if needed."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.init()
    return _db_manager


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get a database session.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    manager = await get_db_manager()
    async with manager.session() as session:
        yield session


async def init_db(config: SIAConfig | None = None) -> DatabaseManager:
    """
    Initialize the database manager.

    Args:
        config: Optional configuration. Uses default if not provided.

    Returns:
        Initialized DatabaseManager instance.
    """
    global _db_manager
    _db_manager = DatabaseManager(config)
    await _db_manager.init()
    return _db_manager


async def close_db() -> None:
    """Close the global database manager."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None


# For synchronous contexts (like CLI startup)
def get_db_manager_sync() -> DatabaseManager:
    """Get database manager synchronously (for CLI usage)."""
    return asyncio.get_event_loop().run_until_complete(get_db_manager())
