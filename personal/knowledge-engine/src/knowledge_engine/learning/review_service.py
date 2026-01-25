"""Review service for managing spaced repetition sessions.

Provides high-level operations for:
- Getting due cards for review
- Processing review ratings
- Managing review sessions
- Tracking learning statistics
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from knowledge_engine.config import Settings, get_settings
from knowledge_engine.learning.card_generator import CardGenerator, CardType
from knowledge_engine.learning.fsrs_scheduler import (
    FSRSScheduler,
    ReviewCard,
    ReviewRating,
    ReviewSession,
    ReviewState,
)
from knowledge_engine.logging_config import get_logger

logger = get_logger(__name__)


def _utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


@dataclass
class ReviewStats:
    """Statistics for a user's learning progress."""

    total_cards: int = 0
    cards_reviewed_today: int = 0
    cards_due_today: int = 0
    cards_new: int = 0
    cards_learning: int = 0
    cards_review: int = 0
    average_retention: float = 0.0
    streak_days: int = 0
    total_reviews: int = 0
    total_time_minutes: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_cards": self.total_cards,
            "cards_reviewed_today": self.cards_reviewed_today,
            "cards_due_today": self.cards_due_today,
            "cards_new": self.cards_new,
            "cards_learning": self.cards_learning,
            "cards_review": self.cards_review,
            "average_retention": self.average_retention,
            "streak_days": self.streak_days,
            "total_reviews": self.total_reviews,
            "total_time_minutes": self.total_time_minutes,
        }


class ReviewService:
    """Service for managing spaced repetition reviews.

    This service coordinates:
    - Card storage and retrieval
    - FSRS scheduling
    - Session management
    - Statistics tracking

    Note: Currently uses in-memory storage. In production, this should
    be backed by PostgreSQL for persistence.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize review service.

        Args:
            settings: Application settings
        """
        self._settings = settings or get_settings()
        self._scheduler = FSRSScheduler()
        self._card_generator = CardGenerator()

        # In-memory storage (replace with database in production)
        self._cards: dict[str, ReviewCard] = {}  # card_id -> card
        self._sessions: dict[str, ReviewSession] = {}  # session_id -> session
        self._user_stats: dict[str, dict[str, Any]] = {}  # user_id -> stats

    # ============================================================
    # Card Management
    # ============================================================

    async def create_card(
        self,
        front: str,
        back: str,
        source_type: str = "manual",
        source_id: str = "",
        namespace: str = "default",
        tags: list[str] | None = None,
        context: str = "",
    ) -> ReviewCard:
        """Create a new review card.

        Args:
            front: Question/prompt
            back: Answer/content
            source_type: Source type (chunk, memory, entity, manual)
            source_id: Reference to source
            namespace: Card namespace
            tags: Tags for filtering
            context: Additional context

        Returns:
            Created review card
        """
        card = ReviewCard(
            id=uuid4(),
            front=front,
            back=back,
            context=context,
            source_type=source_type,
            source_id=source_id,
            namespace=namespace,
            state=ReviewState.NEW,
            tags=tags or [],
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )

        self._cards[str(card.id)] = card
        logger.info("Created review card: %s", card.id)

        return card

    async def get_card(self, card_id: str) -> ReviewCard | None:
        """Get a card by ID.

        Args:
            card_id: Card UUID

        Returns:
            Card if found, None otherwise
        """
        return self._cards.get(card_id)

    async def update_card(self, card: ReviewCard) -> ReviewCard:
        """Update a card.

        Args:
            card: Card with updated data

        Returns:
            Updated card
        """
        card.updated_at = _utc_now()
        self._cards[str(card.id)] = card
        return card

    async def delete_card(self, card_id: str) -> bool:
        """Delete a card.

        Args:
            card_id: Card UUID

        Returns:
            True if deleted, False if not found
        """
        if card_id in self._cards:
            del self._cards[card_id]
            return True
        return False

    async def suspend_card(self, card_id: str, suspend: bool = True) -> ReviewCard | None:
        """Suspend or unsuspend a card.

        Args:
            card_id: Card UUID
            suspend: Whether to suspend

        Returns:
            Updated card or None if not found
        """
        card = self._cards.get(card_id)
        if card:
            card.suspended = suspend
            card.updated_at = _utc_now()
            return card
        return None

    # ============================================================
    # Review Operations
    # ============================================================

    async def get_due_cards(
        self,
        namespace: str = "default",
        limit: int = 20,
        include_new: bool = True,
        new_limit: int = 10,
    ) -> list[ReviewCard]:
        """Get cards due for review.

        Args:
            namespace: Filter by namespace
            limit: Maximum cards to return
            include_new: Whether to include new cards
            new_limit: Maximum new cards to include

        Returns:
            List of due cards, ordered by priority
        """
        now = _utc_now()
        due_cards: list[ReviewCard] = []
        new_cards: list[ReviewCard] = []

        for card in self._cards.values():
            # Skip suspended cards
            if card.suspended:
                continue

            # Filter by namespace
            if card.namespace != namespace:
                continue

            # Check if due
            if card.state == ReviewState.NEW:
                if include_new:
                    new_cards.append(card)
            elif card.due <= now:
                # Update retrievability
                card.retrievability = self._scheduler.get_retrievability(card, now)
                due_cards.append(card)

        # Sort due cards by priority:
        # 1. Learning/relearning cards first (short intervals)
        # 2. Then by how overdue they are
        due_cards.sort(key=lambda c: (
            0 if c.state in (ReviewState.LEARNING, ReviewState.RELEARNING) else 1,
            c.due,
        ))

        # Limit due cards
        due_cards = due_cards[:limit]

        # Add new cards up to limit
        if include_new and len(due_cards) < limit:
            remaining = min(new_limit, limit - len(due_cards))
            due_cards.extend(new_cards[:remaining])

        return due_cards

    async def review_card(
        self,
        card_id: str,
        rating: ReviewRating,
        review_time: datetime | None = None,
    ) -> ReviewCard | None:
        """Process a card review.

        Args:
            card_id: Card UUID
            rating: User's rating
            review_time: Time of review (defaults to now)

        Returns:
            Updated card or None if not found
        """
        card = self._cards.get(card_id)
        if not card:
            return None

        # Apply FSRS scheduling
        updated_card = self._scheduler.schedule(card, rating, review_time)
        self._cards[card_id] = updated_card

        logger.debug(
            "Reviewed card %s: rating=%s, next_due=%s",
            card_id,
            rating.name,
            updated_card.due,
        )

        return updated_card

    # ============================================================
    # Session Management
    # ============================================================

    async def create_session(
        self,
        namespace: str = "default",
        max_cards: int = 20,
        include_new: bool = True,
        new_limit: int = 10,
    ) -> ReviewSession:
        """Create a new review session.

        Args:
            namespace: Card namespace
            max_cards: Maximum cards in session
            include_new: Include new cards
            new_limit: Max new cards

        Returns:
            New review session
        """
        # Get due cards
        cards = await self.get_due_cards(
            namespace=namespace,
            limit=max_cards,
            include_new=include_new,
            new_limit=new_limit,
        )

        session = ReviewSession(
            id=uuid4(),
            namespace=namespace,
            cards=[card.to_dict() for card in cards],
            total_cards=len(cards),
            reviewed_count=0,
            started_at=_utc_now(),
        )

        self._sessions[str(session.id)] = session
        logger.info(
            "Created review session %s with %d cards",
            session.id,
            len(cards),
        )

        return session

    async def get_session(self, session_id: str) -> ReviewSession | None:
        """Get a session by ID.

        Args:
            session_id: Session UUID

        Returns:
            Session if found
        """
        return self._sessions.get(session_id)

    async def complete_session(self, session_id: str) -> ReviewSession | None:
        """Mark a session as complete.

        Args:
            session_id: Session UUID

        Returns:
            Updated session
        """
        session = self._sessions.get(session_id)
        if session:
            session.completed_at = _utc_now()
            return session
        return None

    # ============================================================
    # Card Generation
    # ============================================================

    async def generate_cards_from_document(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
        namespace: str = "default",
        card_types: list[CardType] | None = None,
        tags: list[str] | None = None,
    ) -> list[ReviewCard]:
        """Generate review cards from document chunks.

        Args:
            document_id: Source document ID
            chunks: List of chunk dicts with id, content
            namespace: Card namespace
            card_types: Types of cards to generate
            tags: Tags to add

        Returns:
            Generated cards
        """
        card_types = card_types or [CardType.CONCEPT, CardType.FACT]
        all_cards: list[ReviewCard] = []

        for chunk in chunks:
            cards = await self._card_generator.generate_from_chunk(
                chunk_id=chunk["id"],
                content=chunk["content"],
                document_id=document_id,
                document_title=chunk.get("document_title", ""),
                namespace=namespace,
                card_types=card_types,
                tags=tags,
            )
            all_cards.extend(cards)

            # Store generated cards
            for card in cards:
                self._cards[str(card.id)] = card

        logger.info(
            "Generated %d cards from document %s",
            len(all_cards),
            document_id,
        )

        return all_cards

    # ============================================================
    # Statistics
    # ============================================================

    async def get_stats(
        self,
        namespace: str = "default",
    ) -> ReviewStats:
        """Get learning statistics.

        Args:
            namespace: Filter by namespace

        Returns:
            Review statistics
        """
        now = _utc_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        stats = ReviewStats()
        total_retrievability = 0.0

        for card in self._cards.values():
            if card.namespace != namespace or card.suspended:
                continue

            stats.total_cards += 1

            # Count by state
            if card.state == ReviewState.NEW:
                stats.cards_new += 1
            elif card.state in (ReviewState.LEARNING, ReviewState.RELEARNING):
                stats.cards_learning += 1
            else:
                stats.cards_review += 1

            # Count due today
            if card.state != ReviewState.NEW and card.due <= now:
                stats.cards_due_today += 1

            # Count reviewed today
            if card.last_review and card.last_review >= today_start:
                stats.cards_reviewed_today += 1

            # Accumulate stats
            stats.total_reviews += card.reps

            # Calculate average retrievability
            if card.state not in (ReviewState.NEW, ReviewState.LEARNING):
                ret = self._scheduler.get_retrievability(card, now)
                total_retrievability += ret

        # Calculate average retention
        review_cards = stats.cards_review
        if review_cards > 0:
            stats.average_retention = total_retrievability / review_cards

        return stats

    async def get_forecast(
        self,
        namespace: str = "default",
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Forecast upcoming reviews.

        Args:
            namespace: Filter by namespace
            days: Days to forecast

        Returns:
            List of {date, due_count, new_available}
        """
        now = _utc_now()
        forecast: list[dict[str, Any]] = []

        for day_offset in range(days):
            date = (now + timedelta(days=day_offset)).date()
            day_start = datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)

            due_count = 0
            new_count = 0

            for card in self._cards.values():
                if card.namespace != namespace or card.suspended:
                    continue

                if card.state == ReviewState.NEW:
                    new_count += 1
                elif day_start <= card.due < day_end:
                    due_count += 1

            forecast.append({
                "date": date.isoformat(),
                "due_count": due_count,
                "new_available": new_count if day_offset == 0 else 0,
            })

        return forecast
