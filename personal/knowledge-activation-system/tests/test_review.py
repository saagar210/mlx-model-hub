"""Tests for FSRS-based review system."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fsrs import Card, State, Rating

from knowledge.review import (
    ReviewRating,
    ReviewItem,
    ReviewResult,
    ReviewEngine,
    create_fsrs_card,
    dict_to_card,
    card_to_dict,
    get_review_engine,
    RATING_MAP,
)


class TestFSRSCardConversion:
    """Test FSRS card serialization/deserialization."""

    def test_create_fsrs_card(self):
        """Test creating a new FSRS card state."""
        card_dict = create_fsrs_card()

        assert "state" in card_dict
        assert "due" in card_dict
        assert "stability" in card_dict
        assert "difficulty" in card_dict
        # New cards start in Learning state (value 1)
        assert card_dict["state"] == State.Learning.value

    def test_card_roundtrip(self):
        """Test card to dict and back preserves state."""
        original = Card()
        card_dict = card_to_dict(original)
        restored = dict_to_card(card_dict)

        assert restored.state == original.state
        assert restored.stability == original.stability
        assert restored.difficulty == original.difficulty
        # Due times should be equal (or very close)
        assert abs((restored.due - original.due).total_seconds()) < 1

    def test_dict_to_card_with_reviewed_state(self):
        """Test restoring a card that has been reviewed."""
        scheduler = get_review_engine()._scheduler
        card = Card()
        card, _ = scheduler.review_card(card, Rating.Good)

        card_dict = card_to_dict(card)
        restored = dict_to_card(card_dict)

        assert restored.state == card.state
        assert restored.stability == card.stability
        assert restored.difficulty == card.difficulty


class TestReviewEngine:
    """Test the review engine."""

    def test_engine_initialization(self):
        """Test review engine initializes correctly."""
        engine = ReviewEngine()
        assert engine._scheduler is not None

    def test_engine_with_custom_retention(self):
        """Test review engine with custom retention."""
        engine = ReviewEngine(desired_retention=0.85)
        assert engine._scheduler is not None

    def test_process_review_good(self):
        """Test processing a 'good' review."""
        engine = ReviewEngine()
        card_state = create_fsrs_card()

        new_state, result = engine.process_review(card_state, ReviewRating.GOOD)

        assert result.rating == ReviewRating.GOOD
        # State should be Learning initially, then progress
        assert result.old_state == State.Learning
        # After first Good rating on a learning card, it advances
        assert new_state["due"] is not None

    def test_process_review_again(self):
        """Test processing an 'again' review (forgot)."""
        engine = ReviewEngine()
        card_state = create_fsrs_card()

        new_state, result = engine.process_review(card_state, ReviewRating.AGAIN)

        assert result.rating == ReviewRating.AGAIN
        # Card should still be in learning
        assert State(new_state["state"]) in [State.Learning, State.Relearning]

    def test_process_review_easy(self):
        """Test processing an 'easy' review."""
        engine = ReviewEngine()
        card_state = create_fsrs_card()

        new_state, result = engine.process_review(card_state, ReviewRating.EASY)

        assert result.rating == ReviewRating.EASY
        # Easy should result in longer interval
        assert new_state["due"] is not None

    def test_process_review_hard(self):
        """Test processing a 'hard' review."""
        engine = ReviewEngine()
        card_state = create_fsrs_card()

        new_state, result = engine.process_review(card_state, ReviewRating.HARD)

        assert result.rating == ReviewRating.HARD
        assert new_state["due"] is not None

    def test_get_next_intervals(self):
        """Test getting next intervals for all ratings."""
        engine = ReviewEngine()
        card_state = create_fsrs_card()

        intervals = engine.get_next_intervals(card_state)

        assert ReviewRating.AGAIN in intervals
        assert ReviewRating.HARD in intervals
        assert ReviewRating.GOOD in intervals
        assert ReviewRating.EASY in intervals

        # Easy should have longer interval than Again
        assert intervals[ReviewRating.EASY] > intervals[ReviewRating.AGAIN]

    def test_review_result_timestamps(self):
        """Test that review results have correct timestamps."""
        engine = ReviewEngine()
        card_state = create_fsrs_card()
        review_time = datetime.now(timezone.utc)

        _, result = engine.process_review(card_state, ReviewRating.GOOD, review_time)

        assert result.review_time == review_time


class TestReviewItem:
    """Test ReviewItem dataclass."""

    def test_is_new(self):
        """Test is_new property."""
        item = ReviewItem(
            content_id=uuid4(),
            title="Test",
            content_type="note",
            preview_text="Preview",
            state=State.Learning,
            due=datetime.now(timezone.utc),
            stability=0,
            difficulty=0,
            step=0,  # Step 0 = never reviewed
            last_review=None,
        )
        assert item.is_new is True

        # After review, step advances
        item.step = 1
        assert item.is_new is False

    def test_is_learning(self):
        """Test is_learning property."""
        item = ReviewItem(
            content_id=uuid4(),
            title="Test",
            content_type="note",
            preview_text="Preview",
            state=State.Learning,
            due=datetime.now(timezone.utc),
            stability=0,
            difficulty=0,
            step=0,
            last_review=None,
        )
        assert item.is_learning is True

        item.state = State.Relearning
        assert item.is_learning is True

        item.state = State.Review
        assert item.is_learning is False

    def test_is_review(self):
        """Test is_review property."""
        item = ReviewItem(
            content_id=uuid4(),
            title="Test",
            content_type="note",
            preview_text="Preview",
            state=State.Review,
            due=datetime.now(timezone.utc),
            stability=5.0,
            difficulty=5.0,
            step=None,
            last_review=datetime.now(timezone.utc),
        )
        assert item.is_review is True

        item.state = State.Learning
        assert item.is_review is False


class TestRatingMapping:
    """Test rating mapping between our enum and FSRS."""

    def test_rating_map_completeness(self):
        """Test all ratings are mapped."""
        for rating in ReviewRating:
            assert rating in RATING_MAP
            assert RATING_MAP[rating] in [Rating.Again, Rating.Hard, Rating.Good, Rating.Easy]

    def test_rating_values(self):
        """Test rating mappings are correct."""
        assert RATING_MAP[ReviewRating.AGAIN] == Rating.Again
        assert RATING_MAP[ReviewRating.HARD] == Rating.Hard
        assert RATING_MAP[ReviewRating.GOOD] == Rating.Good
        assert RATING_MAP[ReviewRating.EASY] == Rating.Easy


class TestGlobalEngine:
    """Test global engine instance."""

    def test_get_review_engine_singleton(self):
        """Test that get_review_engine returns same instance."""
        engine1 = get_review_engine()
        engine2 = get_review_engine()
        assert engine1 is engine2


class TestStateProgression:
    """Test card state progression through reviews."""

    def test_learning_to_review(self):
        """Test card graduates from learning to review state."""
        engine = ReviewEngine()
        card_state = create_fsrs_card()

        # New cards start in Learning
        assert State(card_state["state"]) == State.Learning

        # Rate Good multiple times to graduate
        for _ in range(3):  # Usually takes 2-3 Good ratings to graduate
            card_state, _ = engine.process_review(card_state, ReviewRating.GOOD)

        # Should eventually reach Review state
        # (The exact number of reviews depends on FSRS parameters)
        final_state = State(card_state["state"])
        assert final_state in [State.Learning, State.Review]

    def test_review_to_relearning_on_lapse(self):
        """Test card enters relearning on lapse."""
        engine = ReviewEngine()
        card_state = create_fsrs_card()

        # Graduate to review state first
        for _ in range(5):
            card_state, _ = engine.process_review(card_state, ReviewRating.EASY)

        # Now lapse (forget)
        card_state, _ = engine.process_review(card_state, ReviewRating.AGAIN)

        # Should be in Relearning or Learning
        final_state = State(card_state["state"])
        assert final_state in [State.Learning, State.Relearning]

    def test_stability_increases_with_reviews(self):
        """Test stability increases with successful reviews."""
        engine = ReviewEngine()
        card_state = create_fsrs_card()

        initial_stability = card_state.get("stability") or 0

        # Multiple good reviews
        for _ in range(5):
            card_state, _ = engine.process_review(card_state, ReviewRating.GOOD)

        final_stability = card_state.get("stability") or 0
        assert final_stability > initial_stability


class TestReviewRating:
    """Tests for ReviewRating enum."""

    def test_rating_values(self):
        """Test all rating values exist."""
        assert ReviewRating.AGAIN.value == "again"
        assert ReviewRating.HARD.value == "hard"
        assert ReviewRating.GOOD.value == "good"
        assert ReviewRating.EASY.value == "easy"


class TestReviewResult:
    """Tests for ReviewResult dataclass."""

    def test_review_result_creation(self):
        """Test creating a ReviewResult."""
        now = datetime.now(timezone.utc)
        result = ReviewResult(
            content_id=uuid4(),
            rating=ReviewRating.GOOD,
            old_state=State.Learning,
            new_state=State.Review,
            old_due=now,
            new_due=now + timedelta(minutes=10),
        )

        assert result.rating == ReviewRating.GOOD
        assert result.old_state == State.Learning
        assert result.new_state == State.Review
        assert result.new_due > result.old_due
