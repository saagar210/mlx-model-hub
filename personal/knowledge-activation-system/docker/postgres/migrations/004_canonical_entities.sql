-- Migration 004: Canonical entities for deduplication
-- Run: psql -U knowledge -d knowledge -f docker/postgres/migrations/004_canonical_entities.sql

-- Canonical entities table - stores unique entities
CREATE TABLE IF NOT EXISTS canonical_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,                    -- Canonical display name (preserved casing)
    normalized_name TEXT NOT NULL,         -- Lowercase normalized for matching
    entity_type TEXT NOT NULL,             -- technology, concept, person, etc.
    aliases TEXT[] DEFAULT '{}',           -- Alternative names/spellings
    description TEXT,                      -- Optional description
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(normalized_name, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_canonical_entities_norm ON canonical_entities(normalized_name);
CREATE INDEX IF NOT EXISTS idx_canonical_entities_type ON canonical_entities(entity_type);

-- Add canonical_entity_id to entities table (nullable for migration)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'entities' AND column_name = 'canonical_entity_id'
    ) THEN
        ALTER TABLE entities ADD COLUMN canonical_entity_id UUID REFERENCES canonical_entities(id);
        CREATE INDEX idx_entities_canonical ON entities(canonical_entity_id);
    END IF;
END $$;

-- Function to normalize entity names
CREATE OR REPLACE FUNCTION normalize_entity_name(name TEXT) RETURNS TEXT AS $$
BEGIN
    -- Lowercase, trim whitespace, collapse multiple spaces
    RETURN LOWER(TRIM(REGEXP_REPLACE(name, '\s+', ' ', 'g')));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Populate canonical_entities from existing entities
INSERT INTO canonical_entities (name, normalized_name, entity_type)
SELECT DISTINCT ON (normalize_entity_name(name), entity_type)
    name,
    normalize_entity_name(name),
    entity_type
FROM entities
ON CONFLICT (normalized_name, entity_type) DO NOTHING;

-- Link existing entities to their canonical versions
UPDATE entities e
SET canonical_entity_id = ce.id
FROM canonical_entities ce
WHERE normalize_entity_name(e.name) = ce.normalized_name
  AND e.entity_type = ce.entity_type
  AND e.canonical_entity_id IS NULL;

-- View for entity statistics with canonical grouping
CREATE OR REPLACE VIEW entity_stats_canonical AS
SELECT
    ce.id,
    ce.name,
    ce.entity_type,
    COUNT(DISTINCT e.content_id) as content_count,
    COUNT(e.id) as mention_count,
    AVG(e.confidence) as avg_confidence
FROM canonical_entities ce
LEFT JOIN entities e ON e.canonical_entity_id = ce.id
GROUP BY ce.id, ce.name, ce.entity_type
ORDER BY content_count DESC;
