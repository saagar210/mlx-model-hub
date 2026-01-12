"""Core FSRS integration for spaced repetition."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fsrs import Card, Rating, Scheduler, State

from knowledge.review.models import NextIntervals, ReviewRating, ReviewResult

logger = logging.getLogger(__name__)


# Map our rating to FSRS Rating
RATING_MAP: dict[ReviewRating, Rating] = {
    ReviewRating.AGAIN: Rating.Again,
    ReviewRating.HARD: Rating.Hard,
    ReviewRating.GOOD: Rating.Good,
    ReviewRating.EASY: Rating.Easy,
}


def create_fsrs_card() -> dict[str, Any]:
    """
    Create a new FSRS card state.

    Returns:
        Dictionary with FSRS card state ready for database storage.
    """
    card = Card()
    return card.to_dict()


def dict_to_card(data: dict[str, Any]) -> Card:
    """Convert dictionary to FSRS Card."""
    return Card.from_dict(data)


def card_to_dict(card: Card) -> dict[str, Any]:
    """Convert FSRS Card to dictionary for storage."""
    return card.to_dict()


def validate_fsrs_state(state_data: dict[str, Any] | None) -> tuple[bool, str]:
    """
    Validate FSRS state data structure.

    Args:
        state_data: Dictionary containing FSRS card state

    Returns:
        Tuple of (is_valid, error_message)
    """
    if state_data is None:
        return False, "FSRS state is None"

    if not isinstance(state_data, dict):
        return False, f"FSRS state must be dict, got {type(state_data).__name__}"

    # Required field - state must be present
    if "state" not in state_data:
        return False, "FSRS state missing 'state' field"

    # Validate state is a valid integer (0-3)
    # Note: FSRS states: 0=New (unused), 1=Learning, 2=Review, 3=Relearning
    state_value = state_data.get("state")
    if not isinstance(state_value, int) or state_value < 0 or state_value > 3:
        return False, f"Invalid FSRS state value: {state_value} (must be 0-3)"

    # Validate stability if present (can be None for new cards)
    stability = state_data.get("stability")
    if stability is not None:
        if not isinstance(stability, (int, float)) or stability < 0:
            return False, f"Invalid stability: {stability}"

    # Validate difficulty if present (can be None for new cards)
    difficulty = state_data.get("difficulty")
    if difficulty is not None:
        if not isinstance(difficulty, (int, float)) or difficulty < 0 or difficulty > 10:
            return False, f"Invalid difficulty: {difficulty} (must be 0-10)"

    return True, ""


def parse_fsrs_state_safe(fsrs_state_json: dict[str, Any] | None) -> tuple[State, dict[str, Any]]:
    """
    Safely parse FSRS state with validation.

    Returns:
        Tuple of (State enum, state_dict). Uses defaults if invalid.
    """
    if not fsrs_state_json:
        logger.debug("Empty FSRS state, using default new card")
        return State.Learning, create_fsrs_card()

    is_valid, error = validate_fsrs_state(fsrs_state_json)
    if not is_valid:
        logger.warning(f"Invalid FSRS state, using default: {error}")
        return State.Learning, create_fsrs_card()

    try:
        state = State(fsrs_state_json["state"])
        return state, fsrs_state_json
    except (ValueError, KeyError) as e:
        logger.warning(f"Failed to parse FSRS state: {e}")
        return State.Learning, create_fsrs_card()


class ReviewEngine:
    """
    FSRS-based review engine.

    This engine wraps the py-fsrs library to provide spaced repetition
    functionality with optimal parameters for knowledge retention.

    FSRS (Free Spaced Repetition Scheduler) is an algorithm that:
    - Tracks stability (how well you know something)
    - Tracks difficulty (how hard the item is for you)
    - Optimizes review intervals for 90% retention by default
    """

    def __init__(self, desired_retention: float = 0.9):
        """
        Initialize the review engine.

        Args:
            desired_retention: Target retention rate (0.0-1.0). Default 0.9 (90%).
        """
        self._scheduler = Scheduler(desired_retention=desired_retention)
        self._desired_retention = desired_retention

    @property
    def desired_retention(self) -> float:
        """Get the configured desired retention rate."""
        return self._desired_retention

    def process_review(
        self,
        card_state: dict[str, Any],
        rating: ReviewRating,
        review_time: datetime | None = None,
    ) -> tuple[dict[str, Any], ReviewResult]:
        """
        Process a review and update card state.

        Args:
            card_state: Current FSRS card state dictionary
            rating: User's rating
            review_time: When the review occurred (defaults to now)

        Returns:
            Tuple of (new_card_state, ReviewResult)
        """
        review_time = review_time or datetime.now(UTC)
        card = dict_to_card(card_state)
        fsrs_rating = RATING_MAP[rating]

        # Save old state for result
        old_state = card.state
        old_due = card.due

        # Process review
        new_card, _review_log = self._scheduler.review_card(
            card, fsrs_rating, review_datetime=review_time
        )

        # Create result
        result = ReviewResult(
            content_id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder, set by caller
            rating=rating,
            old_state=old_state,
            new_state=new_card.state,
            old_due=old_due,
            new_due=new_card.due,
            review_time=review_time,
        )

        return card_to_dict(new_card), result

    def get_next_intervals(
        self,
        card_state: dict[str, Any],
        review_time: datetime | None = None,
    ) -> dict[ReviewRating, datetime]:
        """
        Get the next due dates for each possible rating.

        Args:
            card_state: Current FSRS card state
            review_time: When the review would occur

        Returns:
            Dictionary mapping rating to next due date
        """
        review_time = review_time or datetime.now(UTC)
        card = dict_to_card(card_state)

        intervals: dict[ReviewRating, datetime] = {}
        for our_rating, fsrs_rating in RATING_MAP.items():
            # Create a copy and review it
            test_card = Card.from_dict(card.to_dict())
            reviewed_card, _ = self._scheduler.review_card(
                test_card, fsrs_rating, review_datetime=review_time
            )
            intervals[our_rating] = reviewed_card.due

        return intervals

    def get_next_intervals_model(
        self,
        card_state: dict[str, Any],
        review_time: datetime | None = None,
    ) -> NextIntervals:
        """
        Get the next intervals as a Pydantic model.

        Args:
            card_state: Current FSRS card state
            review_time: When the review would occur

        Returns:
            NextIntervals model with due dates for each rating
        """
        intervals = self.get_next_intervals(card_state, review_time)
        return NextIntervals.from_dict(intervals)

    def calculate_retention(self, card_state: dict[str, Any]) -> float | None:
        """
        Calculate the current estimated retention probability.

        Args:
            card_state: FSRS card state

        Returns:
            Retention probability (0.0-1.0) or None if cannot calculate
        """
        try:
            stability = card_state.get("stability", 0)
            if stability <= 0:
                return None

            # FSRS retention formula: R = e^(-t/S)
            # where t = days since last review, S = stability
            due_str = card_state.get("due")
            last_review_str = card_state.get("last_review")

            if not due_str:
                return None

            from datetime import timedelta
            import math

            now = datetime.now(UTC)

            # Parse due date
            if isinstance(due_str, str):
                due = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
            else:
                due = due_str

            # Calculate days elapsed since scheduling
            # If due is in the future, retention is at target
            if due > now:
                return self._desired_retention

            # Calculate actual retention based on overdue time
            days_overdue = (now - due).total_seconds() / 86400
            retention = math.exp(-days_overdue / stability)

            return max(0.0, min(1.0, retention))

        except Exception as e:
            logger.warning(f"Failed to calculate retention: {e}")
            return None


# Global engine instance
_engine: ReviewEngine | None = None


def get_review_engine(desired_retention: float = 0.9) -> ReviewEngine:
    """
    Get or create the global review engine.

    Args:
        desired_retention: Target retention rate (only used on first call)

    Returns:
        Singleton ReviewEngine instance
    """
    global _engine
    if _engine is None:
        _engine = ReviewEngine(desired_retention=desired_retention)
    return _engine


def reset_review_engine() -> None:
    """Reset the global review engine (useful for testing)."""
    global _engine
    _engine = None
