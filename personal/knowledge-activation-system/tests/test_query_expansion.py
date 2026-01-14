"""Tests for query expansion module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from knowledge.query_expansion import (
    SYNONYMS,
    ExpandedQuery,
    expand_term,
    expand_query,
    get_all_synonyms,
    add_synonym,
    _normalize_term,
    _extract_terms,
)


class TestNormalizeTerm:
    """Test term normalization."""

    def test_lowercase(self):
        assert _normalize_term("Python") == "python"

    def test_strip_whitespace(self):
        assert _normalize_term("  python  ") == "python"

    def test_combined(self):
        assert _normalize_term("  PYTHON  ") == "python"


class TestExtractTerms:
    """Test term extraction from queries."""

    def test_single_word(self):
        terms = _extract_terms("python")
        assert "python" in terms

    def test_multiple_words(self):
        terms = _extract_terms("python fastapi")
        assert "python" in terms
        assert "fastapi" in terms

    def test_extracts_phrases(self):
        terms = _extract_terms("ci cd pipeline")
        # Should include 2-word and 3-word phrases
        assert any("ci cd" in t for t in terms)


class TestExpandTerm:
    """Test single term expansion."""

    def test_direct_lookup(self):
        expansions = expand_term("python")
        assert "py" in expansions
        assert "python3" in expansions

    def test_reverse_lookup(self):
        # 'js' should expand to 'javascript' and its synonyms
        expansions = expand_term("js")
        assert "javascript" in expansions

    def test_no_match(self):
        expansions = expand_term("xyznonexistent123")
        assert expansions == []

    def test_case_insensitive(self):
        exp1 = expand_term("Python")
        exp2 = expand_term("PYTHON")
        exp3 = expand_term("python")
        assert set(exp1) == set(exp2) == set(exp3)

    def test_kubernetes_synonyms(self):
        expansions = expand_term("kubernetes")
        assert "k8s" in expansions
        assert "kube" in expansions

    def test_database_synonyms(self):
        expansions = expand_term("postgresql")
        assert "postgres" in expansions
        assert "psql" in expansions
        assert "pg" in expansions

    def test_llm_synonyms(self):
        expansions = expand_term("llm")
        assert "large language model" in expansions


class TestExpandQuery:
    """Test full query expansion."""

    @pytest.fixture
    def mock_settings(self):
        with patch("knowledge.query_expansion.get_settings") as mock:
            mock.return_value = MagicMock(search_enable_query_expansion=True)
            yield mock

    @pytest.fixture
    def mock_cache(self):
        with patch("knowledge.query_expansion.get_cache") as mock:
            cache = AsyncMock()
            cache.get.return_value = None
            cache.set.return_value = True
            mock.return_value = cache
            yield cache

    async def test_expansion_disabled(self):
        """Test no expansion when disabled."""
        with patch("knowledge.query_expansion.get_settings") as mock:
            mock.return_value = MagicMock(search_enable_query_expansion=False)

            result = await expand_query("python fastapi")

            assert result.expansion_applied is False
            assert result.expanded == "python fastapi"
            assert result.terms_added == []

    async def test_expansion_adds_terms(self, mock_settings, mock_cache):
        """Test expansion adds synonym terms."""
        result = await expand_query("python api")

        assert result.expansion_applied is True
        assert result.original == "python api"
        # Should have added synonyms
        assert len(result.terms_added) > 0

    async def test_expansion_limits_terms(self, mock_settings, mock_cache):
        """Test expansion limits to 5 terms."""
        # Query with many expandable terms
        result = await expand_query("python javascript typescript golang rust")

        assert len(result.terms_added) <= 5

    async def test_no_duplicate_terms(self, mock_settings, mock_cache):
        """Test expansion doesn't add terms already in query."""
        result = await expand_query("python py python3")

        # These are already in the query, shouldn't be added
        for term in result.terms_added:
            assert term not in ["python", "py", "python3"]

    async def test_returns_cached_result(self, mock_settings):
        """Test returns cached expansion result."""
        with patch("knowledge.query_expansion.get_cache") as mock:
            cache = AsyncMock()
            cache.get.return_value = {
                "original": "test",
                "expanded": "test expanded",
                "terms_added": ["expanded"],
                "expansion_applied": True,
            }
            mock.return_value = cache

            result = await expand_query("test")

            assert result.original == "test"
            assert result.expanded == "test expanded"
            assert result.expansion_applied is True


class TestSynonymDictionary:
    """Test the synonym dictionary."""

    def test_programming_languages(self):
        assert "python" in SYNONYMS
        assert "javascript" in SYNONYMS
        assert "typescript" in SYNONYMS
        assert "golang" in SYNONYMS

    def test_frameworks_python(self):
        assert "fastapi" in SYNONYMS
        assert "django" in SYNONYMS

    def test_frameworks_javascript(self):
        assert "nextjs" in SYNONYMS
        assert "react" in SYNONYMS

    def test_databases(self):
        assert "postgresql" in SYNONYMS
        assert "mongodb" in SYNONYMS
        assert "redis" in SYNONYMS

    def test_ai_ml_terms(self):
        assert "llm" in SYNONYMS
        assert "rag" in SYNONYMS
        assert "embedding" in SYNONYMS

    def test_claude_anthropic(self):
        assert "claude" in SYNONYMS
        assert "mcp" in SYNONYMS

    def test_devops(self):
        assert "docker" in SYNONYMS
        assert "kubernetes" in SYNONYMS
        assert "ci/cd" in SYNONYMS


class TestGetAllSynonyms:
    """Test get_all_synonyms function."""

    def test_returns_copy(self):
        syns = get_all_synonyms()
        assert syns is not SYNONYMS
        assert syns == SYNONYMS

    def test_modification_safe(self):
        syns = get_all_synonyms()
        syns["test_new"] = ["test"]
        assert "test_new" not in SYNONYMS


class TestAddSynonym:
    """Test add_synonym function."""

    def test_add_new_primary(self):
        # Clean up after test
        original = SYNONYMS.get("testterm123", None)

        try:
            add_synonym("testterm123", ["testsynonym"])
            assert "testterm123" in SYNONYMS
            assert "testsynonym" in SYNONYMS["testterm123"]
        finally:
            if original is None and "testterm123" in SYNONYMS:
                del SYNONYMS["testterm123"]

    def test_add_to_existing(self):
        # Add to existing term
        original_python = SYNONYMS.get("python", []).copy()

        try:
            add_synonym("python", ["newpythonsynonym"])
            assert "newpythonsynonym" in SYNONYMS["python"]
        finally:
            SYNONYMS["python"] = original_python

    def test_normalizes_terms(self):
        original = SYNONYMS.get("normalizetest", None)

        try:
            add_synonym("  NormalizeTest  ", ["  SYNONYM  "])
            assert "normalizetest" in SYNONYMS
            assert "synonym" in SYNONYMS["normalizetest"]
        finally:
            if original is None and "normalizetest" in SYNONYMS:
                del SYNONYMS["normalizetest"]
