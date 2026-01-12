"""Pytest fixtures for Knowledge Activation System tests."""

from __future__ import annotations

import os
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from knowledge.config import Settings
from knowledge.db import Database


# Test settings with test database
@pytest.fixture
def test_settings() -> Settings:
    """Create settings for testing."""
    return Settings(
        database_url=os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql://knowledge:localdev@localhost:5432/knowledge_test",
        ),
        ollama_url="http://localhost:11434",
        embedding_model="nomic-embed-text",
        vault_path="/tmp/test_vault",
        knowledge_folder="Knowledge",
    )


@pytest.fixture
def settings() -> Settings:
    """Create default settings (may use real DB)."""
    return Settings()


# Database fixtures
@pytest_asyncio.fixture
async def db(test_settings: Settings) -> AsyncGenerator[Database, None]:
    """Create and connect a test database instance."""
    database = Database(test_settings)
    try:
        await database.connect()
        yield database
    finally:
        await database.disconnect()


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database for unit tests."""
    mock = MagicMock(spec=Database)
    mock.connect = AsyncMock()
    mock.disconnect = AsyncMock()
    mock.check_health = AsyncMock(
        return_value={
            "status": "healthy",
            "extensions": ["vector", "vectorscale"],
            "content_count": 10,
            "chunk_count": 50,
        }
    )
    mock.bm25_search = AsyncMock(return_value=[])
    mock.vector_search = AsyncMock(return_value=[])
    mock.get_stats = AsyncMock(
        return_value={
            "content_by_type": {"youtube": 5, "bookmark": 3, "file": 2},
            "total_content": 10,
            "total_chunks": 50,
            "review_active": 8,
            "review_due": 2,
        }
    )
    return mock


# Embedding fixtures
@pytest.fixture
def mock_embedding() -> list[float]:
    """Create a mock 768-dimensional embedding."""
    import random

    random.seed(42)
    return [random.random() for _ in range(768)]


@pytest.fixture
def mock_embeddings_service() -> MagicMock:
    """Create a mock embeddings service."""
    from knowledge.embeddings import EmbeddingService, OllamaStatus

    mock = MagicMock(spec=EmbeddingService)
    mock.check_health = AsyncMock(
        return_value=OllamaStatus(
            healthy=True,
            models_loaded=["nomic-embed-text:latest", "mxbai-rerank-base-v1:latest"],
        )
    )

    # Return deterministic embeddings
    import random

    random.seed(42)
    mock_embedding = [random.random() for _ in range(768)]
    mock.embed_text = AsyncMock(return_value=mock_embedding)
    mock.embed_batch = AsyncMock(return_value=[mock_embedding])
    mock.close = AsyncMock()

    return mock


# Search fixtures
@pytest.fixture
def sample_bm25_results() -> list[tuple[UUID, str, str, float]]:
    """Sample BM25 search results."""
    return [
        (uuid4(), "Introduction to Machine Learning", "youtube", 0.95),
        (uuid4(), "Deep Learning Fundamentals", "bookmark", 0.82),
        (uuid4(), "Neural Networks Explained", "file", 0.71),
    ]


@pytest.fixture
def sample_vector_results() -> list[tuple[UUID, str, str, str | None, float]]:
    """Sample vector search results."""
    return [
        (
            uuid4(),
            "Machine Learning Basics",
            "youtube",
            "Machine learning is a subset of AI...",
            0.89,
        ),
        (
            uuid4(),
            "Deep Learning Fundamentals",
            "bookmark",
            "Deep learning uses neural networks...",
            0.85,
        ),
        (
            uuid4(),
            "AI Overview",
            "note",
            "Artificial intelligence encompasses...",
            0.78,
        ),
    ]


@pytest.fixture
def sample_content_data() -> dict:
    """Sample content data for testing."""
    return {
        "filepath": "Knowledge/YouTube/test-video.md",
        "content_type": "youtube",
        "title": "Test Video Title",
        "content_for_hash": "This is the content to hash",
        "url": "https://youtube.com/watch?v=test123",
        "summary": "A test video summary",
        "tags": ["test", "video"],
        "metadata": {"channel": "Test Channel", "duration": 600},
    }


@pytest.fixture
def sample_chunks() -> list[dict]:
    """Sample chunks for testing."""
    return [
        {
            "chunk_index": 0,
            "chunk_text": "This is the first chunk of content.",
            "embedding": [0.1] * 768,
            "source_ref": "timestamp:0:00",
            "start_char": 0,
            "end_char": 36,
        },
        {
            "chunk_index": 1,
            "chunk_text": "This is the second chunk of content.",
            "embedding": [0.2] * 768,
            "source_ref": "timestamp:3:00",
            "start_char": 37,
            "end_char": 73,
        },
    ]


# Utility fixtures
@pytest.fixture
def anyio_backend() -> str:
    """Specify asyncio as the async backend."""
    return "asyncio"


# Markers
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires services)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
