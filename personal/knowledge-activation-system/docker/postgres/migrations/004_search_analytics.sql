-- Migration: Search Analytics for query logging and gap analysis
-- Run: docker exec -i knowledge-db psql -U knowledge knowledge < docker/postgres/migrations/004_search_analytics.sql

-- Search queries table
CREATE TABLE IF NOT EXISTS search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    query_hash TEXT NOT NULL,  -- For deduplication
    namespace TEXT,
    result_count INTEGER NOT NULL DEFAULT 0,
    top_score REAL,
    avg_score REAL,
    reranked BOOLEAN NOT NULL DEFAULT FALSE,
    source TEXT DEFAULT 'api',  -- api, mcp, cli
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for analytics queries
CREATE INDEX IF NOT EXISTS idx_search_queries_created_at ON search_queries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_queries_hash ON search_queries(query_hash);
CREATE INDEX IF NOT EXISTS idx_search_queries_low_score ON search_queries(top_score) WHERE top_score < 0.3;

-- Search gaps view - queries with poor results
CREATE OR REPLACE VIEW search_gaps AS
SELECT
    query_text,
    COUNT(*) as search_count,
    AVG(result_count) as avg_results,
    AVG(top_score) as avg_top_score,
    MAX(created_at) as last_searched
FROM search_queries
WHERE result_count = 0 OR top_score < 0.3
GROUP BY query_text
ORDER BY search_count DESC, avg_top_score ASC;

-- Popular queries view
CREATE OR REPLACE VIEW popular_queries AS
SELECT
    query_text,
    COUNT(*) as search_count,
    AVG(result_count) as avg_results,
    AVG(top_score) as avg_top_score,
    MAX(created_at) as last_searched
FROM search_queries
GROUP BY query_text
HAVING COUNT(*) > 1
ORDER BY search_count DESC
LIMIT 100;

-- Comments
COMMENT ON TABLE search_queries IS 'Search query log for analytics and gap analysis';
COMMENT ON VIEW search_gaps IS 'Queries with poor results for content gap identification';
COMMENT ON VIEW popular_queries IS 'Frequently searched queries';
