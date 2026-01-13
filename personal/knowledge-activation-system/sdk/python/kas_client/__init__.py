"""
KAS (Knowledge Activation System) Python SDK

A typed Python client for interacting with the KAS API.

Usage:
    from kas_client import KASClient

    client = KASClient("http://localhost:8000")

    # Search knowledge base
    results = await client.search("FastAPI dependency injection")

    # Ask a question
    answer = await client.ask("How does connection pooling work?")

    # Ingest content
    result = await client.ingest(
        content="# My Notes\n\nSome content here...",
        title="My Notes",
        namespace="notes"
    )
"""

from kas_client.client import (
    KASClient,
    KASClientSync,
    SearchResult,
    SearchResponse,
    AskResponse,
    Citation,
    IngestResponse,
    HealthResponse,
    ReviewItem,
    ReviewSubmitResponse,
    ReviewStats,
    Namespace,
    KASError,
    KASConnectionError,
    KASAPIError,
    KASValidationError,
)

__version__ = "0.1.0"
__all__ = [
    "KASClient",
    "KASClientSync",
    "SearchResult",
    "SearchResponse",
    "AskResponse",
    "Citation",
    "IngestResponse",
    "HealthResponse",
    "ReviewItem",
    "ReviewSubmitResponse",
    "ReviewStats",
    "Namespace",
    "KASError",
    "KASConnectionError",
    "KASAPIError",
    "KASValidationError",
]
