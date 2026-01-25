"""Bi-temporal metadata models."""

from datetime import datetime

from pydantic import BaseModel, Field


class BiTemporalMetadata(BaseModel):
    """
    Bi-temporal tracking for facts.

    Supports both event time (when something happened in the real world)
    and ingestion time (when we learned about it).
    """

    t_valid: datetime = Field(
        description="When the fact became true in the real world"
    )
    t_invalid: datetime | None = Field(
        default=None,
        description="When the fact stopped being true (NULL = still valid)"
    )
    t_created: datetime = Field(
        default_factory=datetime.utcnow,
        description="When ingested into UCE"
    )
    t_expired: datetime | None = Field(
        default=None,
        description="When superseded by a newer version"
    )

    def is_valid(self, as_of: datetime | None = None) -> bool:
        """Check if fact is valid at a given time (defaults to now)."""
        check_time = as_of or datetime.utcnow()

        if self.t_valid > check_time:
            return False

        if self.t_invalid and self.t_invalid <= check_time:
            return False

        return True

    def is_current(self) -> bool:
        """Check if this is the current (non-expired) version."""
        return self.t_expired is None

    def invalidate(self, at: datetime | None = None) -> None:
        """Mark the fact as no longer valid."""
        self.t_invalid = at or datetime.utcnow()

    def expire(self, at: datetime | None = None) -> None:
        """Mark this version as superseded."""
        self.t_expired = at or datetime.utcnow()
