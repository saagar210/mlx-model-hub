"""FSRS (Free Spaced Repetition Scheduler) integration.

FSRS is a modern spaced repetition algorithm that outperforms SuperMemo and Anki's
default algorithms. It uses a neural network-derived formula to predict optimal
review times based on:
- Difficulty of the item
- Stability (how well-learned)
- Retrievability (probability of recall)

Reference: https://github.com/open-spaced-repetition/fsrs4anki
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class ReviewRating(int, Enum):
    """User rating for a review.

    Maps to FSRS grades:
    - AGAIN (1): Complete failure, need to see again soon
    - HARD (2): Significant difficulty, shorter interval
    - GOOD (3): Correct with some effort, normal interval
    - EASY (4): Effortless recall, longer interval
    """

    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


class ReviewState(str, Enum):
    """Card learning state in FSRS."""

    NEW = "new"  # Never reviewed
    LEARNING = "learning"  # In initial learning phase
    REVIEW = "review"  # Graduated to regular reviews
    RELEARNING = "relearning"  # Failed review, back to learning


@dataclass
class FSRSParameters:
    """FSRS algorithm parameters.

    These are the default parameters from FSRS-4.5.
    They can be personalized per-user with enough review data.
    """

    # Weights for the neural network formula
    w: list[float] = field(default_factory=lambda: [
        0.4, 0.6, 2.4, 5.8,  # Initial stability by rating
        4.93, 0.94, 0.86, 0.01,  # Difficulty factors
        1.49, 0.14, 0.94,  # Stability factors
        2.18, 0.05, 0.34, 1.26,  # Retrievability factors
        0.29, 2.61,  # Additional factors
    ])

    # Target retention probability (0.9 = 90%)
    request_retention: float = 0.9

    # Maximum interval in days
    maximum_interval: int = 365 * 2  # 2 years

    # Easy bonus multiplier
    easy_bonus: float = 1.3

    # Hard interval multiplier
    hard_interval: float = 1.2


@dataclass
class ReviewCard:
    """A review card with FSRS scheduling data.

    Represents a single item to be reviewed, typically generated
    from a document chunk, memory, or entity.
    """

    id: UUID = field(default_factory=uuid4)

    # Content
    front: str = ""  # Question/prompt
    back: str = ""  # Answer/content
    context: str = ""  # Additional context shown after answer

    # Source reference
    source_type: str = "chunk"  # chunk, memory, entity
    source_id: str = ""  # Reference to source
    document_id: str | None = None
    namespace: str = "default"

    # FSRS state
    state: ReviewState = ReviewState.NEW
    difficulty: float = 0.3  # Initial difficulty (0-1)
    stability: float = 0.0  # How well-learned (days until 90% retention drops to 50%)
    retrievability: float = 1.0  # Current recall probability

    # Scheduling
    due: datetime = field(default_factory=_utc_now)
    last_review: datetime | None = None
    scheduled_days: int = 0
    elapsed_days: int = 0

    # Stats
    reps: int = 0  # Total reviews
    lapses: int = 0  # Times forgotten (rated AGAIN after graduating)
    streak: int = 0  # Current success streak

    # Metadata
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    suspended: bool = False  # Temporarily exclude from reviews

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "front": self.front,
            "back": self.back,
            "context": self.context,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "document_id": self.document_id,
            "namespace": self.namespace,
            "state": self.state.value,
            "difficulty": self.difficulty,
            "stability": self.stability,
            "retrievability": self.retrievability,
            "due": self.due.isoformat(),
            "last_review": self.last_review.isoformat() if self.last_review else None,
            "scheduled_days": self.scheduled_days,
            "elapsed_days": self.elapsed_days,
            "reps": self.reps,
            "lapses": self.lapses,
            "streak": self.streak,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "suspended": self.suspended,
        }


class FSRSScheduler:
    """FSRS algorithm implementation for scheduling reviews.

    This implements the core FSRS-4.5 algorithm for optimal
    spaced repetition scheduling.
    """

    def __init__(self, params: FSRSParameters | None = None) -> None:
        """Initialize scheduler with parameters.

        Args:
            params: FSRS parameters (uses defaults if not provided)
        """
        self.params = params or FSRSParameters()

    def schedule(
        self,
        card: ReviewCard,
        rating: ReviewRating,
        review_time: datetime | None = None,
    ) -> ReviewCard:
        """Schedule next review based on rating.

        Args:
            card: The card being reviewed
            rating: User's rating of recall quality
            review_time: Time of review (defaults to now)

        Returns:
            Updated card with new scheduling data
        """
        now = review_time or _utc_now()

        # Calculate elapsed days since last review
        if card.last_review:
            elapsed = (now - card.last_review).total_seconds() / 86400
            card.elapsed_days = max(0, int(elapsed))
        else:
            card.elapsed_days = 0

        # Update based on current state
        if card.state == ReviewState.NEW:
            card = self._schedule_new(card, rating, now)
        elif card.state == ReviewState.LEARNING:
            card = self._schedule_learning(card, rating, now)
        elif card.state == ReviewState.RELEARNING:
            card = self._schedule_relearning(card, rating, now)
        else:  # REVIEW
            card = self._schedule_review(card, rating, now)

        # Update common fields
        card.last_review = now
        card.updated_at = now
        card.reps += 1

        # Update streak
        if rating == ReviewRating.AGAIN:
            card.streak = 0
        else:
            card.streak += 1

        return card

    def _schedule_new(
        self,
        card: ReviewCard,
        rating: ReviewRating,
        now: datetime,
    ) -> ReviewCard:
        """Schedule a new card."""
        # Initialize stability based on first rating
        w = self.params.w
        card.stability = w[rating.value - 1]

        # Initialize difficulty
        card.difficulty = self._init_difficulty(rating)

        if rating == ReviewRating.AGAIN:
            card.state = ReviewState.LEARNING
            card.due = now + timedelta(minutes=1)
            card.scheduled_days = 0
        elif rating == ReviewRating.HARD:
            card.state = ReviewState.LEARNING
            card.due = now + timedelta(minutes=5)
            card.scheduled_days = 0
        elif rating == ReviewRating.GOOD:
            card.state = ReviewState.LEARNING
            card.due = now + timedelta(minutes=10)
            card.scheduled_days = 0
        else:  # EASY
            card.state = ReviewState.REVIEW
            interval = self._next_interval(card.stability)
            card.due = now + timedelta(days=interval)
            card.scheduled_days = interval

        return card

    def _schedule_learning(
        self,
        card: ReviewCard,
        rating: ReviewRating,
        now: datetime,
    ) -> ReviewCard:
        """Schedule a card in learning phase."""
        if rating == ReviewRating.AGAIN:
            card.due = now + timedelta(minutes=1)
            card.scheduled_days = 0
        elif rating == ReviewRating.HARD:
            card.due = now + timedelta(minutes=5)
            card.scheduled_days = 0
        elif rating == ReviewRating.GOOD:
            # Graduate to review
            card.state = ReviewState.REVIEW
            card.stability = self._next_stability(card, rating)
            interval = self._next_interval(card.stability)
            card.due = now + timedelta(days=interval)
            card.scheduled_days = interval
        else:  # EASY
            card.state = ReviewState.REVIEW
            card.stability = self._next_stability(card, rating)
            interval = int(
                self._next_interval(card.stability) * self.params.easy_bonus
            )
            card.due = now + timedelta(days=interval)
            card.scheduled_days = interval

        return card

    def _schedule_relearning(
        self,
        card: ReviewCard,
        rating: ReviewRating,
        now: datetime,
    ) -> ReviewCard:
        """Schedule a card in relearning phase."""
        if rating == ReviewRating.AGAIN:
            card.due = now + timedelta(minutes=1)
            card.scheduled_days = 0
        elif rating == ReviewRating.HARD:
            card.due = now + timedelta(minutes=5)
            card.scheduled_days = 0
        else:  # GOOD or EASY
            # Return to review
            card.state = ReviewState.REVIEW
            card.stability = self._next_stability(card, rating)
            interval = self._next_interval(card.stability)
            if rating == ReviewRating.EASY:
                interval = int(interval * self.params.easy_bonus)
            card.due = now + timedelta(days=interval)
            card.scheduled_days = interval

        return card

    def _schedule_review(
        self,
        card: ReviewCard,
        rating: ReviewRating,
        now: datetime,
    ) -> ReviewCard:
        """Schedule a card in review phase."""
        if rating == ReviewRating.AGAIN:
            # Lapse - back to relearning
            card.state = ReviewState.RELEARNING
            card.lapses += 1
            card.stability = max(0.1, card.stability * 0.2)  # Reset stability
            card.due = now + timedelta(minutes=1)
            card.scheduled_days = 0
        else:
            # Update difficulty and stability
            card.difficulty = self._next_difficulty(card.difficulty, rating)
            card.stability = self._next_stability(card, rating)

            # Calculate next interval
            interval = self._next_interval(card.stability)

            if rating == ReviewRating.HARD:
                interval = int(interval * self.params.hard_interval)
            elif rating == ReviewRating.EASY:
                interval = int(interval * self.params.easy_bonus)

            # Cap at maximum interval
            interval = min(interval, self.params.maximum_interval)

            card.due = now + timedelta(days=interval)
            card.scheduled_days = interval

        return card

    def _init_difficulty(self, rating: ReviewRating) -> float:
        """Initialize difficulty based on first rating."""
        # Difficulty ranges from 0 (easiest) to 1 (hardest)
        difficulty_map = {
            ReviewRating.AGAIN: 0.7,
            ReviewRating.HARD: 0.5,
            ReviewRating.GOOD: 0.3,
            ReviewRating.EASY: 0.1,
        }
        return difficulty_map[rating]

    def _next_difficulty(self, current: float, rating: ReviewRating) -> float:
        """Calculate next difficulty based on rating."""
        w = self.params.w

        # Difficulty adjustment based on rating
        delta = {
            ReviewRating.AGAIN: 0.1,
            ReviewRating.HARD: 0.05,
            ReviewRating.GOOD: -0.05,
            ReviewRating.EASY: -0.1,
        }[rating]

        new_diff = current + delta * w[7]
        return max(0.01, min(1.0, new_diff))  # Clamp to [0.01, 1.0]

    def _next_stability(self, card: ReviewCard, rating: ReviewRating) -> float:
        """Calculate next stability using FSRS formula."""
        w = self.params.w
        d = card.difficulty
        s = card.stability
        r = card.retrievability

        # FSRS stability formula
        if rating == ReviewRating.AGAIN:
            # Stability after forgetting
            new_s = w[11] * pow(d, -w[12]) * (pow(s + 1, w[13]) - 1) * pow(r, w[14])
        else:
            # Stability after successful recall
            hard_penalty = w[15] if rating == ReviewRating.HARD else 1
            easy_bonus = w[16] if rating == ReviewRating.EASY else 1

            new_s = s * (
                1
                + pow(w[8], 1) * 11 * pow(d, -w[9]) * (pow(s, -w[10]) - 1)
                * hard_penalty
                * easy_bonus
            )

        return max(0.1, new_s)

    def _next_interval(self, stability: float) -> int:
        """Calculate interval from stability using FSRS formula."""
        # Interval = stability * factor to achieve target retention
        # Using the formula: R = exp(ln(0.9) * t / S)
        # Solving for t when R = request_retention
        import math

        r = self.params.request_retention
        interval = stability * math.log(r) / math.log(0.9)
        return max(1, int(round(interval)))

    def get_retrievability(self, card: ReviewCard, now: datetime | None = None) -> float:
        """Calculate current retrievability (recall probability).

        Args:
            card: The card to check
            now: Current time (defaults to now)

        Returns:
            Probability of successful recall (0-1)
        """
        import math

        now = now or _utc_now()

        if card.last_review is None:
            return 1.0 if card.state == ReviewState.NEW else 0.5

        # Days since last review
        elapsed = (now - card.last_review).total_seconds() / 86400

        # FSRS retrievability formula: R = exp(ln(0.9) * t / S)
        if card.stability <= 0:
            return 0.0

        retrievability = math.exp(math.log(0.9) * elapsed / card.stability)
        return max(0.0, min(1.0, retrievability))


class ReviewSession(BaseModel):
    """A review session containing cards due for review."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: str = "default"
    namespace: str = "default"
    cards: list[dict[str, Any]] = Field(default_factory=list)
    total_cards: int = 0
    reviewed_count: int = 0
    started_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime | None = None

    @property
    def is_complete(self) -> bool:
        """Check if session is complete."""
        return self.reviewed_count >= self.total_cards

    @property
    def remaining(self) -> int:
        """Number of cards remaining."""
        return max(0, self.total_cards - self.reviewed_count)

    @property
    def progress_percent(self) -> float:
        """Progress as percentage."""
        if self.total_cards == 0:
            return 100.0
        return (self.reviewed_count / self.total_cards) * 100
