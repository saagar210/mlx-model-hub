"""Database session management."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from mlx_hub.config import Settings, get_settings

# Global engine and session factory (initialized on first use)
_engine = None
_session_factory = None


def get_engine(settings: Settings):
    """Get or create async database engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            future=True,
        )
    return _engine


def get_session_factory(settings: Settings):
    """Get or create async session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine(settings)
        _session_factory = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for request.

    This is a FastAPI dependency that provides an async database session.
    The session is committed on success, rolled back on error.
    """
    session_factory = get_session_factory(settings)
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type alias for dependency injection
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def reset_engine() -> None:
    """Reset database engine (for testing)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
