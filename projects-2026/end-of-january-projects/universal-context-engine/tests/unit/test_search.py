"""Tests for search components."""

import pytest
from uuid import uuid4

from uce.search.ranking import RankingEngine


class TestRankingEngine:
    """Tests for RankingEngine."""

    def test_rrf_fusion_single_list(self):
        """Test RRF with single result list."""
        ranker = RankingEngine(rrf_k=60)

        results = [
            {"id": uuid4(), "score": 0.9, "match_type": "vector"},
            {"id": uuid4(), "score": 0.8, "match_type": "vector"},
        ]

        fused = ranker.rrf_fusion(results)

        # Should preserve order based on RRF scores
        assert len(fused) == 2
        assert fused[0]["score"] > fused[1]["score"]

    def test_rrf_fusion_multiple_lists(self):
        """Test RRF with multiple result lists."""
        ranker = RankingEngine(rrf_k=60)

        id1 = uuid4()
        id2 = uuid4()
        id3 = uuid4()

        vector_results = [
            {"id": id1, "score": 0.9, "match_type": "vector"},
            {"id": id2, "score": 0.8, "match_type": "vector"},
        ]

        bm25_results = [
            {"id": id2, "score": 0.85, "match_type": "bm25"},  # id2 appears in both
            {"id": id3, "score": 0.7, "match_type": "bm25"},
        ]

        fused = ranker.rrf_fusion(vector_results, bm25_results)

        # id2 should have highest score (appears in both lists)
        scores = {r["id"]: r["score"] for r in fused}
        assert scores[id2] > scores[id1]
        assert scores[id2] > scores[id3]

    def test_normalize_scores(self):
        """Test score normalization."""
        ranker = RankingEngine()

        results = [
            {"id": uuid4(), "score": 100},
            {"id": uuid4(), "score": 50},
            {"id": uuid4(), "score": 0},
        ]

        normalized = ranker.normalize_scores(results)

        assert normalized[0]["score"] == 1.0
        assert normalized[1]["score"] == 0.5
        assert normalized[2]["score"] == 0.0

    def test_normalize_empty_list(self):
        """Test normalization of empty list."""
        ranker = RankingEngine()
        normalized = ranker.normalize_scores([])
        assert normalized == []

    def test_normalize_same_scores(self):
        """Test normalization when all scores are the same."""
        ranker = RankingEngine()

        results = [
            {"id": uuid4(), "score": 5},
            {"id": uuid4(), "score": 5},
        ]

        normalized = ranker.normalize_scores(results)

        # All should be 1.0 when scores are equal
        assert all(r["score"] == 1.0 for r in normalized)

    def test_rank_results(self):
        """Test result ranking."""
        ranker = RankingEngine()

        id1, id2, id3 = uuid4(), uuid4(), uuid4()
        results = [
            {"id": id1, "score": 0.5},
            {"id": id2, "score": 0.9},
            {"id": id3, "score": 0.7},
        ]

        ranked = ranker.rank(results)

        assert ranked[0]["id"] == id2
        assert ranked[1]["id"] == id3
        assert ranked[2]["id"] == id1

    def test_rank_with_limit(self):
        """Test ranking with top_k limit."""
        ranker = RankingEngine()

        results = [{"id": uuid4(), "score": i} for i in range(10)]
        ranked = ranker.rank(results, top_k=3)

        assert len(ranked) == 3
        assert ranked[0]["score"] == 9
