# Database Schema

## Extensions

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale;
```

## Tables

### content

Primary table for all ingested content. Links to Obsidian notes via `filepath`.

```sql
CREATE TABLE content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Obsidian link (source of truth)
    filepath TEXT UNIQUE NOT NULL,           -- Path to Obsidian note
    content_hash TEXT NOT NULL,              -- SHA256 for change detection

    -- Content metadata
    type TEXT NOT NULL CHECK (type IN ('youtube', 'bookmark', 'file', 'note')),
    url TEXT,                                -- Original URL (if applicable)
    title TEXT NOT NULL,
    summary TEXT,                            -- AI-generated summary

    -- Tags
    auto_tags TEXT[] DEFAULT '{}',           -- AI-generated tags
    tags TEXT[] DEFAULT '{}',                -- Manual tags (from YAML)

    -- Flexible metadata (thumbnails, duration, author, etc.)
    metadata JSONB DEFAULT '{}',

    -- Full-text search vector
    fts_vector tsvector,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    captured_at TIMESTAMPTZ,                 -- When originally saved/watched
    deleted_at TIMESTAMPTZ                   -- Soft delete
);
```

### chunks

Chunked content with embeddings for semantic search.

```sql
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id UUID REFERENCES content(id) ON DELETE CASCADE,

    -- Chunk data
    chunk_index INTEGER NOT NULL,            -- Order within document
    chunk_text TEXT NOT NULL,

    -- Embedding
    embedding vector(768),                   -- Nomic Embed Text v1.5
    embedding_model TEXT DEFAULT 'nomic-embed-text-v1.5',

    -- Source reference for citations
    source_ref TEXT,                         -- e.g., "timestamp:3:45" or "page:12"

    -- Character positions (for highlighting)
    start_char INTEGER,
    end_char INTEGER,

    UNIQUE(content_id, chunk_index)
);
```

### review_queue

FSRS spaced repetition state for active engagement.

```sql
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
```

## Indexes

### Content Indexes

```sql
-- Filter by type
CREATE INDEX idx_content_type ON content(type);

-- Tag search (GIN for array containment)
CREATE INDEX idx_content_tags ON content USING GIN(tags);
CREATE INDEX idx_content_auto_tags ON content USING GIN(auto_tags);

-- Full-text search
CREATE INDEX idx_content_fts ON content USING GIN(fts_vector);

-- Soft delete filter
CREATE INDEX idx_content_deleted ON content(deleted_at) WHERE deleted_at IS NULL;

-- URL lookup
CREATE INDEX idx_content_url ON content(url) WHERE url IS NOT NULL;
```

### Chunk Indexes

```sql
-- Vector similarity search (StreamingDiskANN via pgvectorscale)
CREATE INDEX idx_chunks_embedding ON chunks USING diskann(embedding);

-- Fast lookup by content
CREATE INDEX idx_chunks_content_id ON chunks(content_id);
```

### Review Queue Indexes

```sql
-- Get due reviews efficiently
CREATE INDEX idx_review_next ON review_queue(next_review) WHERE status = 'active';

-- Filter by status
CREATE INDEX idx_review_status ON review_queue(status);
```

## Triggers

### Auto-update FTS vector

```sql
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
```

### Auto-update timestamps

```sql
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
```

## Example Queries

### Hybrid Search (BM25 + Vector with RRF)

```sql
-- BM25 search
WITH bm25_results AS (
    SELECT id, ts_rank_cd(fts_vector, query) AS rank
    FROM content, plainto_tsquery('english', $1) query
    WHERE fts_vector @@ query AND deleted_at IS NULL
    ORDER BY rank DESC
    LIMIT 50
),

-- Vector search
vector_results AS (
    SELECT c.content_id AS id,
           1 - (c.embedding <=> $2::vector) AS rank
    FROM chunks c
    JOIN content ct ON c.content_id = ct.id
    WHERE ct.deleted_at IS NULL
    ORDER BY c.embedding <=> $2::vector
    LIMIT 50
),

-- RRF fusion
rrf_scores AS (
    SELECT id, SUM(1.0 / (60 + row_num)) AS score
    FROM (
        SELECT id, ROW_NUMBER() OVER (ORDER BY rank DESC) AS row_num FROM bm25_results
        UNION ALL
        SELECT id, ROW_NUMBER() OVER (ORDER BY rank DESC) AS row_num FROM vector_results
    ) combined
    GROUP BY id
)

SELECT c.*, rrf.score
FROM content c
JOIN rrf_scores rrf ON c.id = rrf.id
ORDER BY rrf.score DESC
LIMIT 10;
```

### Get Due Reviews

```sql
SELECT c.*, rq.fsrs_state, rq.review_count
FROM review_queue rq
JOIN content c ON rq.content_id = c.id
WHERE rq.status = 'active'
  AND rq.next_review <= NOW()
  AND c.deleted_at IS NULL
ORDER BY rq.next_review ASC
LIMIT 20;
```

### Content by Type with Tags

```sql
SELECT * FROM content
WHERE type = 'youtube'
  AND tags @> ARRAY['machine-learning']
  AND deleted_at IS NULL
ORDER BY captured_at DESC
LIMIT 20;
```
