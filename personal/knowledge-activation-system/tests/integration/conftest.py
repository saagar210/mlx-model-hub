"""Integration test fixtures.

Provides real database connections and API clients for integration testing.
"""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from knowledge.config import get_settings
from knowledge.db import Database


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session-scoped async fixtures."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def integration_db() -> AsyncGenerator[Database, None]:
    """Real database connection for integration tests.

    Uses test database URL from environment or defaults to local test DB.
    """
    settings = get_settings()

    # Allow override for CI via environment variable
    test_db_url = os.environ.get("KAS_TEST_DATABASE_URL")
    if test_db_url:
        # Create modified settings with test URL
        settings = settings.model_copy(update={"database_url": test_db_url})
    else:
        # Use default test database (knowledge_test)
        settings = settings.model_copy(
            update={"database_url": settings.database_url.replace("/knowledge", "/knowledge_test")}
        )

    db = Database(settings)
    try:
        await db.connect()
        yield db
    finally:
        await db.close()


@pytest_asyncio.fixture(scope="function")
async def clean_db(integration_db: Database) -> AsyncGenerator[Database, None]:
    """Clean database before each test.

    Truncates all content tables while preserving schema.
    """
    async with integration_db._pool.acquire() as conn:
        await conn.execute("""
            TRUNCATE content, chunks, review_queue, search_queries CASCADE
        """)
    yield integration_db


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for API integration tests."""
    from knowledge.api.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-integration-key"},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def seeded_db(clean_db: Database) -> AsyncGenerator[Database, None]:
    """Database seeded with test content."""
    # Insert test content
    content_id = await clean_db.insert_content(
        title="Integration Test Document",
        content_type="note",
        source_ref="test/integration.md",
        namespace="default",
    )

    # Insert test chunks
    async with clean_db._pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO chunks (content_id, chunk_index, chunk_text)
            VALUES ($1, $2, $3)
            """,
            content_id,
            0,
            "This is a test document for integration testing. "
            "It contains information about Python programming and machine learning.",
        )

    yield clean_db


# Markers for pytest
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (requires real database)",
    )
