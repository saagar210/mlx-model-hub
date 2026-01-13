-- Migration: Expand content types for Knowledge Seeder integration
-- Run this after initial schema setup

-- Drop the existing constraint
ALTER TABLE content DROP CONSTRAINT IF EXISTS content_type_check;

-- Add new constraint with expanded types
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
        'paper'          -- Academic papers (arXiv, etc.)
    ));

-- Add comment
COMMENT ON COLUMN content.type IS 'Content type: youtube, bookmark, file, note, research, documentation, tutorial, paper';
