"""Tests for KAS SDK client."""

import pytest
from httpx import Response
from pytest_httpx import HTTPXMock

from kas_client import (
    KASClient,
    KASClientSync,
    KASAPIError,
    KASConnectionError,
    KASValidationError,
    SearchResponse,
    AskResponse,
    IngestResponse,
    HealthResponse,
    ReviewItem,
    ReviewStats,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client():
    return KASClient("http://localhost:8000")


@pytest.fixture
def sync_client():
    return KASClientSync("http://localhost:8000")


@pytest.fixture
def mock_health_response():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {"database": "connected", "embeddings": "connected"},
        "stats": {"total_content": 100, "total_chunks": 500},
    }


@pytest.fixture
def mock_search_response():
    return {
        "results": [
            {
                "content_id": "abc123",
                "title": "Test Document",
                "content_type": "note",
                "score": 0.85,
                "namespace": "default",
                "chunk_text": "Some relevant text",
                "source_ref": None,
                "vector_similarity": 0.8,
                "bm25_score": 0.9,
            }
        ],
        "query": "test query",
        "total": 1,
        "source": "hybrid",
        "reranked": False,
    }


@pytest.fixture
def mock_ask_response():
    return {
        "query": "How does X work?",
        "answer": "X works by doing Y and Z.",
        "confidence": "high",
        "confidence_score": 0.92,
        "citations": [
            {
                "index": 1,
                "title": "Document A",
                "content_type": "note",
                "chunk_text": "Relevant context",
            }
        ],
        "warning": None,
        "error": None,
    }


@pytest.fixture
def mock_ingest_response():
    return {
        "content_id": "new-123",
        "success": True,
        "chunks_created": 3,
        "message": "Successfully ingested",
        "namespace": "default",
    }


# =============================================================================
# Health Tests
# =============================================================================


@pytest.mark.asyncio
async def test_health(client: KASClient, httpx_mock: HTTPXMock, mock_health_response):
    httpx_mock.add_response(
        url="http://localhost:8000/api/v1/health",
        json=mock_health_response,
    )

    health = await client.health()

    assert health.status == "healthy"
    assert health.version == "1.0.0"
    assert health.services.database == "connected"
    assert health.stats.total_content == 100


@pytest.mark.asyncio
async def test_stats(client: KASClient, httpx_mock: HTTPXMock, mock_health_response):
    httpx_mock.add_response(
        url="http://localhost:8000/api/v1/health",
        json=mock_health_response,
    )

    stats = await client.stats()

    assert stats.total_content == 100
    assert stats.total_chunks == 500


# =============================================================================
# Search Tests
# =============================================================================


@pytest.mark.asyncio
async def test_search_basic(client: KASClient, httpx_mock: HTTPXMock, mock_search_response):
    httpx_mock.add_response(json=mock_search_response)

    results = await client.search("test query")

    assert isinstance(results, SearchResponse)
    assert results.total == 1
    assert len(results.results) == 1
    assert results.results[0].title == "Test Document"
    assert results.results[0].score == 0.85


@pytest.mark.asyncio
async def test_search_with_options(client: KASClient, httpx_mock: HTTPXMock, mock_search_response):
    httpx_mock.add_response(json=mock_search_response)

    results = await client.search(
        "test query",
        limit=5,
        namespace="notes",
        min_score=0.5,
        rerank=True,
    )

    assert results.total == 1
    # Check that request had correct params
    request = httpx_mock.get_requests()[0]
    assert "limit=5" in str(request.url)
    assert "namespace=notes" in str(request.url)
    assert "min_score=0.5" in str(request.url)
    assert "rerank=true" in str(request.url)


@pytest.mark.asyncio
async def test_batch_search(client: KASClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={
            "results": [
                {"query": "query1", "results": [], "error": None},
                {"query": "query2", "results": [], "error": None},
            ],
            "total_queries": 2,
            "successful": 2,
            "failed": 0,
        }
    )

    results = await client.batch_search(["query1", "query2"])

    assert results.total_queries == 2
    assert results.successful == 2


@pytest.mark.asyncio
async def test_batch_search_max_queries(client: KASClient):
    with pytest.raises(KASValidationError, match="Maximum 10 queries"):
        await client.batch_search(["q"] * 11)


# =============================================================================
# Q&A Tests
# =============================================================================


@pytest.mark.asyncio
async def test_ask(client: KASClient, httpx_mock: HTTPXMock, mock_ask_response):
    httpx_mock.add_response(
        url="http://localhost:8000/search/ask",
        json=mock_ask_response,
    )

    answer = await client.ask("How does X work?")

    assert isinstance(answer, AskResponse)
    assert answer.confidence == "high"
    assert answer.confidence_score == 0.92
    assert len(answer.citations) == 1
    assert answer.citations[0].title == "Document A"


# =============================================================================
# Ingest Tests
# =============================================================================


@pytest.mark.asyncio
async def test_ingest(client: KASClient, httpx_mock: HTTPXMock, mock_ingest_response):
    httpx_mock.add_response(
        url="http://localhost:8000/api/v1/ingest/document",
        json=mock_ingest_response,
    )

    result = await client.ingest(
        content="# Test\n\nSome content",
        title="Test Doc",
        namespace="test",
        tags=["test"],
    )

    assert isinstance(result, IngestResponse)
    assert result.success is True
    assert result.chunks_created == 3
    assert result.content_id == "new-123"


@pytest.mark.asyncio
async def test_ingest_youtube(client: KASClient, httpx_mock: HTTPXMock, mock_ingest_response):
    httpx_mock.add_response(
        url="http://localhost:8000/api/v1/ingest/youtube",
        json=mock_ingest_response,
    )

    result = await client.ingest_youtube("abc123", namespace="youtube")

    assert result.success is True


@pytest.mark.asyncio
async def test_ingest_bookmark(client: KASClient, httpx_mock: HTTPXMock, mock_ingest_response):
    httpx_mock.add_response(
        url="http://localhost:8000/api/v1/ingest/bookmark",
        json=mock_ingest_response,
    )

    result = await client.ingest_bookmark(
        "https://example.com",
        title="Example",
        namespace="bookmarks",
    )

    assert result.success is True


# =============================================================================
# Namespace Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_namespaces(client: KASClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://localhost:8000/api/v1/namespaces",
        json={
            "namespaces": [
                {"name": "default", "document_count": 50},
                {"name": "notes", "document_count": 30},
            ]
        },
    )

    namespaces = await client.list_namespaces()

    assert len(namespaces) == 2
    assert namespaces[0].name == "default"
    assert namespaces[0].document_count == 50


# =============================================================================
# Review Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_review_items(client: KASClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={
            "items": [
                {
                    "content_id": "item1",
                    "title": "Review Item",
                    "content_type": "note",
                    "preview_text": "Some preview",
                    "is_new": True,
                    "is_learning": False,
                    "reps": 0,
                }
            ]
        }
    )

    items = await client.get_review_items(limit=5)

    assert len(items) == 1
    assert items[0].title == "Review Item"
    assert items[0].is_new is True


@pytest.mark.asyncio
async def test_submit_review(client: KASClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://localhost:8000/api/v1/review/submit",
        json={
            "success": True,
            "next_review": "2024-01-15T10:00:00Z",
            "new_state": "Review",
        },
    )

    result = await client.submit_review("item1", rating=3)

    assert result.success is True
    assert result.new_state == "Review"


@pytest.mark.asyncio
async def test_submit_review_invalid_rating(client: KASClient):
    with pytest.raises(KASValidationError, match="Rating must be between 1 and 4"):
        await client.submit_review("item1", rating=5)


@pytest.mark.asyncio
async def test_get_review_stats(client: KASClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://localhost:8000/api/v1/review/stats",
        json={
            "due_now": 5,
            "new": 10,
            "learning": 3,
            "review": 2,
            "total_active": 15,
            "reviews_today": 7,
        },
    )

    stats = await client.get_review_stats()

    assert stats.due_now == 5
    assert stats.reviews_today == 7


# =============================================================================
# Content Management Tests
# =============================================================================


@pytest.mark.asyncio
async def test_delete_content(client: KASClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="http://localhost:8000/api/v1/content/abc123",
        json={"deleted": True},
    )

    result = await client.delete_content("abc123")

    assert result is True


@pytest.mark.asyncio
async def test_batch_delete(client: KASClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        json={"deleted": 3, "errors": []},
    )

    result = await client.batch_delete(["id1", "id2", "id3"])

    assert result["deleted"] == 3


@pytest.mark.asyncio
async def test_batch_delete_max_items(client: KASClient):
    with pytest.raises(KASValidationError, match="Maximum 100 items"):
        await client.batch_delete(["id"] * 101)


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_api_error(client: KASClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        status_code=404,
        json={"detail": "Not found"},
    )

    with pytest.raises(KASAPIError) as exc_info:
        await client.search("query")

    assert exc_info.value.status_code == 404
    assert "Not found" in exc_info.value.message


@pytest.mark.asyncio
async def test_connection_error(client: KASClient, httpx_mock: HTTPXMock):
    import httpx
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

    with pytest.raises(KASConnectionError):
        await client.health()


# =============================================================================
# Context Manager Tests
# =============================================================================


@pytest.mark.asyncio
async def test_async_context_manager(httpx_mock: HTTPXMock, mock_health_response):
    httpx_mock.add_response(json=mock_health_response)

    async with KASClient("http://localhost:8000") as client:
        health = await client.health()
        assert health.status == "healthy"


# =============================================================================
# Sync Client Tests
# =============================================================================


def test_sync_health(sync_client: KASClientSync, httpx_mock: HTTPXMock, mock_health_response):
    httpx_mock.add_response(json=mock_health_response)

    health = sync_client.health()

    assert health.status == "healthy"
    sync_client.close()


def test_sync_search(sync_client: KASClientSync, httpx_mock: HTTPXMock, mock_search_response):
    httpx_mock.add_response(json=mock_search_response)

    results = sync_client.search("test")

    assert results.total == 1
    sync_client.close()


def test_sync_context_manager(httpx_mock: HTTPXMock, mock_health_response):
    httpx_mock.add_response(json=mock_health_response)

    with KASClientSync("http://localhost:8000") as client:
        health = client.health()
        assert health.status == "healthy"
