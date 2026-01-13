-- Migration: 007_api_keys
-- Description: API keys table for authentication (P17)
-- Date: 2026-01-13

-- =============================================================================
-- API Keys Table
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    scopes TEXT[] DEFAULT '{read}',
    rate_limit INTEGER DEFAULT 100,  -- requests per minute
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_by TEXT,  -- for audit trail
    metadata JSONB DEFAULT '{}'
);

-- Index for fast lookup by hash (only active keys)
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)
    WHERE revoked_at IS NULL;

-- Index for listing active keys
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(created_at DESC)
    WHERE revoked_at IS NULL;

-- Index for expiring keys cleanup
CREATE INDEX IF NOT EXISTS idx_api_keys_expires ON api_keys(expires_at)
    WHERE expires_at IS NOT NULL AND revoked_at IS NULL;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE api_keys IS 'API keys for authentication. Keys are stored as SHA256 hashes.';
COMMENT ON COLUMN api_keys.key_hash IS 'SHA256 hash of the API key';
COMMENT ON COLUMN api_keys.scopes IS 'Array of allowed scopes: read, write, admin';
COMMENT ON COLUMN api_keys.rate_limit IS 'Requests per minute limit for this key';
COMMENT ON COLUMN api_keys.expires_at IS 'Optional expiration timestamp';
COMMENT ON COLUMN api_keys.revoked_at IS 'When key was revoked (NULL = active)';
