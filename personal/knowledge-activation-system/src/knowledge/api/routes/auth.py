"""Authentication routes (P17: Authentication System)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from knowledge.api.auth import (
    APIKey,
    APIKeyInfo,
    CreateKeyRequest,
    CreateKeyResponse,
    create_api_key_record,
    get_api_key,
    get_api_key_by_id,
    list_api_keys,
    require_admin,
    revoke_api_key,
)
from knowledge.exceptions import NotFoundError
from knowledge.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# Schemas
# =============================================================================


class CurrentUserResponse(BaseModel):
    """Response for current user/key info."""

    authenticated: bool
    key_id: UUID | None = None
    key_name: str | None = None
    scopes: list[str] = []


class RevokeKeyResponse(BaseModel):
    """Response after revoking a key."""

    id: UUID
    revoked: bool
    revoked_at: datetime | None


# =============================================================================
# Routes
# =============================================================================


@router.get("/me")
async def get_current_user(
    api_key: APIKey | None = Depends(get_api_key),  # noqa: B008
) -> CurrentUserResponse:
    """
    Get information about the current API key.

    Returns:
        Current user/key information
    """
    if api_key is None:
        return CurrentUserResponse(authenticated=False)

    return CurrentUserResponse(
        authenticated=True,
        key_id=api_key.id,
        key_name=api_key.name,
        scopes=api_key.scopes,
    )


@router.post("/keys", dependencies=[Depends(require_admin())])
async def create_key(request: CreateKeyRequest) -> CreateKeyResponse:
    """
    Create a new API key.

    Requires admin scope.

    **Important:** The returned `key` is only shown once. Store it securely.

    Args:
        request: Key creation parameters

    Returns:
        Created key information including the plaintext key
    """
    key, key_id = await create_api_key_record(
        name=request.name,
        description=request.description,
        scopes=request.scopes,
        rate_limit=request.rate_limit,
        expires_in_days=request.expires_in_days,
    )

    # Calculate expiration if set
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=request.expires_in_days)

    logger.info(
        "api_key_created_via_api",
        key_id=str(key_id),
        name=request.name,
    )

    return CreateKeyResponse(
        id=key_id,
        name=request.name,
        key=key,
        scopes=request.scopes,
        rate_limit=request.rate_limit,
        expires_at=expires_at,
    )


@router.get("/keys", dependencies=[Depends(require_admin())])
async def list_keys() -> list[APIKeyInfo]:
    """
    List all API keys.

    Requires admin scope.

    Returns:
        List of all API keys (without sensitive data)
    """
    return await list_api_keys()


@router.get("/keys/{key_id}", dependencies=[Depends(require_admin())])
async def get_key(key_id: UUID) -> APIKeyInfo:
    """
    Get information about a specific API key.

    Requires admin scope.

    Args:
        key_id: ID of the key to retrieve

    Returns:
        API key information
    """
    key_info = await get_api_key_by_id(key_id)
    if not key_info:
        raise NotFoundError("API key not found", details={"key_id": str(key_id)})
    return key_info


@router.delete("/keys/{key_id}", dependencies=[Depends(require_admin())])
async def revoke_key(key_id: UUID) -> RevokeKeyResponse:
    """
    Revoke an API key.

    Requires admin scope. This action is irreversible.

    Args:
        key_id: ID of the key to revoke

    Returns:
        Revocation status
    """
    revoked = await revoke_api_key(key_id)

    if not revoked:
        # Check if key exists
        key_info = await get_api_key_by_id(key_id)
        if not key_info:
            raise NotFoundError("API key not found", details={"key_id": str(key_id)})
        # Key exists but already revoked
        return RevokeKeyResponse(
            id=key_id,
            revoked=False,
            revoked_at=None,
        )

    return RevokeKeyResponse(
        id=key_id,
        revoked=True,
        revoked_at=datetime.now(UTC),
    )
