"""Tests for entity extraction module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from knowledge.ai import AIResponse
from knowledge.entity_extraction import (
    Entity,
    ExtractionResult,
    Relationship,
    extract_entities,
    merge_entities,
)


class TestExtractEntities:
    """Tests for extract_entities function."""

    @pytest.mark.asyncio
    async def test_extract_entities_success(self):
        """Test successful entity extraction."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content='''
                {
                  "entities": [
                    {"name": "PostgreSQL", "type": "technology"},
                    {"name": "FastAPI", "type": "framework"},
                    {"name": "hybrid search", "type": "concept"}
                  ],
                  "relationships": [
                    {"from": "KAS", "to": "PostgreSQL", "type": "uses"},
                    {"from": "KAS", "to": "FastAPI", "type": "uses"}
                  ]
                }
                ''',
                model="deepseek",
            )
        )

        result = await extract_entities(
            title="Building Knowledge Systems",
            content="KAS uses PostgreSQL with pgvector for semantic search...",
            ai=mock_ai,
        )

        assert result.success
        assert len(result.entities) == 3
        assert len(result.relationships) == 2

        entity_names = [e.name for e in result.entities]
        assert "PostgreSQL" in entity_names
        assert "FastAPI" in entity_names

    @pytest.mark.asyncio
    async def test_extract_entities_handles_code_blocks(self):
        """Test handling of markdown code blocks in response."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content='''Here is the extracted data:
                ```json
                {
                  "entities": [{"name": "Python", "type": "technology"}],
                  "relationships": []
                }
                ```
                ''',
                model="deepseek",
            )
        )

        result = await extract_entities(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert result.success
        assert len(result.entities) == 1
        assert result.entities[0].name == "Python"

    @pytest.mark.asyncio
    async def test_extract_entities_handles_empty_response(self):
        """Test handling of empty entities/relationships."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content='{"entities": [], "relationships": []}',
                model="deepseek",
            )
        )

        result = await extract_entities(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert result.success
        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    @pytest.mark.asyncio
    async def test_extract_entities_handles_invalid_json(self):
        """Test handling of invalid JSON response."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="This is not valid JSON",
                model="deepseek",
            )
        )

        result = await extract_entities(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert not result.success
        assert "No JSON found" in result.error

    @pytest.mark.asyncio
    async def test_extract_entities_handles_ai_error(self):
        """Test handling of AI provider error."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="",
                model="deepseek",
                error="API error",
            )
        )

        result = await extract_entities(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert not result.success
        assert result.error == "API error"

    @pytest.mark.asyncio
    async def test_extract_entities_truncates_long_names(self):
        """Test that long entity names are truncated."""
        long_name = "A" * 150
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content=f'{{"entities": [{{"name": "{long_name}", "type": "concept"}}], "relationships": []}}',
                model="deepseek",
            )
        )

        result = await extract_entities(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert result.success
        assert len(result.entities[0].name) == 100


class TestMergeEntities:
    """Tests for merge_entities function."""

    def test_merge_deduplicates_entities(self):
        """Test that duplicate entities are merged."""
        result1 = ExtractionResult(
            entities=[
                Entity(name="Python", entity_type="technology"),
                Entity(name="FastAPI", entity_type="framework"),
            ],
            relationships=[],
            success=True,
        )
        result2 = ExtractionResult(
            entities=[
                Entity(name="python", entity_type="technology"),  # Same, different case
                Entity(name="PostgreSQL", entity_type="technology"),
            ],
            relationships=[],
            success=True,
        )

        merged = merge_entities([result1, result2])

        assert len(merged.entities) == 3  # Python, FastAPI, PostgreSQL

    def test_merge_deduplicates_relationships(self):
        """Test that duplicate relationships are merged."""
        result1 = ExtractionResult(
            entities=[],
            relationships=[
                Relationship(from_entity="KAS", to_entity="PostgreSQL", relation_type="uses"),
            ],
            success=True,
        )
        result2 = ExtractionResult(
            entities=[],
            relationships=[
                Relationship(from_entity="KAS", to_entity="PostgreSQL", relation_type="uses"),
                Relationship(from_entity="KAS", to_entity="FastAPI", relation_type="uses"),
            ],
            success=True,
        )

        merged = merge_entities([result1, result2])

        assert len(merged.relationships) == 2  # Deduplicated

    def test_merge_skips_failed_results(self):
        """Test that failed results are skipped during merge."""
        result1 = ExtractionResult(
            entities=[Entity(name="Python", entity_type="technology")],
            relationships=[],
            success=True,
        )
        result2 = ExtractionResult(
            entities=[Entity(name="Java", entity_type="technology")],
            relationships=[],
            success=False,
            error="API error",
        )

        merged = merge_entities([result1, result2])

        assert len(merged.entities) == 1
        assert merged.entities[0].name == "Python"
