-- Universal Context Engine - Sync State Tracking

-- Sync state tracking for incremental sync
CREATE TABLE IF NOT EXISTS sync_state (
    source TEXT PRIMARY KEY,

    -- Cursor for incremental sync
    last_sync_cursor TEXT,               -- Source-specific cursor (timestamp, ID, etc.)
    last_sync_at TIMESTAMPTZ,

    -- Statistics
    items_synced INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    sync_status TEXT DEFAULT 'idle',     -- idle, running, error
    error_message TEXT,
    last_error_at TIMESTAMPTZ,

    -- Configuration
    sync_interval_seconds INTEGER DEFAULT 300,
    enabled BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sync history for debugging
CREATE TABLE IF NOT EXISTS sync_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,                -- success, error, cancelled
    items_processed INTEGER DEFAULT 0,
    items_created INTEGER DEFAULT 0,
    items_updated INTEGER DEFAULT 0,
    items_skipped INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sync_history_source ON sync_history(source, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_history_status ON sync_history(status) WHERE status = 'error';

-- Auto-update timestamp trigger for sync_state
DROP TRIGGER IF EXISTS sync_state_updated_at ON sync_state;
CREATE TRIGGER sync_state_updated_at
    BEFORE UPDATE ON sync_state
    FOR EACH ROW EXECUTE FUNCTION update_context_updated_at();
