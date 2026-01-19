"""Integration test fixtures.

Provides real database connections and API clients for integration testing.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from knowledge.config import get_settings
from knowledge.db import Database

# Store original database URL at module load time to avoid double-replacement
# Read BEFORE any test runs and before any env vars are set
_original_db_url: str = get_settings().database_url


def _get_test_db_url() -> str:
    """Get the test database URL, computing it once."""
    # Allow override for CI via environment variable
    test_db_url = os.environ.get("KAS_TEST_DATABASE_URL")
    if test_db_url:
        return test_db_url

    # Use default test database (knowledge_test)
    # Only replace the database name at the end (after last /)
    if _original_db_url.endswith("/knowledge"):
        return _original_db_url[:-10] + "/knowledge_test"
    else:
        # Fallback: replace last occurrence only
        return "/knowledge_test".join(_original_db_url.rsplit("/knowledge", 1))


# Compute the test database URL once at import time
TEST_DATABASE_URL = _get_test_db_url()


@pytest_asyncio.fixture
async def integration_db() -> AsyncGenerator[Database, None]:
    """Real database connection for integration tests.

    Uses test database URL from environment or defaults to local test DB.
    Creates a new connection per test to avoid event loop conflicts.
    """
    from knowledge.config import clear_settings_cache

    # Set environment variable so API also uses test database
    # Pydantic Settings uses KNOWLEDGE_ prefix
    os.environ["KNOWLEDGE_DATABASE_URL"] = TEST_DATABASE_URL

    # Clear settings cache so it picks up the test database URL
    clear_settings_cache()

    settings = get_settings()
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
async def api_client(integration_db: Database) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for API integration tests.

    Depends on integration_db to ensure database module uses correct connection.
    """
    import knowledge.db as db_module
    from knowledge.api.main import app

    # Reset the global database singleton so it uses fresh connection in this event loop
    if db_module._db is not None:
        try:
            await db_module._db.disconnect()
        except Exception:
            pass
        db_module._db = None

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "test-integration-key"},
    ) as client:
        yield client

    # Cleanup: close the API's database connection
    await db_module.close_db()


@pytest_asyncio.fixture
async def seeded_db(clean_db: Database) -> AsyncGenerator[Database, None]:
    """Database seeded with test content."""
    # Insert test content using current API
    # Skip review queue to avoid FSRS trigger validation
    content_id = await clean_db.insert_content(
        filepath="test/integration.md",
        content_type="note",
        title="Integration Test Document",
        content_for_hash="This is a test document for integration testing.",
        metadata={"namespace": "default"},
        add_to_review=False,
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
