-- Migration: Content Quality Scoring
-- Run: docker exec -i knowledge-db psql -U knowledge knowledge < docker/postgres/migrations/005_content_quality.sql

-- Add quality_score column
ALTER TABLE content ADD COLUMN IF NOT EXISTS quality_score REAL DEFAULT NULL;

-- Index for quality-boosted searches
CREATE INDEX IF NOT EXISTS idx_content_quality ON content(quality_score DESC NULLS LAST);

-- Content quality metrics view
CREATE OR REPLACE VIEW content_quality_metrics AS
SELECT
    c.id,
    c.title,
    c.type,
    c.created_at,
    c.quality_score,
    -- Compute metrics
    LENGTH(COALESCE(c.summary, '')) as summary_length,
    COALESCE(array_length(c.tags, 1), 0) as tag_count,
    CASE WHEN c.url IS NOT NULL THEN 1 ELSE 0 END as has_source,
    (SELECT COUNT(*) FROM chunks WHERE content_id = c.id) as chunk_count,
    -- Computed score if not set
    CASE
        WHEN c.quality_score IS NOT NULL THEN c.quality_score
        ELSE (
            -- Base score
            0.5
            -- Length bonus (up to 0.2)
            + LEAST(LENGTH(COALESCE(c.summary, '')) / 1000.0, 0.2)
            -- Tag bonus (up to 0.15)
            + LEAST(COALESCE(array_length(c.tags, 1), 0) * 0.03, 0.15)
            -- Source bonus
            + CASE WHEN c.url IS NOT NULL THEN 0.1 ELSE 0 END
            -- Chunk penalty for too few
            - CASE WHEN (SELECT COUNT(*) FROM chunks WHERE content_id = c.id) < 2 THEN 0.1 ELSE 0 END
        )
    END as computed_quality
FROM content c
WHERE c.deleted_at IS NULL;

-- Function to compute quality score for a content item
CREATE OR REPLACE FUNCTION compute_content_quality(content_uuid UUID)
RETURNS REAL AS $$
DECLARE
    base_score REAL := 0.5;
    summary_bonus REAL;
    tag_bonus REAL;
    source_bonus REAL;
    chunk_penalty REAL;
    final_score REAL;
BEGIN
    SELECT
        -- Summary length bonus (up to 0.2)
        LEAST(LENGTH(COALESCE(c.summary, '')) / 1000.0, 0.2),
        -- Tag bonus (up to 0.15)
        LEAST(COALESCE(array_length(c.tags, 1), 0) * 0.03, 0.15),
        -- Source URL bonus
        CASE WHEN c.url IS NOT NULL THEN 0.1 ELSE 0 END,
        -- Chunk penalty
        CASE WHEN (SELECT COUNT(*) FROM chunks WHERE content_id = c.id) < 2 THEN 0.1 ELSE 0 END
    INTO summary_bonus, tag_bonus, source_bonus, chunk_penalty
    FROM content c
    WHERE c.id = content_uuid;

    final_score := base_score + summary_bonus + tag_bonus + source_bonus - chunk_penalty;

    -- Clamp to 0-1
    RETURN GREATEST(0, LEAST(1, final_score));
END;
$$ LANGUAGE plpgsql;

-- Update quality scores for all content
-- (Run separately as it may take time for large datasets)
-- UPDATE content SET quality_score = compute_content_quality(id) WHERE deleted_at IS NULL;

COMMENT ON COLUMN content.quality_score IS 'Quality score 0-1, computed from metadata completeness, content length, etc.';
COMMENT ON VIEW content_quality_metrics IS 'Content quality metrics for analysis and debugging';
COMMENT ON FUNCTION compute_content_quality IS 'Compute quality score for a content item based on metadata and structure';
