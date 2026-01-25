"""Tests for entity resolution."""

import pytest

from uce.entity_resolution.aliases import AliasRegistry, alias_registry
from uce.entity_resolution.extractors import PatternExtractor, CompositeExtractor


class TestAliasRegistry:
    """Tests for AliasRegistry."""

    def test_resolve_known_alias(self):
        """Test resolving a known alias."""
        registry = AliasRegistry()
        assert registry.resolve("pg") == "postgresql"
        assert registry.resolve("oauth2") == "oauth"
        assert registry.resolve("ts") == "typescript"

    def test_resolve_unknown_returns_original(self):
        """Test that unknown names return lowercase original."""
        registry = AliasRegistry()
        assert registry.resolve("unknownThing") == "unknownthing"

    def test_add_alias(self):
        """Test adding a custom alias."""
        registry = AliasRegistry()
        registry.add_alias("myalias", "mycanonical")
        assert registry.resolve("myalias") == "mycanonical"

    def test_get_aliases(self):
        """Test getting aliases for a canonical name."""
        registry = AliasRegistry()
        aliases = registry.get_aliases("postgresql")
        assert "pg" in aliases
        assert "postgres" in aliases

    def test_case_insensitive(self):
        """Test that resolution is case-insensitive."""
        registry = AliasRegistry()
        assert registry.resolve("OAuth2") == "oauth"
        assert registry.resolve("FASTAPI") == "fastapi"


class TestPatternExtractor:
    """Tests for PatternExtractor."""

    def test_extract_known_technologies(self):
        """Test extracting known technology names."""
        extractor = PatternExtractor(include_generic=False)
        text = "We're using FastAPI with PostgreSQL and OAuth for authentication."
        entities = extractor.extract(text)

        names = [e.name for e in entities]
        assert "fastapi" in names
        assert "postgresql" in names
        assert "oauth" in names

    def test_extract_with_generic_patterns(self):
        """Test extracting with generic patterns enabled."""
        extractor = PatternExtractor(include_generic=True)
        text = "The MyCustomClass handles `config.yaml` files."
        entities = extractor.extract(text)

        names = [e.name for e in entities]
        # Should find CamelCase and backtick patterns
        assert any("mycustomclass" in n.lower() for n in names)

    def test_extract_code_references(self):
        """Test extracting code references in backticks."""
        extractor = PatternExtractor(include_generic=True)
        text = "Edit the `settings.py` file and run `main.py`."
        entities = extractor.extract(text)

        names = [e.name for e in entities]
        assert any("settings.py" in n for n in names)


class TestCompositeExtractor:
    """Tests for CompositeExtractor."""

    def test_composite_extracts_multiple_types(self):
        """Test that composite extractor finds entities from all sources."""
        extractor = CompositeExtractor()
        text = "FastAPI database project uses PostgreSQL."
        entities = extractor.extract(text)

        names = [e.name for e in entities]
        assert "fastapi" in names
        assert "postgresql" in names

    def test_deduplication(self):
        """Test that duplicates are removed."""
        extractor = CompositeExtractor()
        text = "FastAPI FastAPI FastAPI"
        entities = extractor.extract(text)

        names = [e.name for e in entities]
        assert names.count("fastapi") == 1
