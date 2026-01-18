"""Security utilities and hardening for the Knowledge Engine.

This module provides security primitives for:
- Constant-time comparisons (timing attack prevention)
- Path traversal prevention
- Input sanitization
- Request correlation
- Secure secret handling
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import uuid
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Context variable for request correlation ID
_request_id: ContextVar[str] = ContextVar("request_id", default="")


# =============================================================================
# Request Correlation
# =============================================================================


def get_request_id() -> str:
    """Get the current request correlation ID."""
    return _request_id.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set and return a request correlation ID."""
    rid = request_id or str(uuid.uuid4())[:8]
    _request_id.set(rid)
    return rid


def clear_request_id() -> None:
    """Clear the request correlation ID."""
    _request_id.set("")


# =============================================================================
# Constant-Time Comparisons (Timing Attack Prevention)
# =============================================================================


def secure_compare(a: str | bytes, b: str | bytes) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.

    Always use this for comparing:
    - API keys
    - Webhook signatures
    - Tokens
    - Any security-sensitive values

    Args:
        a: First value to compare
        b: Second value to compare

    Returns:
        True if values are equal, False otherwise
    """
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    return secrets.compare_digest(a, b)


def verify_hmac_signature(
    payload: str | bytes,
    signature: str,
    secret: str,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify an HMAC signature using constant-time comparison.

    Args:
        payload: The payload that was signed
        signature: The signature to verify (hex-encoded)
        secret: The secret key
        algorithm: Hash algorithm (default: sha256)

    Returns:
        True if signature is valid
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        getattr(hashlib, algorithm),
    ).hexdigest()

    return secure_compare(signature, expected)


# =============================================================================
# Path Traversal Prevention
# =============================================================================


class PathSecurityError(Exception):
    """Raised when a path security violation is detected."""
    pass


def resolve_safe_path(
    user_path: str | Path,
    base_path: str | Path,
    allow_symlinks: bool = False,
) -> Path:
    """
    Safely resolve a user-provided path within a base directory.

    Prevents path traversal attacks by ensuring the resolved path
    is within the allowed base directory.

    Args:
        user_path: User-provided path (may be relative or absolute)
        base_path: Allowed base directory
        allow_symlinks: Whether to allow symlinks (default: False)

    Returns:
        Safely resolved absolute path

    Raises:
        PathSecurityError: If path escapes base directory or contains symlinks
    """
    base = Path(base_path).resolve()

    # Handle both absolute and relative paths
    if Path(user_path).is_absolute():
        target = Path(user_path)
    else:
        target = base / user_path

    # Resolve the path (follows symlinks by default)
    resolved = target.resolve()

    # Check if resolved path is within base
    try:
        resolved.relative_to(base)
    except ValueError as e:
        raise PathSecurityError(
            f"Path traversal detected: {user_path} escapes {base_path}"
        ) from e

    # Check for symlinks if not allowed
    if not allow_symlinks:
        # Walk up the path checking for symlinks
        check_path = resolved
        while check_path != base:
            if check_path.is_symlink():
                raise PathSecurityError(
                    f"Symlink not allowed: {check_path}"
                )
            check_path = check_path.parent
            if check_path == check_path.parent:
                break

    return resolved


def is_safe_filename(filename: str) -> bool:
    """
    Check if a filename is safe (no path components, no special chars).

    Args:
        filename: Filename to check

    Returns:
        True if filename is safe
    """
    # No path separators
    if "/" in filename or "\\" in filename:
        return False

    # No hidden files (starts with dot)
    if filename.startswith("."):
        return False

    # No null bytes
    if "\x00" in filename:
        return False

    # No control characters
    if any(ord(c) < 32 for c in filename):
        return False

    # Reasonable length
    if len(filename) > 255:
        return False

    return True


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    Sanitize a filename for safe filesystem use.

    Args:
        filename: Original filename
        max_length: Maximum allowed length

    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Replace problematic characters
    filename = re.sub(r'[^\w\-_. ]', '_', filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')

    # Collapse multiple underscores/spaces
    filename = re.sub(r'[_\s]+', '_', filename)

    # Truncate
    if len(filename) > max_length:
        base, ext = os.path.splitext(filename)
        base = base[:max_length - len(ext)]
        filename = base + ext

    # Ensure not empty
    if not filename:
        filename = "unnamed"

    return filename


# =============================================================================
# Input Validation
# =============================================================================


class InputValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_search_query(
    query: str,
    max_length: int = 1000,
    min_length: int = 1,
) -> str:
    """
    Validate and sanitize a search query.

    Args:
        query: Raw search query
        max_length: Maximum allowed length
        min_length: Minimum required length

    Returns:
        Validated query string

    Raises:
        InputValidationError: If query is invalid
    """
    if not query:
        raise InputValidationError("Query cannot be empty")

    # Strip whitespace
    query = query.strip()

    # Check length
    if len(query) < min_length:
        raise InputValidationError(f"Query too short (min {min_length} chars)")

    if len(query) > max_length:
        raise InputValidationError(f"Query too long (max {max_length} chars)")

    # Remove null bytes and control characters
    query = re.sub(r'[\x00-\x1f\x7f]', '', query)

    return query


def validate_uuid(value: str) -> str:
    """
    Validate a UUID string.

    Args:
        value: UUID string to validate

    Returns:
        Validated UUID string (lowercase)

    Raises:
        InputValidationError: If not a valid UUID
    """
    try:
        from uuid import UUID
        return str(UUID(value))
    except (ValueError, AttributeError) as e:
        raise InputValidationError(f"Invalid UUID: {value}") from e


def validate_content_type(content_type: str) -> str:
    """
    Validate content type against allowed values.

    Args:
        content_type: Content type to validate

    Returns:
        Validated content type

    Raises:
        InputValidationError: If content type not allowed
    """
    allowed = {"youtube", "bookmark", "file", "note", "research"}

    if content_type not in allowed:
        raise InputValidationError(
            f"Invalid content type: {content_type}. "
            f"Allowed: {', '.join(sorted(allowed))}"
        )

    return content_type


# =============================================================================
# Secret Management
# =============================================================================


def generate_api_key(prefix: str = "kas", length: int = 32) -> str:
    """
    Generate a cryptographically secure API key.

    Format: {prefix}_{random_hex}
    Example: kas_a1b2c3d4e5f6...

    Args:
        prefix: Key prefix for identification
        length: Number of random bytes

    Returns:
        Generated API key
    """
    random_part = secrets.token_hex(length)
    return f"{prefix}_{random_part}"


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage.

    Uses SHA-256 which is sufficient for API keys since they're
    already high-entropy values.

    Args:
        api_key: API key to hash

    Returns:
        Hex-encoded hash
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """
    Mask a secret for safe logging/display.

    Args:
        secret: Secret to mask
        visible_chars: Number of chars to show at end

    Returns:
        Masked string like "****abcd"
    """
    if len(secret) <= visible_chars:
        return "*" * len(secret)

    return "*" * (len(secret) - visible_chars) + secret[-visible_chars:]


# =============================================================================
# Error Sanitization
# =============================================================================


def sanitize_error_message(
    error: Exception,
    include_type: bool = True,
    production: bool = True,
) -> str:
    """
    Sanitize error messages for external responses.

    In production mode, removes potentially sensitive information
    like file paths, stack traces, internal details, and credentials.

    Args:
        error: The exception
        include_type: Include error type name
        production: Whether in production mode

    Returns:
        Sanitized error message
    """
    if not production:
        return str(error)

    error_str = str(error)

    # Remove credentials and secrets (password=xxx, secret=xxx, token=xxx, api_key=xxx)
    error_str = re.sub(
        r'(password|passwd|secret|token|api_key|apikey|auth|credential|bearer)\s*[=:]\s*\S+',
        r'\1=[REDACTED]',
        error_str,
        flags=re.IGNORECASE
    )

    # Remove connection strings with embedded credentials
    error_str = re.sub(
        r'(postgres|mysql|mongodb|redis)://[^@]+@',
        r'\1://[REDACTED]@',
        error_str,
        flags=re.IGNORECASE
    )

    # Remove file paths
    error_str = re.sub(r'/[^\s:]+\.(py|txt|md|json|yaml)', '[file]', error_str)

    # Remove line numbers from tracebacks
    error_str = re.sub(r'line \d+', 'line [N]', error_str)

    # Remove internal module references
    error_str = re.sub(r'knowledge\.[a-z_.]+', '[module]', error_str)

    # Remove IP addresses
    error_str = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', '[IP]', error_str)

    # Truncate very long messages
    if len(error_str) > 200:
        error_str = error_str[:200] + "..."

    if include_type:
        return f"{type(error).__name__}: {error_str}"

    return error_str


# =============================================================================
# Security Configuration
# =============================================================================


@lru_cache
def get_security_config() -> dict[str, Any]:
    """
    Get security configuration from environment.

    Returns:
        Security configuration dict
    """
    return {
        "production": os.getenv("ENV", "development") == "production",
        "require_api_key": os.getenv("KNOWLEDGE_REQUIRE_API_KEY", "false").lower() == "true",
        "rate_limit_enabled": True,
        "max_query_length": int(os.getenv("KNOWLEDGE_MAX_QUERY_LENGTH", "1000")),
        "max_upload_size_mb": int(os.getenv("KNOWLEDGE_MAX_UPLOAD_SIZE_MB", "50")),
        "allowed_file_extensions": {".pdf", ".txt", ".md", ".markdown"},
    }


def is_production() -> bool:
    """Check if running in production mode."""
    return get_security_config()["production"]
