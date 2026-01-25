"""Tests for intent router."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from universal_context_engine.router.classifier import (
    Intent,
    IntentClassifier,
    IntentType,
    classify_intent,
    INTENT_PATTERNS,
)


class TestIntentClassifier:
    """Test intent classification."""

    def test_pattern_match_research(self):
        """Research patterns should be classified correctly."""
        classifier = IntentClassifier()

        for query in ["research how GraphRAG works", "learn about OAuth", "explain embeddings"]:
            intent = classifier.classify_by_patterns(query)
            assert intent is not None
            assert intent.type == IntentType.RESEARCH
            assert intent.confidence >= 0.8

    def test_pattern_match_recall(self):
        """Recall patterns should be classified correctly."""
        classifier = IntentClassifier()

        for query in ["what was i working on", "yesterday's progress", "last session"]:
            intent = classifier.classify_by_patterns(query)
            assert intent is not None
            assert intent.type == IntentType.RECALL
            assert intent.confidence >= 0.8

    def test_pattern_match_knowledge(self):
        """Knowledge search patterns should be classified correctly."""
        classifier = IntentClassifier()

        for query in ["search for authentication", "find docs on caching", "how to deploy"]:
            intent = classifier.classify_by_patterns(query)
            assert intent is not None
            assert intent.type == IntentType.KNOWLEDGE
            assert intent.confidence >= 0.8

    def test_pattern_match_decompose(self):
        """Task decomposition patterns should be classified correctly."""
        classifier = IntentClassifier()

        for query in ["break down the login feature", "plan the deployment", "steps to implement auth"]:
            intent = classifier.classify_by_patterns(query)
            assert intent is not None
            assert intent.type == IntentType.DECOMPOSE
            assert intent.confidence >= 0.8

    def test_pattern_match_debug(self):
        """Debug patterns should be classified correctly."""
        classifier = IntentClassifier()

        for query in ["error in the auth module", "fix the bug", "not working properly"]:
            intent = classifier.classify_by_patterns(query)
            assert intent is not None
            assert intent.type == IntentType.DEBUG
            assert intent.confidence >= 0.8

    def test_pattern_match_save(self):
        """Save patterns should be classified correctly."""
        classifier = IntentClassifier()

        for query in ["remember this decision", "save the context", "note this pattern"]:
            intent = classifier.classify_by_patterns(query)
            assert intent is not None
            assert intent.type == IntentType.SAVE
            assert intent.confidence >= 0.8

    def test_no_pattern_match_returns_none(self):
        """Unrecognized patterns should return None."""
        classifier = IntentClassifier()
        intent = classifier.classify_by_patterns("completely random gibberish xyz123")
        assert intent is None

    def test_topic_extraction(self):
        """Topics should be extracted from patterns."""
        classifier = IntentClassifier()

        intent = classifier.classify_by_patterns("research about GraphRAG implementation")
        assert intent is not None
        assert intent.extracted_topic is not None
        assert "GraphRAG" in intent.extracted_topic

    def test_topic_cleans_common_prefixes(self):
        """Topic extraction should clean common prefixes."""
        classifier = IntentClassifier()

        intent = classifier.classify_by_patterns("learn about the OAuth protocol")
        assert intent is not None
        # "the" should be stripped from the topic
        assert intent.extracted_topic
        assert not intent.extracted_topic.lower().startswith("the ")

    @pytest.mark.asyncio
    async def test_classify_uses_pattern_first(self):
        """classify() should use pattern matching before LLM."""
        classifier = IntentClassifier()
        classifier._generate_client = MagicMock()

        intent = await classifier.classify("research GraphRAG")

        # Should use pattern match, not call LLM
        classifier._generate_client.generate.assert_not_called()
        assert intent.type == IntentType.RESEARCH

    @pytest.mark.asyncio
    async def test_classify_falls_back_to_llm(self):
        """classify() should fall back to LLM for ambiguous cases."""
        classifier = IntentClassifier()
        classifier._generate_client = AsyncMock()
        classifier._generate_client.generate.return_value = '{"intent": "KNOWLEDGE", "confidence": 0.7}'

        intent = await classifier.classify("xyz random query that matches nothing")

        classifier._generate_client.generate.assert_called_once()
        assert intent.type == IntentType.KNOWLEDGE

    @pytest.mark.asyncio
    async def test_classify_llm_failure_returns_unknown(self):
        """LLM failure should return UNKNOWN intent."""
        classifier = IntentClassifier()
        classifier._generate_client = AsyncMock()
        classifier._generate_client.generate.side_effect = Exception("LLM error")

        intent = await classifier.classify("xyz random query")

        assert intent.type == IntentType.UNKNOWN
        assert intent.confidence < 0.5


@pytest.mark.asyncio
async def test_classify_intent_function():
    """Test the module-level classify_intent function."""
    intent = await classify_intent("research how to implement caching")
    assert intent.type == IntentType.RESEARCH
    assert intent.confidence >= 0.8


class TestIntentPatterns:
    """Test pattern definitions."""

    def test_all_intent_types_have_patterns(self):
        """Every intent type (except UNKNOWN) should have patterns."""
        for intent_type in IntentType:
            if intent_type != IntentType.UNKNOWN:
                assert intent_type in INTENT_PATTERNS
                assert len(INTENT_PATTERNS[intent_type]) > 0

    def test_patterns_are_lowercase(self):
        """All patterns should be lowercase for case-insensitive matching."""
        for patterns in INTENT_PATTERNS.values():
            for pattern in patterns:
                assert pattern == pattern.lower()
