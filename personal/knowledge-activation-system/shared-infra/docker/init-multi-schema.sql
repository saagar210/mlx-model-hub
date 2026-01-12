-- Multi-schema PostgreSQL initialization for KAS ecosystem
-- This script sets up separate schemas for KAS and LocalCrew
-- in a single PostgreSQL instance.

-- Create extensions in public schema (shared)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- KAS Schema (Knowledge Activation System)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS kas;

-- Create KAS user with access to kas schema
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'kas') THEN
        CREATE ROLE kas WITH LOGIN PASSWORD 'kas_localdev';
    END IF;
END$$;

GRANT USAGE ON SCHEMA kas TO kas;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA kas TO kas;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kas TO kas;
ALTER DEFAULT PRIVILEGES IN SCHEMA kas GRANT ALL ON TABLES TO kas;
ALTER DEFAULT PRIVILEGES IN SCHEMA kas GRANT ALL ON SEQUENCES TO kas;

-- Grant access to vector extension
GRANT USAGE ON SCHEMA public TO kas;

-- Set default search path for KAS user
ALTER ROLE kas SET search_path TO kas, public;

-- KAS Tables
SET search_path TO kas, public;

CREATE TABLE IF NOT EXISTS content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filepath TEXT NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('youtube', 'bookmark', 'note', 'pdf', 'file', 'research', 'pattern')),
    title TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    tags TEXT[] DEFAULT '{}',
    content_hash VARCHAR(64) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(768),
    source_ref TEXT,
    start_char INTEGER,
    end_char INTEGER,
    UNIQUE(content_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS review_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE UNIQUE,
    fsrs_state JSONB NOT NULL,
    next_review TIMESTAMPTZ NOT NULL,
    last_reviewed TIMESTAMPTZ,
    review_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'suspended'))
);

-- Indexes for KAS
CREATE INDEX IF NOT EXISTS idx_content_type ON content(type);
CREATE INDEX IF NOT EXISTS idx_content_deleted ON content(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_content_tags ON content USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_chunks_content_id ON chunks(content_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_review_next ON review_queue(next_review) WHERE status = 'active';

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_content_fts ON content USING GIN(
    to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(summary, ''))
);


-- =============================================================================
-- LocalCrew Schema
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS localcrew;

-- Create LocalCrew user with access to localcrew schema
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'localcrew') THEN
        CREATE ROLE localcrew WITH LOGIN PASSWORD 'localcrew_localdev';
    END IF;
END$$;

GRANT USAGE ON SCHEMA localcrew TO localcrew;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA localcrew TO localcrew;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA localcrew TO localcrew;
ALTER DEFAULT PRIVILEGES IN SCHEMA localcrew GRANT ALL ON TABLES TO localcrew;
ALTER DEFAULT PRIVILEGES IN SCHEMA localcrew GRANT ALL ON SEQUENCES TO localcrew;

-- Set default search path for LocalCrew user
ALTER ROLE localcrew SET search_path TO localcrew, public;

-- LocalCrew Tables
SET search_path TO localcrew, public;

CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    crew_type VARCHAR(50) NOT NULL,
    config JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID REFERENCES workflows(id),
    crew_type VARCHAR(50) NOT NULL,
    input_text TEXT NOT NULL,
    input_config JSONB,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'review_required')),
    output JSONB,
    error_message VARCHAR(2000),
    confidence_score INTEGER CHECK (confidence_score >= 0 AND confidence_score <= 100),
    duration_ms INTEGER,
    model_used VARCHAR(100),
    tokens_used INTEGER,
    kas_content_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    decision VARCHAR(20) DEFAULT 'pending' CHECK (decision IN ('pending', 'approved', 'modified', 'rejected', 'rerun')),
    confidence_score INTEGER NOT NULL,
    original_content JSONB NOT NULL,
    modified_content JSONB,
    feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ
);

-- Indexes for LocalCrew
CREATE INDEX IF NOT EXISTS idx_executions_workflow ON executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
CREATE INDEX IF NOT EXISTS idx_executions_created ON executions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_execution ON reviews(execution_id);
CREATE INDEX IF NOT EXISTS idx_reviews_decision ON reviews(decision);


-- =============================================================================
-- Cross-schema access (optional, for future integration)
-- =============================================================================

-- Allow LocalCrew to read from KAS (for context retrieval)
GRANT USAGE ON SCHEMA kas TO localcrew;
GRANT SELECT ON kas.content TO localcrew;
GRANT SELECT ON kas.chunks TO localcrew;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Multi-schema initialization complete';
    RAISE NOTICE 'KAS schema: kas.* (user: kas)';
    RAISE NOTICE 'LocalCrew schema: localcrew.* (user: localcrew)';
END$$;
