"""Pytest fixtures for UCE tests."""

import asyncio
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio

from uce.models.context_item import ContextItem, BiTemporalMetadata, RelevanceSignals
from uce.models.entity import Entity


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_context_item() -> ContextItem:
    """Create a sample context item for testing."""
    return ContextItem(
        id=uuid4(),
        source="kas",
        source_id="test_123",
        source_url="https://example.com/doc",
        content_type="document_chunk",
        title="Test Document - OAuth Implementation",
        content="This document describes how to implement OAuth 2.0 authentication using FastAPI and JWT tokens.",
        temporal=BiTemporalMetadata(t_valid=datetime.utcnow()),
        tags=["auth", "oauth", "fastapi"],
        relevance=RelevanceSignals(source_quality=0.9),
        metadata={"chunk_index": 0},
    )


@pytest.fixture
def sample_entity() -> Entity:
    """Create a sample entity for testing."""
    return Entity(
        id=uuid4(),
        canonical_name="oauth",
        display_name="OAuth",
        entity_type="technology",
        aliases=["oauth2", "oauth 2.0"],
        mention_count=5,
    )


@pytest.fixture
def sample_context_items() -> list[ContextItem]:
    """Create multiple sample context items."""
    return [
        ContextItem(
            source="kas",
            source_id=f"doc_{i}",
            content_type="document_chunk",
            title=f"Document {i}",
            content=f"Content for document {i} about {'OAuth' if i % 2 == 0 else 'FastAPI'}",
            temporal=BiTemporalMetadata(t_valid=datetime.utcnow()),
        )
        for i in range(5)
    ]
