"""Tests for session management."""

import tempfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from universal_context_engine.models import ContextType


class MockEmbeddingClient:
    """Mock embedding client for testing."""

    async def embed(self, text: str) -> list[float]:
        hash_val = hash(text) % 1000
        return [float(hash_val + i) / 1000 for i in range(768)]


class MockGenerateClient:
    """Mock generate client for testing."""

    async def generate(self, prompt: str, system: str | None = None) -> str:
        if "decision" in prompt.lower():
            return "- Use JWT tokens\n- Implement rate limiting"
        return "Test session summary: worked on authentication"


@pytest.fixture
def mock_clients():
    """Mock both embedding and generate clients."""
    with patch("universal_context_engine.context_store.embedding_client", MockEmbeddingClient()):
        with patch("universal_context_engine.summarizer.generate_client", MockGenerateClient()):
            yield


@pytest.fixture
def temp_store(mock_clients):
    """Create a temporary context store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("universal_context_engine.context_store.embedding_client", MockEmbeddingClient()):
            from universal_context_engine.context_store import ContextStore
            store = ContextStore(persist_directory=tmpdir)
            store._embedding_client = MockEmbeddingClient()
            yield store


@pytest.fixture
def session_manager(temp_store, mock_clients):
    """Create a session manager with mocked dependencies."""
    with patch("universal_context_engine.session.context_store", temp_store):
        with patch("universal_context_engine.session.SessionManager._get_git_info") as mock_git:
            mock_git.return_value = ("/test/project", "main")
            from universal_context_engine.session import SessionManager
            manager = SessionManager()
            yield manager


@pytest.mark.asyncio
async def test_start_session(session_manager):
    """Test starting a new session."""
    result = await session_manager.start_session()

    assert "session_id" in result
    assert result["project"] == "/test/project"
    assert result["branch"] == "main"
    assert "recent_context" in result
    assert "sessions" in result["recent_context"]
    assert "decisions" in result["recent_context"]
    assert "blockers" in result["recent_context"]


@pytest.mark.asyncio
async def test_end_session(session_manager, mock_clients):
    """Test ending a session with summarization."""
    # Start a session first
    await session_manager.start_session()

    # End the session
    result = await session_manager.end_session(
        conversation_excerpt="Worked on implementing authentication with JWT tokens",
        files_modified=["auth.py", "config.py"],
    )

    assert "session_id" in result
    assert "summary" in result
    assert result["project"] == "/test/project"
    assert result["files_modified"] == 2


@pytest.mark.asyncio
async def test_capture_decision(session_manager, temp_store):
    """Test capturing a decision."""
    result = await session_manager.capture_decision(
        decision="Use JWT for authentication tokens",
        category="security",
        rationale="Better for stateless microservices",
    )

    assert "id" in result
    assert result["decision"] == "Use JWT for authentication tokens"
    assert result["category"] == "security"
    assert result["project"] == "/test/project"


@pytest.mark.asyncio
async def test_capture_blocker(session_manager, temp_store):
    """Test capturing a blocker."""
    result = await session_manager.capture_blocker(
        description="Need access to production database",
        severity="high",
        context="Required for migration testing",
    )

    assert "id" in result
    assert result["description"] == "Need access to production database"
    assert result["severity"] == "high"


@pytest.mark.asyncio
async def test_get_blockers(session_manager, temp_store):
    """Test getting blockers."""
    # First capture a blocker
    await session_manager.capture_blocker(
        description="Test blocker",
        severity="medium",
    )

    # Get blockers
    blockers = await session_manager.get_blockers()

    assert len(blockers) >= 1
    assert blockers[0]["description"] == "Test blocker"
    assert blockers[0]["severity"] == "medium"
    assert blockers[0]["resolved"] is False
