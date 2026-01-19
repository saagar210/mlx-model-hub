"""Tests for query router module."""

from __future__ import annotations

import pytest

from knowledge.query_router import (
    QueryType,
    SearchParams,
    analyze_query,
    classify_query,
    get_search_params,
)


class TestClassifyQuery:
    """Tests for classify_query function."""

    def test_simple_query(self):
        """Test simple lookup queries."""
        assert classify_query("FastAPI") == QueryType.SIMPLE
        assert classify_query("python requests") == QueryType.SIMPLE
        assert classify_query("docker compose") == QueryType.SIMPLE

    def test_definition_query(self):
        """Test definition queries."""
        assert classify_query("What is RAG?") == QueryType.DEFINITION
        assert classify_query("What's a vector database?") == QueryType.DEFINITION
        assert classify_query("define microservices") == QueryType.DEFINITION
        assert classify_query("explain kubernetes") == QueryType.DEFINITION

    def test_how_to_query(self):
        """Test how-to/procedural queries."""
        assert classify_query("How to implement authentication?") == QueryType.HOW_TO
        assert classify_query("How do I create a REST API?") == QueryType.HOW_TO
        assert classify_query("Steps to deploy Docker containers") == QueryType.HOW_TO
        assert classify_query("Guide to setting up PostgreSQL") == QueryType.HOW_TO

    def test_comparison_query(self):
        """Test comparison queries."""
        assert classify_query("PostgreSQL vs MySQL") == QueryType.COMPARISON
        assert classify_query("Compare FastAPI and Flask") == QueryType.COMPARISON
        assert classify_query("Difference between REST and GraphQL") == QueryType.COMPARISON
        assert classify_query("MongoDB versus PostgreSQL") == QueryType.COMPARISON

    def test_list_query(self):
        """Test list/enumeration queries."""
        assert classify_query("What are the features of FastAPI?") == QueryType.LIST
        assert classify_query("List of Python web frameworks") == QueryType.LIST
        assert classify_query("Types of database indexes") == QueryType.LIST
        assert classify_query("Examples of REST endpoints") == QueryType.LIST

    def test_complex_query(self):
        """Test complex queries requiring reasoning."""
        assert classify_query("Why should I use connection pooling in my database?") == QueryType.COMPLEX
        assert classify_query(
            "When should I consider using a message queue in my microservices architecture?"
        ) == QueryType.COMPLEX
        assert classify_query(
            "What are the trade-offs between synchronous and asynchronous communication?"
        ) == QueryType.COMPLEX

    def test_case_insensitivity(self):
        """Test that classification is case-insensitive."""
        assert classify_query("WHAT IS RAG?") == QueryType.DEFINITION
        assert classify_query("How To Build An API") == QueryType.HOW_TO
        assert classify_query("PostgreSQL VS MySQL") == QueryType.COMPARISON


class TestGetSearchParams:
    """Tests for get_search_params function."""

    def test_simple_params(self):
        """Test parameters for simple queries."""
        params = get_search_params(QueryType.SIMPLE)
        assert params.limit == 5
        assert params.rerank is False
        assert params.multi_hop is False

    def test_definition_params(self):
        """Test parameters for definition queries."""
        params = get_search_params(QueryType.DEFINITION)
        assert params.limit == 5
        assert params.rerank is True
        assert params.vector_weight == 0.6  # Higher vector weight for semantic

    def test_how_to_params(self):
        """Test parameters for how-to queries."""
        params = get_search_params(QueryType.HOW_TO)
        assert params.limit == 10
        assert params.rerank is True
        assert params.include_related is True

    def test_comparison_params(self):
        """Test parameters for comparison queries."""
        params = get_search_params(QueryType.COMPARISON)
        assert params.limit == 20
        assert params.rerank is True
        assert params.multi_hop is True  # Need info about both entities

    def test_complex_params(self):
        """Test parameters for complex queries."""
        params = get_search_params(QueryType.COMPLEX)
        assert params.limit == 15
        assert params.rerank is True
        assert params.multi_hop is True


class TestAnalyzeQuery:
    """Tests for analyze_query function."""

    def test_returns_tuple(self):
        """Test that analyze_query returns correct tuple."""
        query_type, params = analyze_query("What is PostgreSQL?")

        assert isinstance(query_type, QueryType)
        assert isinstance(params, SearchParams)

    def test_params_match_type(self):
        """Test that returned params match query type."""
        query_type, params = analyze_query("How to build a REST API?")

        assert query_type == QueryType.HOW_TO
        expected_params = get_search_params(QueryType.HOW_TO)
        assert params.limit == expected_params.limit
        assert params.rerank == expected_params.rerank

    def test_empty_query(self):
        """Test handling of empty query."""
        query_type, params = analyze_query("")
        assert query_type == QueryType.SIMPLE  # Default fallback

    def test_whitespace_query(self):
        """Test handling of whitespace-only query."""
        query_type, params = analyze_query("   ")
        assert query_type == QueryType.SIMPLE


class TestSearchParamsDataclass:
    """Tests for SearchParams dataclass."""

    def test_creation(self):
        """Test creating SearchParams."""
        params = SearchParams(
            limit=10,
            rerank=True,
            vector_weight=0.5,
            include_related=False,
            multi_hop=False,
        )
        assert params.limit == 10
        assert params.rerank is True
        assert params.vector_weight == 0.5

    def test_defaults_not_available(self):
        """Test that all fields are required (no defaults)."""
        with pytest.raises(TypeError):
            SearchParams(limit=10)  # type: ignore
