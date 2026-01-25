-- Universal Context Engine - Initial Schema
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Unified context items table
CREATE TABLE IF NOT EXISTS context_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Source identification
    source TEXT NOT NULL,                -- kas, git, browser, localcrew
    source_id TEXT,                      -- Original ID in source system
    source_url TEXT,                     -- URL/path to original

    -- Content
    content_type TEXT NOT NULL,          -- document_chunk, git_commit, page_content, agent_output
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,          -- SHA256 for deduplication

    -- Vector embedding (768d nomic-embed-text)
    embedding vector(768),

    -- Bi-temporal metadata
    t_valid TIMESTAMPTZ NOT NULL,        -- When the fact became true in real world
    t_invalid TIMESTAMPTZ,               -- When the fact stopped being true (NULL = still valid)
    t_created TIMESTAMPTZ DEFAULT NOW(), -- When ingested into UCE
    t_expired TIMESTAMPTZ,               -- When superseded by newer version

    -- Expiration (for ephemeral context like browser tabs)
    expires_at TIMESTAMPTZ,

    -- Entity links (denormalized for fast filtering)
    entities TEXT[] DEFAULT '{}',        -- Extracted entity names
    entity_ids UUID[] DEFAULT '{}',      -- Links to entities table

    -- Classification
    tags TEXT[] DEFAULT '{}',
    namespace TEXT DEFAULT 'default',    -- For multi-tenant/project isolation

    -- Relevance signals (JSONB for flexibility)
    relevance JSONB DEFAULT '{
        "recency": 0.5,
        "frequency": 0.0,
        "source_quality": 0.8,
        "explicit_relevance": 0.0
    }',

    -- Flexible metadata
    metadata JSONB DEFAULT '{}',

    -- Full-text search vector
    fts_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(content, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(array_to_string(tags, ' '), '')), 'C')
    ) STORED,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    UNIQUE(source, source_id) WHERE source_id IS NOT NULL
);

-- Indexes for context_items
CREATE INDEX IF NOT EXISTS idx_context_source ON context_items(source);
CREATE INDEX IF NOT EXISTS idx_context_type ON context_items(content_type);
CREATE INDEX IF NOT EXISTS idx_context_hash ON context_items(content_hash);
CREATE INDEX IF NOT EXISTS idx_context_t_valid ON context_items(t_valid DESC);
CREATE INDEX IF NOT EXISTS idx_context_expires ON context_items(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_context_entities ON context_items USING GIN(entities);
CREATE INDEX IF NOT EXISTS idx_context_entity_ids ON context_items USING GIN(entity_ids);
CREATE INDEX IF NOT EXISTS idx_context_tags ON context_items USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_context_fts ON context_items USING GIN(fts_vector);
CREATE INDEX IF NOT EXISTS idx_context_namespace ON context_items(namespace);
CREATE INDEX IF NOT EXISTS idx_context_active ON context_items(source, t_created DESC)
    WHERE t_expired IS NULL AND (expires_at IS NULL OR expires_at > NOW());

-- Vector index (using IVFFlat for now, can upgrade to DiskANN later)
CREATE INDEX IF NOT EXISTS idx_context_embedding ON context_items USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION update_context_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS context_items_updated_at ON context_items;
CREATE TRIGGER context_items_updated_at
    BEFORE UPDATE ON context_items
    FOR EACH ROW EXECUTE FUNCTION update_context_updated_at();
