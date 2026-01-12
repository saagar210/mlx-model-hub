"""Pydantic models for FSRS spaced repetition system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from fsrs import State
from pydantic import BaseModel, Field


class ReviewRating(str, Enum):
    """User rating for a review."""

    AGAIN = "again"  # Complete failure to recall (1)
    HARD = "hard"  # Recalled with difficulty (2)
    GOOD = "good"  # Recalled with some effort (3)
    EASY = "easy"  # Recalled effortlessly (4)

    @classmethod
    def from_int(cls, value: int) -> "ReviewRating":
        """Convert integer rating (1-4) to ReviewRating."""
        mapping = {
            1: cls.AGAIN,
            2: cls.HARD,
            3: cls.GOOD,
            4: cls.EASY,
        }
        if value not in mapping:
            raise ValueError(f"Invalid rating value: {value}. Must be 1-4.")
        return mapping[value]


@dataclass
class FSRSState:
    """FSRS card state for storage and retrieval."""

    state: int  # 0=New, 1=Learning, 2=Review, 3=Relearning
    stability: float
    difficulty: float
    due: datetime
    last_review: datetime | None = None
    reps: int = 0
    lapses: int = 0
    step: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FSRSState":
        """Create FSRSState from dictionary."""
        due = data.get("due")
        if isinstance(due, str):
            due = datetime.fromisoformat(due.replace("Z", "+00:00"))

        last_review = data.get("last_review")
        if isinstance(last_review, str):
            last_review = datetime.fromisoformat(last_review.replace("Z", "+00:00"))

        return cls(
            state=data.get("state", 0),
            stability=data.get("stability", 0.0),
            difficulty=data.get("difficulty", 0.0),
            due=due or datetime.now(UTC),
            last_review=last_review,
            reps=data.get("reps", 0),
            lapses=data.get("lapses", 0),
            step=data.get("step"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "state": self.state,
            "stability": self.stability,
            "difficulty": self.difficulty,
            "due": self.due.isoformat() if self.due else None,
            "last_review": self.last_review.isoformat() if self.last_review else None,
            "reps": self.reps,
            "lapses": self.lapses,
            "step": self.step,
        }


@dataclass
class ReviewItem:
    """An item in the review queue."""

    content_id: UUID
    title: str
    content_type: str
    preview_text: str
    state: State
    due: datetime
    stability: float
    difficulty: float
    step: int | None
    last_review: datetime | None
    reps: int = 0
    lapses: int = 0

    @property
    def is_new(self) -> bool:
        """Check if item has never been reviewed (still in initial learning)."""
        return self.state == State.Learning and self.step == 0

    @property
    def is_learning(self) -> bool:
        """Check if item is in learning phase."""
        return self.state == State.Learning or self.state == State.Relearning

    @property
    def is_review(self) -> bool:
        """Check if item is in review phase."""
        return self.state == State.Review


@dataclass
class ReviewResult:
    """Result of processing a review."""

    content_id: UUID
    rating: ReviewRating
    old_state: State
    new_state: State
    old_due: datetime
    new_due: datetime
    review_time: datetime = field(default_factory=lambda: datetime.now(UTC))


class ReviewSession(BaseModel):
    """Model for an active review session."""

    session_id: str = Field(..., description="Unique session identifier")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    items_total: int = Field(0, description="Total items to review")
    items_reviewed: int = Field(0, description="Items reviewed so far")
    items_remaining: int = Field(0, description="Items remaining")
    ratings_breakdown: dict[str, int] = Field(
        default_factory=lambda: {"again": 0, "hard": 0, "good": 0, "easy": 0},
        description="Count of each rating given",
    )

    @property
    def completion_percentage(self) -> float:
        """Calculate session completion percentage."""
        if self.items_total == 0:
            return 0.0
        return (self.items_reviewed / self.items_total) * 100


class ReviewStats(BaseModel):
    """Statistics about the review queue."""

    total_active: int = Field(0, description="Total active items in queue")
    due_now: int = Field(0, description="Items currently due")
    new_count: int = Field(0, description="New items never reviewed")
    learning_count: int = Field(0, description="Items in learning phase")
    review_count: int = Field(0, description="Items in review phase")
    suspended_count: int = Field(0, description="Suspended items")
    average_stability: float | None = Field(None, description="Average stability")
    average_difficulty: float | None = Field(None, description="Average difficulty")
    retention_rate: float | None = Field(None, description="Estimated retention rate")
    reviews_today: int = Field(0, description="Reviews completed today")
    streak_days: int = Field(0, description="Consecutive days of review")


class NextIntervals(BaseModel):
    """Preview of next intervals for each rating option."""

    again: datetime
    hard: datetime
    good: datetime
    easy: datetime

    @classmethod
    def from_dict(cls, intervals: dict[ReviewRating, datetime]) -> "NextIntervals":
        """Create from dictionary mapping."""
        return cls(
            again=intervals[ReviewRating.AGAIN],
            hard=intervals[ReviewRating.HARD],
            good=intervals[ReviewRating.GOOD],
            easy=intervals[ReviewRating.EASY],
        )
