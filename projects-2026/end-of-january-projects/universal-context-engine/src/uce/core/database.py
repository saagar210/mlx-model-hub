"""Database connection management."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

from .config import settings


_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    """Get or create the database connection pool."""
    global _pool
    if _pool is None:
        # Convert SQLAlchemy URL to asyncpg URL format
        db_url = settings.database_url.replace("+asyncpg", "").replace("postgresql://", "")
        _pool = await asyncpg.create_pool(
            f"postgresql://{db_url}",
            min_size=2,
            max_size=settings.db_pool_size,
        )
    return _pool


async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection() -> AsyncIterator[asyncpg.Connection]:
    """Get a database connection from the pool."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn


async def execute_migration(sql: str) -> None:
    """Execute a SQL migration."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(sql)
