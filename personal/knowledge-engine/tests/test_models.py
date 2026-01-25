"""Tests for Pydantic models."""

import pytest
from uuid import uuid4

from knowledge_engine.models.documents import (
    Document,
    DocumentCreate,
    DocumentMetadata,
    DocumentType,
)
from knowledge_engine.models.search import (
    HybridSearchRequest,
    SearchResult,
    SearchResultItem,
)
from knowledge_engine.models.memory import (
    Memory,
    MemoryCreate,
    MemoryType,
)


class TestDocumentModels:
    """Tests for document models."""

    def test_document_create_minimal(self):
        """Test minimal document creation."""
        doc = DocumentCreate(content="Test content")
        assert doc.content == "Test content"
        assert doc.document_type == DocumentType.TEXT
        assert doc.namespace == "default"

    def test_document_create_full(self):
        """Test full document creation."""
        metadata = DocumentMetadata(
            source="https://example.com",
            author="Test Author",
            tags=["test", "example"],
        )
        doc = DocumentCreate(
            content="Test content",
            title="Test Title",
            document_type=DocumentType.MARKDOWN,
            namespace="custom",
            metadata=metadata,
        )
        assert doc.title == "Test Title"
        assert doc.document_type == DocumentType.MARKDOWN
        assert doc.namespace == "custom"
        assert doc.metadata.tags == ["test", "example"]

    def test_document_model(self):
        """Test full document model."""
        doc = Document(
            content="Test content",
            document_type=DocumentType.TEXT,
        )
        assert doc.id is not None
        assert doc.chunk_count == 0
        assert doc.is_deleted is False


class TestSearchModels:
    """Tests for search models."""

    def test_hybrid_search_request_minimal(self):
        """Test minimal search request."""
        req = HybridSearchRequest(query="test query")
        assert req.query == "test query"
        assert req.namespace == "default"
        assert req.limit == 10
        assert req.rerank is True

    def test_search_result_item(self):
        """Test search result item."""
        item = SearchResultItem(
            document_id=uuid4(),
            content="Test content",
            document_type=DocumentType.TEXT,
            namespace="default",
            score=0.95,
        )
        assert item.score == 0.95
        assert item.vector_score is None


class TestMemoryModels:
    """Tests for memory models."""

    def test_memory_create_minimal(self):
        """Test minimal memory creation."""
        memory = MemoryCreate(content="Remember this")
        assert memory.content == "Remember this"
        assert memory.memory_type == MemoryType.FACT
        assert memory.importance == 0.5

    def test_memory_model(self):
        """Test full memory model."""
        memory = Memory(
            content="Test memory",
            memory_type=MemoryType.PREFERENCE,
            importance=0.8,
        )
        assert memory.access_count == 0
        assert memory.is_deleted is False
