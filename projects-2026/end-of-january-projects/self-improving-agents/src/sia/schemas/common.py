"""
Common schemas shared across the application.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for database query."""
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


class HealthCheck(BaseModel):
    """Health check response."""

    status: str = Field(description="Health status (healthy/unhealthy)")
    version: str | None = Field(default=None, description="Database version")
    extensions: list[str] = Field(default_factory=list, description="Installed extensions")
    tables: list[str] = Field(default_factory=list, description="Available tables")
    error: str | None = Field(default=None, description="Error message if unhealthy")


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(description="Error message")
    error_type: str | None = Field(default=None, description="Error type/code")
    context: dict[str, Any] | None = Field(default=None, description="Additional context")
