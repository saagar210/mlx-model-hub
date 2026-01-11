"""Shared pytest fixtures for MLX Hub tests."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from mlx_hub.config import Settings

# Import all models to register them with SQLModel.metadata
from mlx_hub.db.models import Dataset, Model, ModelVersion, TrainingJob  # noqa: F401


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Get test settings with temporary storage paths."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        storage_base_path=tmp_path / "storage",
        storage_models_path=tmp_path / "storage/models",
        storage_datasets_path=tmp_path / "storage/datasets",
        debug=True,
    )


@pytest.fixture
def test_db_engine():
    """Create test database engine with in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine


@pytest_asyncio.fixture
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    async_session_factory = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables and enable foreign keys
    async with test_db_engine.begin() as conn:
        # Enable foreign key enforcement for SQLite
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_factory() as session:
        # Enable FK enforcement for this session
        await session.execute(text("PRAGMA foreign_keys=ON"))
        try:
            yield session
        finally:
            await session.rollback()

    # Drop tables
    async with test_db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await test_db_engine.dispose()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""
    # Import here to avoid circular imports
    from mlx_hub.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
