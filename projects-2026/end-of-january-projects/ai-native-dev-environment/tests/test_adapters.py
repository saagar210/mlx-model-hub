"""Tests for external service adapters."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from universal_context_engine.adapters.kas import KASAdapter, KASResult, KASAnswer
from universal_context_engine.adapters.localcrew import LocalCrewAdapter, Subtask, ExecutionStatus


class TestKASAdapter:
    """Test KAS API adapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with mocked client."""
        adapter = KASAdapter(base_url="http://test:8000")
        return adapter

    @pytest.mark.asyncio
    async def test_search_success(self, adapter):
        """search() should return results on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"id": "1", "title": "Test Doc", "content": "Test content", "score": 0.9, "tags": ["test"]}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            results = await adapter.search("test query", limit=5)

        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].title == "Test Doc"
        assert results[0].score == 0.9

    @pytest.mark.asyncio
    async def test_search_error_returns_empty(self, adapter):
        """search() should return empty list on error."""
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.side_effect = httpx.HTTPError("Connection failed")
            mock_client.return_value = client

            results = await adapter.search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_ask_success(self, adapter):
        """ask() should return answer on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "answer": "Test answer",
            "sources": [{"id": "1", "title": "Source"}],
            "confidence": 0.85,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            answer = await adapter.ask("What is OAuth?")

        assert answer.answer == "Test answer"
        assert answer.confidence == 0.85
        assert len(answer.sources) == 1

    @pytest.mark.asyncio
    async def test_ask_error_returns_error_answer(self, adapter):
        """ask() should return error message on failure."""
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.side_effect = Exception("API error")
            mock_client.return_value = client

            answer = await adapter.ask("test question")

        assert "Error" in answer.answer
        assert answer.confidence == 0.0

    @pytest.mark.asyncio
    async def test_ingest_success(self, adapter):
        """ingest() should return ID on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new-doc-123"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            doc_id = await adapter.ingest(content="Test", title="Test Doc")

        assert doc_id == "new-doc-123"

    @pytest.mark.asyncio
    async def test_ingest_error_raises(self, adapter):
        """ingest() should raise on failure."""
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.side_effect = Exception("API error")
            mock_client.return_value = client

            with pytest.raises(RuntimeError, match="Failed to ingest"):
                await adapter.ingest(content="Test", title="Test Doc")

    @pytest.mark.asyncio
    async def test_health_healthy(self, adapter):
        """health() should return healthy on 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            health = await adapter.health()

        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_unhealthy(self, adapter):
        """health() should return unhealthy on error."""
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get.side_effect = Exception("Connection refused")
            mock_client.return_value = client

            health = await adapter.health()

        assert health["status"] == "unhealthy"
        assert "error" in health

    @pytest.mark.asyncio
    async def test_close_client(self, adapter):
        """close() should close the HTTP client."""
        mock_client = AsyncMock()
        adapter._client = mock_client

        await adapter.close()

        mock_client.aclose.assert_called_once()
        assert adapter._client is None


class TestLocalCrewAdapter:
    """Test LocalCrew API adapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with mocked client."""
        adapter = LocalCrewAdapter(base_url="http://test:8001")
        return adapter

    @pytest.mark.asyncio
    async def test_research_success_completed(self, adapter):
        """research() should return result for completed execution."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "completed",
            "result": "Research findings about the topic."
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await adapter.research("OAuth2 flows", depth="medium")

        assert "Research findings" in result

    @pytest.mark.asyncio
    async def test_research_error_returns_message(self, adapter):
        """research() should return error message on failure."""
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.side_effect = Exception("API error")
            mock_client.return_value = client

            result = await adapter.research("test topic")

        assert "Research failed" in result

    @pytest.mark.asyncio
    async def test_decompose_success_structured(self, adapter):
        """decompose() should return structured subtasks."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "subtasks": [
                {"id": "task-1", "description": "Set up project", "priority": 0, "complexity": "low"},
                {"id": "task-2", "description": "Implement auth", "priority": 1, "dependencies": ["task-1"]},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            subtasks = await adapter.decompose("Build authentication system")

        assert len(subtasks) == 2
        assert subtasks[0].id == "task-1"
        assert subtasks[1].dependencies == ["task-1"]

    @pytest.mark.asyncio
    async def test_decompose_success_string_list(self, adapter):
        """decompose() should handle string-only subtask lists."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "subtasks": ["Step 1: Setup", "Step 2: Implement", "Step 3: Test"]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            subtasks = await adapter.decompose("Build feature")

        assert len(subtasks) == 3
        assert subtasks[0].description == "Step 1: Setup"
        assert subtasks[0].id == "subtask-1"

    @pytest.mark.asyncio
    async def test_decompose_error_returns_fallback(self, adapter):
        """decompose() should return fallback subtask on error."""
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post.side_effect = Exception("API error")
            mock_client.return_value = client

            subtasks = await adapter.decompose("test task")

        assert len(subtasks) == 1
        assert "Decomposition failed" in subtasks[0].description

    @pytest.mark.asyncio
    async def test_get_status_success(self, adapter):
        """get_status() should return execution status."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "running",
            "progress": 0.5,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            status = await adapter.get_status("exec-123")

        assert status.status == "running"
        assert status.progress == 0.5

    @pytest.mark.asyncio
    async def test_get_status_error(self, adapter):
        """get_status() should return error status on failure."""
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get.side_effect = Exception("Connection failed")
            mock_client.return_value = client

            status = await adapter.get_status("exec-123")

        assert status.status == "error"
        assert status.error is not None

    @pytest.mark.asyncio
    async def test_health_healthy(self, adapter):
        """health() should return healthy on 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            health = await adapter.health()

        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_unhealthy(self, adapter):
        """health() should return unhealthy on error."""
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get.side_effect = Exception("Connection refused")
            mock_client.return_value = client

            health = await adapter.health()

        assert health["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_close_client(self, adapter):
        """close() should close the HTTP client."""
        mock_client = AsyncMock()
        adapter._client = mock_client

        await adapter.close()

        mock_client.aclose.assert_called_once()
        assert adapter._client is None


class TestDataClasses:
    """Test data classes."""

    def test_kas_result(self):
        """KASResult should store all fields."""
        result = KASResult(
            id="test-id",
            title="Test Title",
            content="Test content",
            score=0.95,
            tags=["tag1", "tag2"],
        )
        assert result.id == "test-id"
        assert result.tags == ["tag1", "tag2"]
        assert result.source == "kas"

    def test_kas_answer(self):
        """KASAnswer should store all fields."""
        answer = KASAnswer(
            answer="Test answer",
            sources=[{"id": "1"}],
            confidence=0.9,
        )
        assert answer.answer == "Test answer"
        assert answer.confidence == 0.9

    def test_subtask(self):
        """Subtask should store all fields."""
        subtask = Subtask(
            id="task-1",
            description="Test task",
            priority=1,
            dependencies=["task-0"],
            estimated_complexity="high",
        )
        assert subtask.id == "task-1"
        assert subtask.dependencies == ["task-0"]

    def test_execution_status(self):
        """ExecutionStatus should store all fields."""
        status = ExecutionStatus(
            execution_id="exec-1",
            status="completed",
            progress=1.0,
            result="Done",
        )
        assert status.execution_id == "exec-1"
        assert status.status == "completed"
        assert status.result == "Done"
