"""
Pytest configuration and fixtures.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from sia.config import SIAConfig, get_config
from sia.db import DatabaseManager, init_db
from sia.db.connection import close_db


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def config() -> SIAConfig:
    """Get test configuration."""
    return get_config()


@pytest_asyncio.fixture(scope="session")
async def db_manager(config: SIAConfig) -> AsyncGenerator[DatabaseManager, None]:
    """Create a database manager for testing."""
    manager = await init_db(config)
    yield manager
    await close_db()


@pytest_asyncio.fixture
async def db_session(db_manager: DatabaseManager) -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for testing."""
    async with db_manager.session() as session:
        yield session
        # Rollback any changes made during the test
        await session.rollback()


@pytest.fixture
def sample_agent_data() -> dict:
    """Sample agent data for testing."""
    return {
        "name": "test_agent",
        "version": "1.0.0",
        "description": "A test agent",
        "type": "single",
        "code_module": "sia.agents.test",
        "original_code": "def execute(task): return {'result': 'test'}",
        "system_prompt": "You are a test agent.",
        "task_prompt_template": "Execute: {{task}}",
    }


@pytest.fixture
def sample_skill_data() -> dict:
    """Sample skill data for testing."""
    return {
        "name": "test_skill",
        "description": "A test skill for unit testing",
        "category": "testing",
        "code": "def test_skill(x): return x * 2",
        "signature": "test_skill(x: int) -> int",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}}},
        "output_schema": {"type": "integer"},
    }


@pytest.fixture
def sample_execution_data(sample_agent_data: dict) -> dict:
    """Sample execution data for testing."""
    return {
        "task_type": "test",
        "task_description": "Test task",
        "input_data": {"query": "test"},
    }
