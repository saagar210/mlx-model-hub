"""Tests for database entity operations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


class TestEntityOperations:
    """Tests for entity database operations."""

    @pytest.mark.asyncio
    async def test_insert_entity(self, mock_db: MagicMock):
        """Test inserting a single entity."""
        content_id = uuid4()
        expected_id = uuid4()

        mock_db.insert_entity = AsyncMock(return_value=expected_id)

        entity_id = await mock_db.insert_entity(
            content_id=content_id,
            name="PostgreSQL",
            entity_type="technology",
            confidence=0.95,
        )

        assert entity_id == expected_id

    @pytest.mark.asyncio
    async def test_insert_entities_batch(self, mock_db: MagicMock):
        """Test batch inserting entities."""
        content_id = uuid4()
        entities = [
            {"name": "Python", "entity_type": "technology", "confidence": 0.9},
            {"name": "FastAPI", "entity_type": "framework", "confidence": 0.85},
        ]
        expected_ids = [uuid4(), uuid4()]

        mock_db.insert_entities_batch = AsyncMock(return_value=expected_ids)

        entity_ids = await mock_db.insert_entities_batch(
            content_id=content_id,
            entities=entities,
        )

        assert len(entity_ids) == 2
        assert entity_ids == expected_ids

    @pytest.mark.asyncio
    async def test_insert_entities_batch_empty(self, mock_db: MagicMock):
        """Test batch inserting empty list returns empty."""
        content_id = uuid4()

        mock_db.insert_entities_batch = AsyncMock(return_value=[])

        entity_ids = await mock_db.insert_entities_batch(
            content_id=content_id,
            entities=[],
        )

        assert entity_ids == []

    @pytest.mark.asyncio
    async def test_insert_relationship(self, mock_db: MagicMock):
        """Test inserting a relationship."""
        from_id = uuid4()
        to_id = uuid4()
        expected_id = uuid4()

        mock_db.insert_relationship = AsyncMock(return_value=expected_id)

        rel_id = await mock_db.insert_relationship(
            from_entity_id=from_id,
            to_entity_id=to_id,
            relation_type="uses",
            confidence=0.9,
        )

        assert rel_id == expected_id

    @pytest.mark.asyncio
    async def test_insert_relationship_duplicate(self, mock_db: MagicMock):
        """Test inserting duplicate relationship returns None."""
        from_id = uuid4()
        to_id = uuid4()

        mock_db.insert_relationship = AsyncMock(return_value=None)

        rel_id = await mock_db.insert_relationship(
            from_entity_id=from_id,
            to_entity_id=to_id,
            relation_type="uses",
        )

        assert rel_id is None

    @pytest.mark.asyncio
    async def test_get_entities_by_content(self, mock_db: MagicMock):
        """Test getting entities by content ID."""
        content_id = uuid4()
        expected_entities = [
            {"id": uuid4(), "name": "Python", "entity_type": "technology", "confidence": 0.9, "created_at": None},
            {"id": uuid4(), "name": "FastAPI", "entity_type": "framework", "confidence": 0.85, "created_at": None},
        ]

        mock_db.get_entities_by_content = AsyncMock(return_value=expected_entities)

        entities = await mock_db.get_entities_by_content(content_id)

        assert len(entities) == 2
        assert entities[0]["name"] == "Python"
        assert entities[1]["name"] == "FastAPI"

    @pytest.mark.asyncio
    async def test_get_entity_by_name(self, mock_db: MagicMock):
        """Test getting entity by name."""
        expected_entity = {
            "id": uuid4(),
            "content_id": uuid4(),
            "name": "PostgreSQL",
            "entity_type": "technology",
            "confidence": 0.95,
            "created_at": None,
        }

        mock_db.get_entity_by_name = AsyncMock(return_value=expected_entity)

        entity = await mock_db.get_entity_by_name("PostgreSQL")

        assert entity is not None
        assert entity["name"] == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_get_entity_by_name_with_type(self, mock_db: MagicMock):
        """Test getting entity by name with type filter."""
        expected_entity = {
            "id": uuid4(),
            "content_id": uuid4(),
            "name": "PostgreSQL",
            "entity_type": "technology",
            "confidence": 0.95,
            "created_at": None,
        }

        mock_db.get_entity_by_name = AsyncMock(return_value=expected_entity)

        entity = await mock_db.get_entity_by_name("PostgreSQL", entity_type="technology")

        assert entity is not None
        assert entity["entity_type"] == "technology"

    @pytest.mark.asyncio
    async def test_get_entity_by_name_not_found(self, mock_db: MagicMock):
        """Test getting entity that doesn't exist."""
        mock_db.get_entity_by_name = AsyncMock(return_value=None)

        entity = await mock_db.get_entity_by_name("NonExistent")

        assert entity is None

    @pytest.mark.asyncio
    async def test_get_relationships_by_entity(self, mock_db: MagicMock):
        """Test getting relationships for an entity."""
        entity_id = uuid4()
        expected_relationships = [
            {
                "id": uuid4(),
                "relation_type": "uses",
                "confidence": 0.9,
                "from_name": "KAS",
                "from_type": "tool",
                "to_name": "PostgreSQL",
                "to_type": "technology",
            },
        ]

        mock_db.get_relationships_by_entity = AsyncMock(return_value=expected_relationships)

        relationships = await mock_db.get_relationships_by_entity(entity_id)

        assert len(relationships) == 1
        assert relationships[0]["relation_type"] == "uses"
        assert relationships[0]["from_name"] == "KAS"

    @pytest.mark.asyncio
    async def test_get_entity_stats(self, mock_db: MagicMock):
        """Test getting entity statistics."""
        expected_stats = [
            {"entity_type": "technology", "count": 50, "unique_names": 45},
            {"entity_type": "framework", "count": 30, "unique_names": 28},
        ]

        mock_db.get_entity_stats = AsyncMock(return_value=expected_stats)

        stats = await mock_db.get_entity_stats()

        assert len(stats) == 2
        assert stats[0]["entity_type"] == "technology"
        assert stats[0]["count"] == 50

    @pytest.mark.asyncio
    async def test_get_connected_entities(self, mock_db: MagicMock):
        """Test getting most connected entities."""
        expected_connected = [
            {"name": "Python", "entity_type": "technology", "connection_count": 25},
            {"name": "PostgreSQL", "entity_type": "technology", "connection_count": 20},
        ]

        mock_db.get_connected_entities = AsyncMock(return_value=expected_connected)

        connected = await mock_db.get_connected_entities(limit=10)

        assert len(connected) == 2
        assert connected[0]["name"] == "Python"
        assert connected[0]["connection_count"] == 25

    @pytest.mark.asyncio
    async def test_delete_entities_by_content(self, mock_db: MagicMock):
        """Test deleting entities by content ID."""
        content_id = uuid4()

        mock_db.delete_entities_by_content = AsyncMock(return_value=5)

        count = await mock_db.delete_entities_by_content(content_id)

        assert count == 5

    @pytest.mark.asyncio
    async def test_delete_entities_by_content_none(self, mock_db: MagicMock):
        """Test deleting entities when none exist."""
        content_id = uuid4()

        mock_db.delete_entities_by_content = AsyncMock(return_value=0)

        count = await mock_db.delete_entities_by_content(content_id)

        assert count == 0
