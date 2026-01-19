-- Migration: 008_knowledge_graph.sql
-- Description: Add tables for knowledge graph entity extraction
-- Created: 2026-01-19

-- Entity extraction table
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,  -- technology, concept, tool, framework, organization, person
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for entity queries
CREATE INDEX IF NOT EXISTS idx_entities_content ON entities(content_id);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name_lower ON entities(LOWER(name));

-- Relationship table
CREATE TABLE IF NOT EXISTS relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,  -- uses, depends_on, implements, related_to, mentions
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for relationship queries
CREATE INDEX IF NOT EXISTS idx_rel_from ON relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_rel_to ON relationships(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(relation_type);

-- Unique constraint to prevent duplicate relationships
CREATE UNIQUE INDEX IF NOT EXISTS idx_rel_unique ON relationships(from_entity_id, to_entity_id, relation_type);

-- View for entity statistics
CREATE OR REPLACE VIEW entity_stats AS
SELECT
    entity_type,
    COUNT(*) as count,
    COUNT(DISTINCT name) as unique_names
FROM entities
GROUP BY entity_type
ORDER BY count DESC;

-- View for most connected entities
CREATE OR REPLACE VIEW connected_entities AS
SELECT
    e.name,
    e.entity_type,
    COUNT(DISTINCT CASE WHEN r.from_entity_id = e.id THEN r.to_entity_id END) +
    COUNT(DISTINCT CASE WHEN r.to_entity_id = e.id THEN r.from_entity_id END) as connection_count
FROM entities e
LEFT JOIN relationships r ON r.from_entity_id = e.id OR r.to_entity_id = e.id
GROUP BY e.id, e.name, e.entity_type
ORDER BY connection_count DESC;
