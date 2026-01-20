-- Knowledge Activation System - Database Schema
-- PostgreSQL 16 + pgvector + pgvectorscale

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;

-- ============================================================================
-- TABLES
-- ============================================================================

-- Content: Primary table for all ingested content
CREATE TABLE content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Obsidian link (source of truth)
    filepath TEXT UNIQUE NOT NULL,
    content_hash TEXT NOT NULL,

    -- Content metadata
    type TEXT NOT NULL CHECK (type IN ('youtube', 'bookmark', 'file', 'note')),
    url TEXT,
    title TEXT NOT NULL,
    summary TEXT,

    -- Tags
    auto_tags TEXT[] DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',

    -- Flexible metadata (thumbnails, duration, author, etc.)
    metadata JSONB DEFAULT '{}',

    -- Full-text search vector
    fts_vector tsvector,

    -- Error tracking for ingestion failures
    error_log TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    captured_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

-- Chunks: Chunked content with embeddings for semantic search
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES content(id) ON DELETE CASCADE,

    -- Chunk data
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,

    -- Embedding (Nomic Embed Text v1.5 = 768 dimensions)
    embedding vector(768),
    embedding_model TEXT DEFAULT 'nomic-embed-text',
    embedding_version TEXT DEFAULT 'v1.5',

    -- Source reference for citations
    source_ref TEXT,

    -- Character positions (for highlighting)
    start_char INTEGER,
    end_char INTEGER,

    UNIQUE(content_id, chunk_index)
);

-- Review Queue: FSRS spaced repetition state
CREATE TABLE review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES content(id) ON DELETE CASCADE UNIQUE,

    -- FSRS state (stability, difficulty, etc.)
    fsrs_state JSONB DEFAULT '{}',

    -- Review schedule
    next_review TIMESTAMPTZ,
    last_reviewed TIMESTAMPTZ,
    review_count INTEGER DEFAULT 0,

    -- Queue status
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'suspended'))
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Content indexes
CREATE INDEX idx_content_type ON content(type);
CREATE INDEX idx_content_tags ON content USING GIN(tags);
CREATE INDEX idx_content_auto_tags ON content USING GIN(auto_tags);
CREATE INDEX idx_content_fts ON content USING GIN(fts_vector);
CREATE INDEX idx_content_deleted ON content(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_content_url ON content(url) WHERE url IS NOT NULL;
CREATE INDEX idx_content_hash ON content(content_hash) WHERE deleted_at IS NULL;

-- Chunk indexes
-- HNSW index optimized for 768-dim Nomic embeddings
-- m=24: Better graph connectivity for improved recall
-- ef_construction=128: Higher build quality for better search accuracy
CREATE INDEX idx_chunks_embedding ON chunks USING hnsw(embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);
CREATE INDEX idx_chunks_content_id ON chunks(content_id);

-- Review queue indexes
CREATE INDEX idx_review_next ON review_queue(next_review) WHERE status = 'active';
CREATE INDEX idx_review_status ON review_queue(status);

-- Timestamp indexes for common queries
CREATE INDEX idx_content_created_at ON content(created_at DESC);
CREATE INDEX idx_content_captured_at ON content(captured_at DESC) WHERE captured_at IS NOT NULL;

-- Compound index for active review due date filtering
CREATE INDEX idx_review_active_next ON review_queue(status, next_review)
    WHERE status = 'active';

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update FTS vector on content insert/update
CREATE OR REPLACE FUNCTION update_fts_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fts_vector := to_tsvector('english',
        COALESCE(NEW.title, '') || ' ' ||
        COALESCE(NEW.summary, '') || ' ' ||
        COALESCE(array_to_string(NEW.tags, ' '), '') || ' ' ||
        COALESCE(array_to_string(NEW.auto_tags, ' '), '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER content_fts_update
    BEFORE INSERT OR UPDATE ON content
    FOR EACH ROW
    EXECUTE FUNCTION update_fts_vector();

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER content_updated_at
    BEFORE UPDATE ON content
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Validate FSRS state structure before insert/update
CREATE OR REPLACE FUNCTION validate_fsrs_state()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow NULL fsrs_state (will use defaults)
    IF NEW.fsrs_state IS NULL THEN
        RETURN NEW;
    END IF;

    -- Ensure fsrs_state has required fields
    IF NOT (
        NEW.fsrs_state ? 'state' AND
        NEW.fsrs_state ? 'stability' AND
        NEW.fsrs_state ? 'difficulty'
    ) THEN
        RAISE EXCEPTION 'Invalid FSRS state: missing required fields (state, stability, difficulty)';
    END IF;

    -- Validate state is between 0-3 (FSRS State enum: New=0, Learning=1, Review=2, Relearning=3)
    IF (NEW.fsrs_state->>'state')::int NOT BETWEEN 0 AND 3 THEN
        RAISE EXCEPTION 'Invalid FSRS state value: must be 0-3, got %', NEW.fsrs_state->>'state';
    END IF;

    -- Validate stability is non-negative
    IF (NEW.fsrs_state->>'stability')::numeric < 0 THEN
        RAISE EXCEPTION 'Invalid FSRS stability: must be non-negative';
    END IF;

    -- Validate difficulty is between 0-10
    IF (NEW.fsrs_state->>'difficulty')::numeric < 0 OR (NEW.fsrs_state->>'difficulty')::numeric > 10 THEN
        RAISE EXCEPTION 'Invalid FSRS difficulty: must be between 0 and 10';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER validate_fsrs_state_trigger
    BEFORE INSERT OR UPDATE ON review_queue
    FOR EACH ROW
    EXECUTE FUNCTION validate_fsrs_state();

-- Ensure review schedule is logical
ALTER TABLE review_queue
    ADD CONSTRAINT valid_review_schedule
    CHECK (next_review IS NULL OR last_reviewed IS NULL OR next_review >= last_reviewed);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE content IS 'Primary table for all ingested content. Links to Obsidian notes via filepath.';
COMMENT ON TABLE chunks IS 'Chunked content with embeddings for semantic search.';
COMMENT ON TABLE review_queue IS 'FSRS spaced repetition state for active engagement.';
COMMENT ON COLUMN content.filepath IS 'Path to Obsidian note - source of truth';
COMMENT ON COLUMN content.content_hash IS 'SHA256 for change detection';
COMMENT ON COLUMN chunks.embedding IS 'Nomic Embed Text v1.5 (768 dimensions)';
COMMENT ON COLUMN chunks.source_ref IS 'Citation reference e.g. "timestamp:3:45" or "page:12"';
