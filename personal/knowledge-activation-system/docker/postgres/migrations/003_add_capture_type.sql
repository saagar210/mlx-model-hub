-- Migration: Add capture type for quick capture webhook
-- Run: docker exec -i kas-postgres psql -U kas kas < docker/postgres/migrations/003_add_capture_type.sql

-- Drop the existing constraint
ALTER TABLE content DROP CONSTRAINT IF EXISTS content_type_check;

-- Add new constraint with capture type
ALTER TABLE content ADD CONSTRAINT content_type_check
    CHECK (type IN (
        -- Original types
        'youtube',
        'bookmark',
        'file',
        'note',
        -- Extended types for Knowledge Seeder
        'research',      -- Research reports
        'documentation', -- Technical documentation
        'tutorial',      -- Tutorials and guides
        'paper',         -- Academic papers
        -- Quick capture types
        'capture',       -- Quick captures from webhooks
        'pattern',       -- Code patterns
        'decision'       -- Architecture decisions
    ));

-- Add comment
COMMENT ON COLUMN content.type IS 'Content type: youtube, bookmark, file, note, research, documentation, tutorial, paper, capture, pattern, decision';
