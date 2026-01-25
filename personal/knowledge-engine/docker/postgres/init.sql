-- Knowledge Engine PostgreSQL Schema
-- This file is run automatically when the PostgreSQL container starts

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Documents table (created by SQLAlchemy, but schema here for reference)
-- CREATE TABLE IF NOT EXISTS documents (
--     id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
--     namespace VARCHAR(255) NOT NULL,
--     title VARCHAR(1024),
--     document_type VARCHAR(50) NOT NULL,
--     source TEXT,
--     chunk_count INTEGER DEFAULT 0,
--     embedding_model VARCHAR(255),
--     metadata JSONB DEFAULT '{}',
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     is_deleted BOOLEAN DEFAULT FALSE
-- );

-- Indexes (created by SQLAlchemy, but listed for reference)
-- CREATE INDEX IF NOT EXISTS idx_documents_namespace ON documents(namespace);
-- CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
-- CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at);
-- CREATE INDEX IF NOT EXISTS idx_documents_deleted ON documents(is_deleted);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO knowledge_engine;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO knowledge_engine;
