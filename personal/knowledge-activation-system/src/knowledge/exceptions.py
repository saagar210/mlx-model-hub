"""Custom exception hierarchy for KAS (P14: Error Handling Standardization)."""

from typing import Any


class KASError(Exception):
    """Base exception for all KAS errors."""

    error_code: str = "KAS_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        self.cause = cause
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        result = {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }
        return result

    def __str__(self) -> str:
        if self.details:
            return f"{self.error_code}: {self.message} ({self.details})"
        return f"{self.error_code}: {self.message}"


# =============================================================================
# Database Errors
# =============================================================================


class DatabaseError(KASError):
    """Database operation failed."""

    error_code = "DATABASE_ERROR"
    status_code = 503


class ConnectionError(DatabaseError):
    """Database connection failed."""

    error_code = "CONNECTION_ERROR"


class ConnectionPoolExhaustedError(DatabaseError):
    """Connection pool exhausted."""

    error_code = "POOL_EXHAUSTED"


class QueryError(DatabaseError):
    """Database query failed."""

    error_code = "QUERY_ERROR"


class TransactionError(DatabaseError):
    """Database transaction failed."""

    error_code = "TRANSACTION_ERROR"


# =============================================================================
# Search Errors
# =============================================================================


class SearchError(KASError):
    """Search operation failed."""

    error_code = "SEARCH_ERROR"
    status_code = 500


class EmbeddingError(SearchError):
    """Embedding generation failed."""

    error_code = "EMBEDDING_ERROR"


class RerankerError(SearchError):
    """Reranking operation failed."""

    error_code = "RERANKER_ERROR"


class SearchTimeoutError(SearchError):
    """Search operation timed out."""

    error_code = "SEARCH_TIMEOUT"
    status_code = 504


# =============================================================================
# Ingestion Errors
# =============================================================================


class IngestError(KASError):
    """Content ingestion failed."""

    error_code = "INGEST_ERROR"
    status_code = 400


class ContentFetchError(IngestError):
    """Failed to fetch content from URL."""

    error_code = "CONTENT_FETCH_ERROR"


class ContentParseError(IngestError):
    """Failed to parse content."""

    error_code = "CONTENT_PARSE_ERROR"


class ChunkingError(IngestError):
    """Content chunking failed."""

    error_code = "CHUNKING_ERROR"


class DuplicateContentError(IngestError):
    """Content already exists."""

    error_code = "DUPLICATE_CONTENT"
    status_code = 409


class ContentTooLargeError(IngestError):
    """Content exceeds size limit."""

    error_code = "CONTENT_TOO_LARGE"
    status_code = 413


class UnsupportedContentTypeError(IngestError):
    """Content type not supported."""

    error_code = "UNSUPPORTED_CONTENT_TYPE"
    status_code = 415


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(KASError):
    """Input validation failed."""

    error_code = "VALIDATION_ERROR"
    status_code = 400


class InvalidQueryError(ValidationError):
    """Search query is invalid."""

    error_code = "INVALID_QUERY"


class InvalidNamespaceError(ValidationError):
    """Namespace format is invalid."""

    error_code = "INVALID_NAMESPACE"


class InvalidFilepathError(ValidationError):
    """Filepath is invalid or unsafe."""

    error_code = "INVALID_FILEPATH"


class InvalidURLError(ValidationError):
    """URL is invalid or unsafe."""

    error_code = "INVALID_URL"


# =============================================================================
# Resource Errors
# =============================================================================


class NotFoundError(KASError):
    """Resource not found."""

    error_code = "NOT_FOUND"
    status_code = 404


class ContentNotFoundError(NotFoundError):
    """Content not found."""

    error_code = "CONTENT_NOT_FOUND"


class ChunkNotFoundError(NotFoundError):
    """Chunk not found."""

    error_code = "CHUNK_NOT_FOUND"


# =============================================================================
# Authentication & Authorization Errors
# =============================================================================


class AuthError(KASError):
    """Authentication failed."""

    error_code = "AUTH_ERROR"
    status_code = 401


class InvalidAPIKeyError(AuthError):
    """API key is invalid or expired."""

    error_code = "INVALID_API_KEY"


class MissingAPIKeyError(AuthError):
    """API key is required but not provided."""

    error_code = "MISSING_API_KEY"


class InsufficientScopeError(KASError):
    """Insufficient permissions for operation."""

    error_code = "INSUFFICIENT_SCOPE"
    status_code = 403


class RateLimitError(KASError):
    """Rate limit exceeded."""

    error_code = "RATE_LIMIT_EXCEEDED"
    status_code = 429

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if retry_after is not None:
            details["retry_after"] = retry_after
        super().__init__(message, details=details, **kwargs)
        self.retry_after = retry_after


# =============================================================================
# External Service Errors
# =============================================================================


class ExternalServiceError(KASError):
    """External service is unavailable."""

    error_code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502


class OllamaError(ExternalServiceError):
    """Ollama service error."""

    error_code = "OLLAMA_ERROR"


class OllamaUnavailableError(OllamaError):
    """Ollama service is unavailable."""

    error_code = "OLLAMA_UNAVAILABLE"
    status_code = 503


class CircuitOpenError(ExternalServiceError):
    """Circuit breaker is open."""

    error_code = "CIRCUIT_OPEN"
    status_code = 503

    def __init__(
        self,
        circuit_name: str,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.circuit_name = circuit_name
        msg = message or f"Circuit '{circuit_name}' is open"
        super().__init__(msg, details={"circuit": circuit_name}, **kwargs)


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(KASError):
    """Configuration error."""

    error_code = "CONFIGURATION_ERROR"
    status_code = 500


class MissingConfigurationError(ConfigurationError):
    """Required configuration is missing."""

    error_code = "MISSING_CONFIGURATION"


# =============================================================================
# Review Errors
# =============================================================================


class ReviewError(KASError):
    """Review operation failed."""

    error_code = "REVIEW_ERROR"
    status_code = 400


class InvalidRatingError(ReviewError):
    """Invalid review rating."""

    error_code = "INVALID_RATING"


class NoCardsAvailableError(ReviewError):
    """No cards available for review."""

    error_code = "NO_CARDS_AVAILABLE"
    status_code = 404
