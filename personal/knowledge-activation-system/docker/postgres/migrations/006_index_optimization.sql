-- Migration: Database Index Optimization (P11)
-- Purpose: Optimize query performance with composite and partial indexes
-- Run: docker exec -i knowledge-db psql -U knowledge knowledge < docker/postgres/migrations/006_index_optimization.sql

-- ============================================================================
-- PRE-FLIGHT: Increase work memory for index builds
-- ============================================================================

-- Temporarily increase maintenance_work_mem for faster index creation
-- This helps with HNSW and GIN index builds
SET maintenance_work_mem = '256MB';

-- ============================================================================
-- CONTENT TABLE INDEXES
-- ============================================================================

-- Composite index for type + soft-delete filtering
-- Used by: content listing by type, type-based statistics
CREATE INDEX IF NOT EXISTS idx_content_type_deleted
    ON content(type, deleted_at)
    WHERE deleted_at IS NULL;

-- JSONB index for namespace filtering
-- Supports both exact match and prefix (LIKE) queries on metadata->>'namespace'
CREATE INDEX IF NOT EXISTS idx_content_metadata_namespace
    ON content((metadata->>'namespace'));

-- GIN index on full metadata JSONB for flexible queries
-- Enables efficient containment queries like metadata @> '{"key": "value"}'
CREATE INDEX IF NOT EXISTS idx_content_metadata_gin
    ON content USING GIN(metadata jsonb_path_ops);

-- Composite index for namespace + soft-delete (most common filter pattern)
-- Used by: BM25 search, vector search with namespace filter
CREATE INDEX IF NOT EXISTS idx_content_namespace_deleted
    ON content((COALESCE(metadata->>'namespace', 'default')), deleted_at)
    WHERE deleted_at IS NULL;

-- Partial index for active content only (common join pattern)
CREATE INDEX IF NOT EXISTS idx_content_active
    ON content(id)
    WHERE deleted_at IS NULL;

-- ============================================================================
-- CHUNKS TABLE INDEXES
-- ============================================================================

-- Note: UNIQUE(content_id, chunk_index) already creates implicit btree index
-- Adding explicit covering index for chunk lookups with text
CREATE INDEX IF NOT EXISTS idx_chunks_content_chunk
    ON chunks(content_id, chunk_index);

-- Partial index for chunks with embeddings (for vector search)
CREATE INDEX IF NOT EXISTS idx_chunks_has_embedding
    ON chunks(content_id)
    WHERE embedding IS NOT NULL;

-- ============================================================================
-- SEARCH_QUERIES TABLE INDEXES (if exists)
-- ============================================================================

-- Index for gap analysis queries (low result count)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'search_queries') THEN
        CREATE INDEX IF NOT EXISTS idx_search_queries_gaps
            ON search_queries(result_count, top_score)
            WHERE result_count = 0 OR top_score < 0.3;
    END IF;
END $$;

-- ============================================================================
-- REVIEW_QUEUE INDEXES
-- ============================================================================

-- Composite index for due reviews query
-- Optimizes: SELECT ... WHERE status = 'active' AND next_review <= NOW()
CREATE INDEX IF NOT EXISTS idx_review_queue_due
    ON review_queue(next_review, status)
    WHERE status = 'active' AND next_review IS NOT NULL;

-- ============================================================================
-- HNSW INDEX TUNING (if not already optimized)
-- ============================================================================

-- Note: HNSW index already exists in init.sql with m=24, ef_construction=128
-- These settings are good for 768-dim Nomic embeddings
-- To tune ef_search at query time, use: SET hnsw.ef_search = 100;

-- ============================================================================
-- ANALYZE TABLES
-- ============================================================================

-- Update statistics for query planner after adding indexes
ANALYZE content;
ANALYZE chunks;
ANALYZE review_queue;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON INDEX idx_content_type_deleted IS 'Composite index for type filtering on active content';
COMMENT ON INDEX idx_content_metadata_namespace IS 'B-tree index for namespace filtering from JSONB';
COMMENT ON INDEX idx_content_metadata_gin IS 'GIN index for flexible JSONB queries';
COMMENT ON INDEX idx_content_namespace_deleted IS 'Composite for namespace + soft-delete filtering';
COMMENT ON INDEX idx_content_active IS 'Partial index covering only non-deleted content';
COMMENT ON INDEX idx_chunks_content_chunk IS 'Composite for chunk lookups by content';
COMMENT ON INDEX idx_chunks_has_embedding IS 'Partial index for chunks with embeddings';
COMMENT ON INDEX idx_review_queue_due IS 'Composite for due review queries';

-- Reset maintenance_work_mem to default
RESET maintenance_work_mem;
