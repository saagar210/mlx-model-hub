"""Tests for database module."""

import pytest

from sia.db import DatabaseManager


@pytest.mark.asyncio
async def test_db_manager_init(db_manager: DatabaseManager):
    """Test database manager initialization."""
    assert db_manager is not None
    assert db_manager._pool is not None
    assert db_manager._engine is not None


@pytest.mark.asyncio
async def test_db_health_check(db_manager: DatabaseManager):
    """Test database health check."""
    health = await db_manager.health_check()

    assert health["status"] == "healthy"
    assert "version" in health
    assert "PostgreSQL" in health["version"]
    assert "extensions" in health
    assert "vector" in health["extensions"]


@pytest.mark.asyncio
async def test_db_fetch(db_manager: DatabaseManager):
    """Test raw SQL fetch."""
    result = await db_manager.fetchval("SELECT 1")
    assert result == 1


@pytest.mark.asyncio
async def test_db_tables_exist(db_manager: DatabaseManager):
    """Test that all expected tables exist."""
    expected_tables = [
        "agents",
        "executions",
        "skills",
        "episodic_memory",
        "semantic_memory",
        "improvement_experiments",
        "feedback",
        "dspy_optimizations",
        "code_evolutions",
        "benchmarks",
        "benchmark_results",
    ]

    health = await db_manager.health_check()
    tables = health["tables"]

    for table in expected_tables:
        assert table in tables, f"Table {table} not found"


@pytest.mark.asyncio
async def test_db_connection_context(db_manager: DatabaseManager):
    """Test database connection context manager."""
    async with db_manager.connection() as conn:
        result = await conn.fetchval("SELECT 1")
        assert result == 1


@pytest.mark.asyncio
async def test_db_session_context(db_manager: DatabaseManager):
    """Test database session context manager."""
    from sqlalchemy import text

    async with db_manager.session() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
