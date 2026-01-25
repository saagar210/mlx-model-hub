"""Tests for aggregation utilities and cross-source functionality."""

import pytest
from datetime import datetime, timedelta

from personal_context.schema import ContextItem, ContextSource
from personal_context.utils.fusion import (
    reciprocal_rank_fusion,
    deduplicate_by_content,
    time_decay_score,
    apply_source_weights,
)
from personal_context.utils.entities import (
    extract_entities_from_text,
    extract_entities_from_items,
    find_entity_mentions,
)
from personal_context.utils.relevance import (
    compute_relevance_score,
    compute_query_boost,
    rerank_by_relevance,
    interleave_sources,
)


def make_item(
    id: str,
    source: ContextSource,
    title: str,
    content: str,
    score: float = 0.5,
    hours_ago: int = 0,
) -> ContextItem:
    """Helper to create test items."""
    return ContextItem(
        id=id,
        source=source,
        title=title,
        content=content,
        relevance_score=score,
        timestamp=datetime.now() - timedelta(hours=hours_ago),
    )


class TestReciprocaldRankFusion:
    """Tests for RRF fusion."""

    def test_single_source(self):
        """RRF with single source returns same order."""
        items = [
            make_item("1", ContextSource.OBSIDIAN, "First", "content"),
            make_item("2", ContextSource.OBSIDIAN, "Second", "content"),
        ]
        fused = reciprocal_rank_fusion([items])
        assert len(fused) == 2
        assert fused[0].id == "1"
        assert fused[1].id == "2"

    def test_multiple_sources(self):
        """RRF combines multiple sources."""
        obsidian = [
            make_item("obs1", ContextSource.OBSIDIAN, "OAuth Guide", "auth content"),
            make_item("obs2", ContextSource.OBSIDIAN, "JWT Guide", "jwt content"),
        ]
        git = [
            make_item("git1", ContextSource.GIT, "Add OAuth", "commit"),
            make_item("git2", ContextSource.GIT, "Fix auth", "commit"),
        ]
        fused = reciprocal_rank_fusion([obsidian, git])
        assert len(fused) == 4
        # First items from each should be ranked higher
        ids = [item.id for item in fused]
        assert ids.index("obs1") < ids.index("obs2")
        assert ids.index("git1") < ids.index("git2")

    def test_empty_sources(self):
        """RRF handles empty lists."""
        fused = reciprocal_rank_fusion([[], []])
        assert fused == []


class TestDeduplication:
    """Tests for content deduplication."""

    def test_removes_duplicates(self):
        """Dedup removes items with same content."""
        items = [
            make_item("1", ContextSource.OBSIDIAN, "Auth", "authentication guide for oauth"),
            make_item("2", ContextSource.GIT, "Auth", "authentication guide for oauth"),  # Duplicate
        ]
        deduped = deduplicate_by_content(items, similarity_threshold=0.9)
        assert len(deduped) == 1

    def test_keeps_different(self):
        """Dedup keeps items with different content."""
        items = [
            make_item("1", ContextSource.OBSIDIAN, "Auth", "oauth authentication guide"),
            make_item("2", ContextSource.GIT, "Deploy", "kubernetes deployment config"),
        ]
        deduped = deduplicate_by_content(items)
        assert len(deduped) == 2


class TestTimeDecay:
    """Tests for time decay scoring."""

    def test_recent_higher(self):
        """Recent items score higher."""
        recent = make_item("1", ContextSource.OBSIDIAN, "Recent", "content", hours_ago=1)
        old = make_item("2", ContextSource.OBSIDIAN, "Old", "content", hours_ago=168)

        recent_score = time_decay_score(recent, 1.0)
        old_score = time_decay_score(old, 1.0)

        assert recent_score > old_score

    def test_half_life(self):
        """Score halves at half-life."""
        item = make_item("1", ContextSource.OBSIDIAN, "Test", "content", hours_ago=168)
        score = time_decay_score(item, 1.0, half_life_hours=168)
        assert 0.45 < score < 0.55  # Should be ~0.5


class TestEntityExtraction:
    """Tests for entity extraction."""

    def test_extracts_technologies(self):
        """Extracts known technology terms."""
        text = "Using Python with FastAPI and PostgreSQL for the backend."
        entities = extract_entities_from_text(text)

        assert "technology" in entities
        assert "python" in entities["technology"]
        assert "fastapi" in entities["technology"]
        assert "postgresql" in entities["technology"]

    def test_extracts_projects(self):
        """Extracts project-like names."""
        text = "The PersonalContextLayer project uses knowledge-engine."
        entities = extract_entities_from_text(text)

        assert "project" in entities
        assert "PersonalContextLayer" in entities["project"]
        assert "knowledge-engine" in entities["project"]

    def test_find_mentions(self):
        """Finds items mentioning entity."""
        items = [
            make_item("1", ContextSource.OBSIDIAN, "OAuth Guide", "oauth authentication"),
            make_item("2", ContextSource.GIT, "Add feature", "new feature"),
            make_item("3", ContextSource.KAS, "OAuth KB", "OAuth 2.0 implementation"),
        ]
        mentions = find_entity_mentions("oauth", items)

        assert len(mentions) == 2
        ids = [m.id for m in mentions]
        assert "1" in ids
        assert "3" in ids


class TestRelevanceScoring:
    """Tests for relevance scoring."""

    def test_query_boost(self):
        """Query match boosts score."""
        item = make_item("1", ContextSource.OBSIDIAN, "OAuth Guide", "oauth implementation")
        boost = compute_query_boost(item, "oauth")
        assert boost > 0

    def test_source_weights(self):
        """Different sources have different weights."""
        obsidian = make_item("1", ContextSource.OBSIDIAN, "Note", "content", score=1.0)
        git = make_item("2", ContextSource.GIT, "Commit", "content", score=1.0)

        obs_score = compute_relevance_score(obsidian)
        git_score = compute_relevance_score(git)

        # Obsidian should score higher with default weights
        assert obs_score > git_score

    def test_interleave_sources(self):
        """Interleaving provides source diversity."""
        items = [
            make_item("obs1", ContextSource.OBSIDIAN, "N1", "c", score=0.9),
            make_item("obs2", ContextSource.OBSIDIAN, "N2", "c", score=0.8),
            make_item("obs3", ContextSource.OBSIDIAN, "N3", "c", score=0.7),
            make_item("git1", ContextSource.GIT, "C1", "c", score=0.85),
            make_item("git2", ContextSource.GIT, "C2", "c", score=0.75),
        ]
        interleaved = interleave_sources(items, max_per_source=2)

        # Should have items from both sources in top results
        sources = [i.source for i in interleaved[:4]]
        assert ContextSource.OBSIDIAN in sources
        assert ContextSource.GIT in sources
