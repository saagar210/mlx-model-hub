"""Tests for auto-tagging module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from knowledge.ai import AIResponse
from knowledge.autotag import extract_tags, suggest_tags


class TestExtractTags:
    """Tests for extract_tags function."""

    @pytest.mark.asyncio
    async def test_extract_tags_success(self):
        """Test successful tag extraction."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="python, machine-learning, fastapi, postgresql",
                model="deepseek",
            )
        )

        tags = await extract_tags(
            title="Building ML APIs with FastAPI",
            content="This tutorial shows how to build machine learning APIs...",
            ai=mock_ai,
        )

        assert len(tags) == 4
        assert "python" in tags
        assert "machine-learning" in tags
        assert "fastapi" in tags
        assert "postgresql" in tags

    @pytest.mark.asyncio
    async def test_extract_tags_cleans_tags(self):
        """Test that tags are properly cleaned."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content='"Python", [machine learning], (FastAPI)',
                model="deepseek",
            )
        )

        tags = await extract_tags(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert "python" in tags
        assert "machine-learning" in tags
        assert "fastapi" in tags

    @pytest.mark.asyncio
    async def test_extract_tags_limits_to_seven(self):
        """Test that max 7 tags are returned."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="one, two, three, four, five, six, seven, eight, nine",
                model="deepseek",
            )
        )

        tags = await extract_tags(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert len(tags) == 7

    @pytest.mark.asyncio
    async def test_extract_tags_removes_duplicates(self):
        """Test that duplicate tags are removed."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="python, Python, PYTHON, fastapi",
                model="deepseek",
            )
        )

        tags = await extract_tags(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert tags.count("python") == 1
        assert "fastapi" in tags

    @pytest.mark.asyncio
    async def test_extract_tags_truncates_long_tags(self):
        """Test that long tags are truncated to 25 chars."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="this-is-a-very-long-tag-that-should-be-truncated",
                model="deepseek",
            )
        )

        tags = await extract_tags(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert len(tags) == 1
        assert len(tags[0]) <= 25

    @pytest.mark.asyncio
    async def test_extract_tags_filters_short_tags(self):
        """Test that tags shorter than 2 chars are filtered."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="a, py, python, ai, ml",
                model="deepseek",
            )
        )

        tags = await extract_tags(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert "a" not in tags
        assert "py" in tags
        assert "python" in tags
        assert "ai" in tags
        assert "ml" in tags

    @pytest.mark.asyncio
    async def test_extract_tags_handles_ai_error(self):
        """Test handling of AI provider error."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="",
                model="deepseek",
                error="API error",
            )
        )

        tags = await extract_tags(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert tags == []

    @pytest.mark.asyncio
    async def test_extract_tags_handles_exception(self):
        """Test handling of exceptions during extraction."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(side_effect=Exception("Connection error"))

        tags = await extract_tags(
            title="Test",
            content="Test content",
            ai=mock_ai,
        )

        assert tags == []


class TestSuggestTags:
    """Tests for suggest_tags function."""

    @pytest.mark.asyncio
    async def test_suggest_tags_excludes_existing(self):
        """Test that existing tags are excluded from suggestions."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="python, fastapi, postgresql, docker",
                model="deepseek",
            )
        )

        new_tags = await suggest_tags(
            title="Test",
            content="Test content",
            existing_tags=["python", "fastapi"],
            ai=mock_ai,
        )

        assert "python" not in new_tags
        assert "fastapi" not in new_tags
        assert "postgresql" in new_tags
        assert "docker" in new_tags

    @pytest.mark.asyncio
    async def test_suggest_tags_with_no_existing(self):
        """Test suggesting tags when no existing tags."""
        mock_ai = MagicMock()
        mock_ai.generate = AsyncMock(
            return_value=AIResponse(
                content="python, fastapi",
                model="deepseek",
            )
        )

        new_tags = await suggest_tags(
            title="Test",
            content="Test content",
            existing_tags=None,
            ai=mock_ai,
        )

        assert "python" in new_tags
        assert "fastapi" in new_tags
