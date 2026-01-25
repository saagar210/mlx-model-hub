"""Retry utilities with exponential backoff."""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    before_sleep_log,
    after_log,
)

from knowledge_seeder.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Retryable exceptions for HTTP operations
RETRYABLE_HTTP_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)

# HTTP status codes worth retrying
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class RetryableHTTPError(Exception):
    """HTTP error that should be retried."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


def is_retryable_status(status_code: int) -> bool:
    """Check if HTTP status code is retryable."""
    return status_code in RETRYABLE_STATUS_CODES


def create_retry_decorator(
    max_attempts: int | None = None,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    exponential_base: float = 2.0,
) -> Callable:
    """Create a retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts (default from settings)
        min_wait: Minimum wait time between retries
        max_wait: Maximum wait time between retries
        exponential_base: Base for exponential backoff

    Returns:
        Configured retry decorator
    """
    settings = get_settings()
    attempts = max_attempts or settings.max_retries

    return retry(
        retry=retry_if_exception_type(RETRYABLE_HTTP_EXCEPTIONS + (RetryableHTTPError,)),
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(
            multiplier=min_wait,
            max=max_wait,
            exp_base=exponential_base,
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )


async def retry_async(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int | None = None,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    **kwargs: Any,
) -> T:
    """Execute async function with exponential backoff retry.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_attempts: Maximum retry attempts
        min_wait: Minimum wait time between retries
        max_wait: Maximum wait time between retries
        **kwargs: Keyword arguments for func

    Returns:
        Result of successful function call

    Raises:
        RetryError: If all retry attempts fail
    """
    settings = get_settings()
    attempts = max_attempts or settings.max_retries

    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(RETRYABLE_HTTP_EXCEPTIONS + (RetryableHTTPError,)),
        stop=stop_after_attempt(attempts),
        wait=wait_random_exponential(min=min_wait, max=max_wait),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    ):
        with attempt:
            return await func(*args, **kwargs)

    # Should never reach here due to reraise=True
    raise RuntimeError("Retry loop exited unexpectedly")


async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    method: str = "GET",
    max_attempts: int | None = None,
    **kwargs: Any,
) -> httpx.Response:
    """Fetch URL with automatic retry on transient failures.

    Args:
        client: HTTP client instance
        url: URL to fetch
        method: HTTP method (GET, POST, etc.)
        max_attempts: Maximum retry attempts
        **kwargs: Additional arguments for httpx request

    Returns:
        HTTP response

    Raises:
        httpx.HTTPError: If request fails after all retries
        RetryableHTTPError: If response has retryable status code
    """
    settings = get_settings()
    attempts = max_attempts or settings.max_retries

    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(RETRYABLE_HTTP_EXCEPTIONS + (RetryableHTTPError,)),
        stop=stop_after_attempt(attempts),
        wait=wait_random_exponential(min=1, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    ):
        with attempt:
            response = await client.request(method, url, **kwargs)

            # Check for retryable status codes
            if is_retryable_status(response.status_code):
                raise RetryableHTTPError(
                    response.status_code,
                    f"Retryable HTTP error for {url}",
                )

            return response

    # Should never reach here
    raise RuntimeError("Retry loop exited unexpectedly")


class RetryStats:
    """Track retry statistics for monitoring."""

    def __init__(self) -> None:
        self.total_attempts: int = 0
        self.successful_first_try: int = 0
        self.successful_after_retry: int = 0
        self.failed_all_retries: int = 0
        self.total_wait_time: float = 0.0

    def record_success(self, attempts: int, wait_time: float = 0.0) -> None:
        """Record a successful operation."""
        self.total_attempts += attempts
        self.total_wait_time += wait_time
        if attempts == 1:
            self.successful_first_try += 1
        else:
            self.successful_after_retry += 1

    def record_failure(self, attempts: int, wait_time: float = 0.0) -> None:
        """Record a failed operation."""
        self.total_attempts += attempts
        self.total_wait_time += wait_time
        self.failed_all_retries += 1

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        total = self.successful_first_try + self.successful_after_retry + self.failed_all_retries
        if total == 0:
            return 0.0
        return (self.successful_first_try + self.successful_after_retry) / total

    @property
    def retry_rate(self) -> float:
        """Calculate rate of operations requiring retry."""
        successful = self.successful_first_try + self.successful_after_retry
        if successful == 0:
            return 0.0
        return self.successful_after_retry / successful

    def __repr__(self) -> str:
        return (
            f"RetryStats(success_rate={self.success_rate:.2%}, "
            f"retry_rate={self.retry_rate:.2%}, "
            f"total_attempts={self.total_attempts})"
        )
