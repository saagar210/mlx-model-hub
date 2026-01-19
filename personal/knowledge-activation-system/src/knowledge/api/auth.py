"""API Authentication (P17: Authentication System)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, Header, Request
from pydantic import BaseModel

from knowledge.config import get_settings
from knowledge.db import get_db
from knowledge.exceptions import (
    InsufficientScopeError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
)
from knowledge.logging import get_logger

logger = get_logger(__name__)

# Argon2 hasher with tuned parameters for API keys (high entropy)
# Lower memory/time cost than passwords since API keys have high entropy
_argon2_hasher = PasswordHasher(
    time_cost=2,      # 2 iterations
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


# =============================================================================
# Valid Scopes
# =============================================================================

# Whitelist of valid API scopes
VALID_SCOPES: set[str] = {
    "read",      # Read content, search, Q&A
    "write",     # Create/update content
    "delete",    # Delete content
    "admin",     # Full admin access (grants all scopes)
    "export",    # Export data
    "import",    # Import data
    "review",    # Access review/FSRS features
    "analytics", # Access analytics data
}


def validate_scopes(scopes: list[str]) -> list[str]:
    """Validate that all scopes are in the allowed list.

    Args:
        scopes: List of scopes to validate

    Returns:
        Validated list of scopes

    Raises:
        ValueError: If any scope is invalid
    """
    invalid = set(scopes) - VALID_SCOPES
    if invalid:
        raise ValueError(
            f"Invalid scope(s): {', '.join(sorted(invalid))}. "
            f"Valid scopes: {', '.join(sorted(VALID_SCOPES))}"
        )
    return scopes


# =============================================================================
# Models
# =============================================================================


class APIKey(BaseModel):
    """Validated API key with metadata."""

    id: UUID
    name: str
    scopes: list[str]
    rate_limit: int


class APIKeyInfo(BaseModel):
    """API key information (without sensitive data)."""

    id: UUID
    name: str
    description: str | None
    scopes: list[str]
    rate_limit: int
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    is_active: bool


class CreateKeyRequest(BaseModel):
    """Request to create a new API key."""

    name: str
    description: str | None = None
    scopes: list[str] = ["read"]
    rate_limit: int = 100
    expires_in_days: int | None = None


class CreateKeyResponse(BaseModel):
    """Response with newly created API key."""

    id: UUID
    name: str
    key: str  # Only returned once at creation
    scopes: list[str]
    rate_limit: int
    expires_at: datetime | None


# =============================================================================
# Key Generation
# =============================================================================


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key and its Argon2 hash.

    Returns:
        Tuple of (plaintext_key, key_hash)
    """
    key = f"kas_{secrets.token_urlsafe(32)}"
    key_hash = _argon2_hasher.hash(key)
    return key, key_hash


def hash_api_key_argon2(key: str) -> str:
    """Hash an API key using Argon2id for storage."""
    return _argon2_hasher.hash(key)


def hash_api_key_sha256(key: str) -> str:
    """Hash an API key using SHA-256 (legacy, for migration)."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(key: str, stored_hash: str) -> bool:
    """
    Verify an API key against a stored hash.

    Supports both Argon2 (new) and SHA-256 (legacy) hashes.
    Argon2 hashes start with '$argon2', SHA-256 are 64 hex chars.

    Args:
        key: The plaintext API key
        stored_hash: The stored hash to verify against

    Returns:
        True if the key matches, False otherwise
    """
    if stored_hash.startswith("$argon2"):
        # Argon2 hash
        try:
            _argon2_hasher.verify(stored_hash, key)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False
    else:
        # Legacy SHA-256 hash (64 hex characters)
        return hashlib.sha256(key.encode()).hexdigest() == stored_hash


# =============================================================================
# Authentication Dependencies
# =============================================================================


async def get_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> APIKey | None:
    """
    Validate API key from request header.

    This is a FastAPI dependency that:
    1. Checks if authentication is required
    2. Validates the provided API key
    3. Returns APIKey model if valid

    Args:
        request: FastAPI request object
        x_api_key: API key from X-API-Key header

    Returns:
        APIKey if valid, None if auth not required

    Raises:
        MissingAPIKeyError: If auth required but no key provided
        InvalidAPIKeyError: If key is invalid/expired/revoked
    """
    settings = get_settings()

    # If auth not required and no key provided, allow anonymous access
    if not settings.require_api_key and not x_api_key:
        return None

    # If auth required but no key, reject
    if settings.require_api_key and not x_api_key:
        logger.warning(
            "api_key_missing",
            path=request.url.path,
            method=request.method,
        )
        raise MissingAPIKeyError("API key required")

    # No key provided and not required
    if not x_api_key:
        return None

    # Validate key format
    if not x_api_key.startswith("kas_"):
        logger.warning(
            "api_key_invalid_format",
            path=request.url.path,
        )
        raise InvalidAPIKeyError("Invalid API key format")

    # Fetch all active keys and verify using Argon2 or SHA-256 (legacy)
    # This approach supports both new Argon2 hashes and legacy SHA-256 hashes
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, scopes, rate_limit, key_hash
            FROM api_keys
            WHERE revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > NOW())
            """
        )

        # Find matching key by verifying against each stored hash
        row = None
        for candidate in rows:
            if verify_api_key(x_api_key, candidate["key_hash"]):
                row = candidate
                break

        if not row:
            # Log with SHA-256 hash prefix for debugging (doesn't reveal key)
            debug_hash = hash_api_key_sha256(x_api_key)
            logger.warning(
                "api_key_invalid",
                path=request.url.path,
                key_hash_prefix=debug_hash[:16],
            )
            raise InvalidAPIKeyError("Invalid or expired API key")

        # Update last used timestamp
        await conn.execute(
            "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1",
            row["id"],
        )

        logger.debug(
            "api_key_validated",
            key_id=str(row["id"]),
            key_name=row["name"],
        )

        return APIKey(
            id=row["id"],
            name=row["name"],
            scopes=list(row["scopes"]),
            rate_limit=row["rate_limit"],
        )


def require_scope(scope: str) -> Any:
    """
    Create a dependency that requires a specific scope.

    Usage:
        @router.post("/content", dependencies=[Depends(require_scope("write"))])
        async def create_content(...):
            ...

    Args:
        scope: Required scope (e.g., "read", "write", "admin")

    Returns:
        FastAPI dependency function

    Raises:
        ValueError: If scope is not in VALID_SCOPES
    """
    # Validate scope at dependency creation time (fail fast)
    if scope not in VALID_SCOPES:
        raise ValueError(
            f"Invalid scope '{scope}'. Valid scopes: {', '.join(sorted(VALID_SCOPES))}"
        )

    async def check_scope(
        api_key: APIKey | None = Depends(get_api_key),  # noqa: B008
    ) -> APIKey | None:
        """Check if API key has required scope."""
        # No key and not required = allow anonymous
        if api_key is None:
            return None

        # Admin scope grants all access
        if "admin" in api_key.scopes:
            return api_key

        # Check for required scope
        if scope not in api_key.scopes:
            logger.warning(
                "insufficient_scope",
                key_id=str(api_key.id),
                required_scope=scope,
                key_scopes=api_key.scopes,
            )
            raise InsufficientScopeError(
                f"Scope '{scope}' required",
                details={"required_scope": scope, "available_scopes": api_key.scopes},
            )

        return api_key

    return check_scope


def require_admin() -> Any:
    """
    Create a dependency that requires admin scope.

    Usage:
        @router.delete("/keys/{id}", dependencies=[Depends(require_admin())])
        async def delete_key(...):
            ...
    """
    return require_scope("admin")


# =============================================================================
# API Key Management
# =============================================================================


async def create_api_key_record(
    name: str,
    description: str | None = None,
    scopes: list[str] | None = None,
    rate_limit: int = 100,
    expires_in_days: int | None = None,
    created_by: str | None = None,
) -> tuple[str, UUID]:
    """
    Create a new API key in the database.

    Args:
        name: Human-readable name for the key
        description: Optional description
        scopes: List of scopes (default: ["read"])
        rate_limit: Requests per minute limit
        expires_in_days: Days until expiration (None = never)
        created_by: Audit trail - who created this key

    Returns:
        Tuple of (plaintext_key, key_id)

    Raises:
        ValueError: If any scope is invalid
    """
    key, key_hash = generate_api_key()

    if scopes is None:
        scopes = ["read"]
    else:
        # Validate scopes against whitelist
        validate_scopes(scopes)

    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO api_keys (key_hash, name, description, scopes, rate_limit, expires_at, created_by)
            VALUES ($1, $2, $3, $4, $5,
                    CASE WHEN $6::int IS NOT NULL
                         THEN NOW() + ($6::int || ' days')::interval
                         ELSE NULL END,
                    $7)
            RETURNING id
            """,
            key_hash,
            name,
            description,
            scopes,
            rate_limit,
            expires_in_days,
            created_by,
        )

        logger.info(
            "api_key_created",
            key_id=str(row["id"]),
            name=name,
            scopes=scopes,
        )

        return key, row["id"]


async def list_api_keys() -> list[APIKeyInfo]:
    """
    List all API keys (without sensitive data).

    Returns:
        List of APIKeyInfo
    """
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, description, scopes, rate_limit,
                   created_at, last_used_at, expires_at,
                   (revoked_at IS NULL AND (expires_at IS NULL OR expires_at > NOW())) as is_active
            FROM api_keys
            ORDER BY created_at DESC
            """
        )

        return [
            APIKeyInfo(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                scopes=list(row["scopes"]),
                rate_limit=row["rate_limit"],
                created_at=row["created_at"],
                last_used_at=row["last_used_at"],
                expires_at=row["expires_at"],
                is_active=row["is_active"],
            )
            for row in rows
        ]


async def revoke_api_key(key_id: UUID) -> bool:
    """
    Revoke an API key.

    Args:
        key_id: ID of the key to revoke

    Returns:
        True if key was revoked, False if not found
    """
    db = await get_db()
    async with db.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE api_keys
            SET revoked_at = NOW()
            WHERE id = $1 AND revoked_at IS NULL
            """,
            key_id,
        )

        revoked = result == "UPDATE 1"

        if revoked:
            logger.info("api_key_revoked", key_id=str(key_id))
        else:
            logger.warning("api_key_revoke_failed", key_id=str(key_id))

        return revoked


async def get_api_key_by_id(key_id: UUID) -> APIKeyInfo | None:
    """
    Get API key info by ID.

    Args:
        key_id: ID of the key

    Returns:
        APIKeyInfo or None if not found
    """
    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, description, scopes, rate_limit,
                   created_at, last_used_at, expires_at,
                   (revoked_at IS NULL AND (expires_at IS NULL OR expires_at > NOW())) as is_active
            FROM api_keys
            WHERE id = $1
            """,
            key_id,
        )

        if not row:
            return None

        return APIKeyInfo(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            scopes=list(row["scopes"]),
            rate_limit=row["rate_limit"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
            expires_at=row["expires_at"],
            is_active=row["is_active"],
        )
