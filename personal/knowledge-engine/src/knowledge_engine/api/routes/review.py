"""API routes for spaced repetition reviews."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from knowledge_engine.learning import (
    FSRSScheduler,
    ReviewCard,
    ReviewRating,
    ReviewService,
    ReviewSession,
)

router = APIRouter(prefix="/review", tags=["Review"])

# Global review service instance (in production, use dependency injection)
_review_service: ReviewService | None = None


def get_review_service() -> ReviewService:
    """Get or create review service."""
    global _review_service
    if _review_service is None:
        _review_service = ReviewService()
    return _review_service


# ============================================================
# Request/Response Models
# ============================================================


class CreateCardRequest(BaseModel):
    """Request to create a review card."""

    front: str = Field(..., min_length=1, description="Question/prompt")
    back: str = Field(..., min_length=1, description="Answer/content")
    context: str = Field(default="", description="Additional context")
    namespace: str = Field(default="default")
    tags: list[str] = Field(default_factory=list)
    source_type: str = Field(default="manual")
    source_id: str = Field(default="")


class ReviewRequest(BaseModel):
    """Request to submit a review."""

    card_id: str = Field(..., description="Card UUID")
    rating: int = Field(..., ge=1, le=4, description="Rating: 1=Again, 2=Hard, 3=Good, 4=Easy")


class CreateSessionRequest(BaseModel):
    """Request to create a review session."""

    namespace: str = Field(default="default")
    max_cards: int = Field(default=20, ge=1, le=100)
    include_new: bool = Field(default=True)
    new_limit: int = Field(default=10, ge=0, le=50)


class CardResponse(BaseModel):
    """Response with card data."""

    id: str
    front: str
    back: str
    context: str
    source_type: str
    source_id: str
    namespace: str
    state: str
    difficulty: float
    stability: float
    retrievability: float
    due: str
    reps: int
    lapses: int
    streak: int
    tags: list[str]

    @classmethod
    def from_card(cls, card: ReviewCard) -> "CardResponse":
        """Create from ReviewCard."""
        return cls(
            id=str(card.id),
            front=card.front,
            back=card.back,
            context=card.context,
            source_type=card.source_type,
            source_id=card.source_id,
            namespace=card.namespace,
            state=card.state.value,
            difficulty=card.difficulty,
            stability=card.stability,
            retrievability=card.retrievability,
            due=card.due.isoformat(),
            reps=card.reps,
            lapses=card.lapses,
            streak=card.streak,
            tags=card.tags,
        )


class SessionResponse(BaseModel):
    """Response with session data."""

    id: str
    namespace: str
    total_cards: int
    reviewed_count: int
    remaining: int
    progress_percent: float
    started_at: str
    is_complete: bool
    cards: list[dict[str, Any]]

    @classmethod
    def from_session(cls, session: ReviewSession) -> "SessionResponse":
        """Create from ReviewSession."""
        return cls(
            id=str(session.id),
            namespace=session.namespace,
            total_cards=session.total_cards,
            reviewed_count=session.reviewed_count,
            remaining=session.remaining,
            progress_percent=session.progress_percent,
            started_at=session.started_at.isoformat(),
            is_complete=session.is_complete,
            cards=session.cards,
        )


class StatsResponse(BaseModel):
    """Response with learning statistics."""

    total_cards: int
    cards_reviewed_today: int
    cards_due_today: int
    cards_new: int
    cards_learning: int
    cards_review: int
    average_retention: float
    streak_days: int
    total_reviews: int


class ForecastItem(BaseModel):
    """A single day in the review forecast."""

    date: str
    due_count: int
    new_available: int


# ============================================================
# Card Endpoints
# ============================================================


@router.post("/cards", response_model=CardResponse)
async def create_card(
    request: CreateCardRequest,
    service: ReviewService = Depends(get_review_service),
) -> CardResponse:
    """Create a new review card."""
    card = await service.create_card(
        front=request.front,
        back=request.back,
        context=request.context,
        namespace=request.namespace,
        tags=request.tags,
        source_type=request.source_type,
        source_id=request.source_id,
    )
    return CardResponse.from_card(card)


@router.get("/cards/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: str,
    service: ReviewService = Depends(get_review_service),
) -> CardResponse:
    """Get a card by ID."""
    card = await service.get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return CardResponse.from_card(card)


@router.delete("/cards/{card_id}")
async def delete_card(
    card_id: str,
    service: ReviewService = Depends(get_review_service),
) -> dict[str, str]:
    """Delete a card."""
    deleted = await service.delete_card(card_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"status": "deleted", "card_id": card_id}


@router.post("/cards/{card_id}/suspend")
async def suspend_card(
    card_id: str,
    suspend: bool = Query(default=True),
    service: ReviewService = Depends(get_review_service),
) -> CardResponse:
    """Suspend or unsuspend a card."""
    card = await service.suspend_card(card_id, suspend)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return CardResponse.from_card(card)


# ============================================================
# Review Endpoints
# ============================================================


@router.get("/due", response_model=list[CardResponse])
async def get_due_cards(
    namespace: str = Query(default="default"),
    limit: int = Query(default=20, ge=1, le=100),
    include_new: bool = Query(default=True),
    new_limit: int = Query(default=10, ge=0, le=50),
    service: ReviewService = Depends(get_review_service),
) -> list[CardResponse]:
    """Get cards due for review."""
    cards = await service.get_due_cards(
        namespace=namespace,
        limit=limit,
        include_new=include_new,
        new_limit=new_limit,
    )
    return [CardResponse.from_card(card) for card in cards]


@router.post("/submit", response_model=CardResponse)
async def submit_review(
    request: ReviewRequest,
    service: ReviewService = Depends(get_review_service),
) -> CardResponse:
    """Submit a card review."""
    try:
        rating = ReviewRating(request.rating)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid rating. Use 1=Again, 2=Hard, 3=Good, 4=Easy",
        )

    card = await service.review_card(request.card_id, rating)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    return CardResponse.from_card(card)


# ============================================================
# Session Endpoints
# ============================================================


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    service: ReviewService = Depends(get_review_service),
) -> SessionResponse:
    """Create a new review session."""
    session = await service.create_session(
        namespace=request.namespace,
        max_cards=request.max_cards,
        include_new=request.include_new,
        new_limit=request.new_limit,
    )
    return SessionResponse.from_session(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    service: ReviewService = Depends(get_review_service),
) -> SessionResponse:
    """Get a session by ID."""
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse.from_session(session)


@router.post("/sessions/{session_id}/complete", response_model=SessionResponse)
async def complete_session(
    session_id: str,
    service: ReviewService = Depends(get_review_service),
) -> SessionResponse:
    """Mark a session as complete."""
    session = await service.complete_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse.from_session(session)


# ============================================================
# Statistics Endpoints
# ============================================================


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    namespace: str = Query(default="default"),
    service: ReviewService = Depends(get_review_service),
) -> StatsResponse:
    """Get learning statistics."""
    stats = await service.get_stats(namespace)
    return StatsResponse(
        total_cards=stats.total_cards,
        cards_reviewed_today=stats.cards_reviewed_today,
        cards_due_today=stats.cards_due_today,
        cards_new=stats.cards_new,
        cards_learning=stats.cards_learning,
        cards_review=stats.cards_review,
        average_retention=stats.average_retention,
        streak_days=stats.streak_days,
        total_reviews=stats.total_reviews,
    )


@router.get("/forecast", response_model=list[ForecastItem])
async def get_forecast(
    namespace: str = Query(default="default"),
    days: int = Query(default=7, ge=1, le=30),
    service: ReviewService = Depends(get_review_service),
) -> list[ForecastItem]:
    """Get review forecast for upcoming days."""
    forecast = await service.get_forecast(namespace, days)
    return [ForecastItem(**item) for item in forecast]
