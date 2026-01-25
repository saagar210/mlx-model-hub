"""Tests for the MCP server tools.

Note: FastMCP @mcp.tool() decorators wrap functions in FunctionTool objects.
To test the underlying functions, we access their .fn attribute or test
through the MCP server interface.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_context_store():
    """Mock the context store."""
    with patch("universal_context_engine.server.context_store") as mock:
        yield mock


@pytest.fixture
def mock_git_info():
    """Mock git info detection."""
    with patch("universal_context_engine.server.get_git_info") as mock:
        mock.return_value = ("/test/project", "main")
        yield mock


@pytest.mark.asyncio
async def test_save_context_tool(mock_context_store, mock_git_info):
    """Test the save_context MCP tool."""
    from universal_context_engine.models import ContextItem, ContextType
    from universal_context_engine.server import save_context

    # Setup mock
    mock_item = ContextItem(
        id="test-id-123",
        content="Test content",
        context_type=ContextType.DECISION,
        project="/test/project",
        branch="main",
        timestamp=datetime.now(UTC),
        metadata={},
    )
    mock_context_store.save = AsyncMock(return_value=mock_item)

    # Access the underlying function via .fn attribute
    result = await save_context.fn(
        content="Test content",
        context_type="decision",
        metadata={"key": "value"},
    )

    # Verify
    assert result["id"] == "test-id-123"
    assert result["type"] == "decision"
    assert result["project"] == "/test/project"
    mock_context_store.save.assert_called_once()


@pytest.mark.asyncio
async def test_search_context_tool(mock_context_store, mock_git_info):
    """Test the search_context MCP tool."""
    from universal_context_engine.models import ContextItem, ContextType, SearchResult
    from universal_context_engine.server import search_context

    # Setup mock
    mock_results = [
        SearchResult(
            item=ContextItem(
                id="result-1",
                content="Found content",
                context_type=ContextType.CONTEXT,
                project="/test/project",
                timestamp=datetime.now(UTC),
            ),
            score=0.95,
            distance=0.05,
        )
    ]
    mock_context_store.search = AsyncMock(return_value=mock_results)

    # Access the underlying function via .fn attribute
    results = await search_context.fn(
        query="test query",
        limit=5,
    )

    # Verify
    assert len(results) == 1
    assert results[0]["id"] == "result-1"
    assert results[0]["score"] == 0.95
    mock_context_store.search.assert_called_once()


@pytest.mark.asyncio
async def test_get_recent_tool(mock_context_store, mock_git_info):
    """Test the get_recent MCP tool."""
    from universal_context_engine.models import ContextItem, ContextType
    from universal_context_engine.server import get_recent

    # Setup mock
    mock_items = [
        ContextItem(
            id="recent-1",
            content="Recent item",
            context_type=ContextType.SESSION,
            project="/test/project",
            branch="main",
            timestamp=datetime.now(UTC),
        )
    ]
    mock_context_store.get_recent = AsyncMock(return_value=mock_items)

    # Access the underlying function via .fn attribute
    results = await get_recent.fn(hours=24)

    # Verify
    assert len(results) == 1
    assert results[0]["id"] == "recent-1"
    mock_context_store.get_recent.assert_called_once()


@pytest.mark.asyncio
async def test_recall_work_tool(mock_context_store, mock_git_info):
    """Test the recall_work MCP tool."""
    from universal_context_engine.server import recall_work

    # Setup mock
    mock_context_store.get_recent = AsyncMock(return_value=[])
    mock_context_store.get_stats = AsyncMock(return_value={
        "session": 5,
        "decision": 10,
        "pattern": 3,
        "context": 20,
        "blocker": 2,
        "error": 1,
    })

    # Access the underlying function via .fn attribute
    result = await recall_work.fn()

    # Verify
    assert result["project"] == "/test/project"
    assert result["branch"] == "main"
    assert "summary" in result
    assert result["total_items"] == 41


@pytest.mark.asyncio
async def test_context_stats_tool(mock_context_store):
    """Test the context_stats MCP tool."""
    from universal_context_engine.server import context_stats

    # Setup mock
    mock_context_store.get_stats = AsyncMock(return_value={
        "session": 5,
        "decision": 10,
        "pattern": 3,
        "context": 20,
        "blocker": 2,
        "error": 1,
    })

    # Access the underlying function via .fn attribute
    result = await context_stats.fn()

    # Verify
    assert result["total_items"] == 41
    assert result["items_by_type"]["session"] == 5
    assert result["items_by_type"]["decision"] == 10
