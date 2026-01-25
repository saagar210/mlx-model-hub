-- Universal Context Engine - Entity Tables

-- Entity registry
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    canonical_name TEXT NOT NULL UNIQUE,  -- Normalized canonical form
    display_name TEXT NOT NULL,           -- Human-readable form

    -- Classification
    entity_type TEXT NOT NULL,            -- technology, framework, database, file, person, project

    -- Aliases (for resolution)
    aliases TEXT[] DEFAULT '{}',

    -- Metadata
    description TEXT,
    metadata JSONB DEFAULT '{}',

    -- Statistics
    mention_count INTEGER DEFAULT 0,
    last_seen_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_aliases ON entities USING GIN(aliases);
CREATE INDEX IF NOT EXISTS idx_entities_mentions ON entities(mention_count DESC);

-- Entity relationships (for knowledge graph)
CREATE TABLE IF NOT EXISTS entity_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationship
    from_entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    to_entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,      -- uses, depends_on, related_to, part_of

    -- Bi-temporal
    t_valid TIMESTAMPTZ NOT NULL,         -- When relationship became true
    t_invalid TIMESTAMPTZ,                -- When relationship ended

    -- Confidence and provenance
    confidence FLOAT DEFAULT 1.0,
    source TEXT,                          -- Which adapter discovered this
    source_item_id UUID,                  -- Context item that established this

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(from_entity_id, to_entity_id, relationship_type, t_valid)
);

CREATE INDEX IF NOT EXISTS idx_relationships_from ON entity_relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON entity_relationships(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON entity_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_relationships_valid ON entity_relationships(t_valid DESC) WHERE t_invalid IS NULL;

-- Entity co-occurrence tracking
CREATE TABLE IF NOT EXISTS entity_cooccurrence (
    entity_a_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    entity_b_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    cooccurrence_count INTEGER DEFAULT 1,
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (entity_a_id, entity_b_id),
    CHECK (entity_a_id < entity_b_id)  -- Ensure consistent ordering
);

CREATE INDEX IF NOT EXISTS idx_cooccurrence_count ON entity_cooccurrence(cooccurrence_count DESC);

-- Auto-update timestamp trigger for entities
DROP TRIGGER IF EXISTS entities_updated_at ON entities;
CREATE TRIGGER entities_updated_at
    BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_context_updated_at();
