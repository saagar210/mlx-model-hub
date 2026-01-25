#!/usr/bin/env python3
"""Seed database with sample data for testing."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import asyncpg

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uce.core.config import settings


async def seed_data() -> None:
    """Insert sample data into the database."""
    db_url = settings.database_url.replace("+asyncpg", "")

    print("Connecting to database...")
    conn = await asyncpg.connect(db_url)

    try:
        # Sample entities
        entities = [
            ("oauth", "OAuth", "technology", ["oauth2", "oauth 2.0"]),
            ("fastapi", "FastAPI", "framework", ["fast-api"]),
            ("postgresql", "PostgreSQL", "database", ["postgres", "pg"]),
            ("python", "Python", "language", ["py", "python3"]),
            ("typescript", "TypeScript", "language", ["ts"]),
            ("claude_code", "Claude Code", "tool", ["cc"]),
        ]

        print("Inserting sample entities...")
        for canonical, display, etype, aliases in entities:
            await conn.execute(
                """
                INSERT INTO entities (id, canonical_name, display_name, entity_type, aliases, mention_count)
                VALUES ($1, $2, $3, $4, $5, 1)
                ON CONFLICT (canonical_name) DO NOTHING
                """,
                uuid4(),
                canonical,
                display,
                etype,
                aliases,
            )

        # Sample context items
        items = [
            ("kas", "document_chunk", "OAuth 2.0 Implementation Guide",
             "This guide explains how to implement OAuth 2.0 authentication in your FastAPI application using JWT tokens.",
             ["oauth", "fastapi"]),
            ("kas", "document_chunk", "PostgreSQL Performance Tuning",
             "Learn how to optimize your PostgreSQL database queries and indexes for better performance.",
             ["postgresql"]),
            ("git", "git_commit", "[claude-code] Add new search feature",
             "Implemented hybrid search combining vector similarity and BM25 full-text search.",
             ["claude_code"]),
            ("git", "git_commit", "[knowledge-engine] Fix sync issue",
             "Fixed incremental sync cursor not being updated after successful sync.",
             []),
        ]

        print("Inserting sample context items...")
        for source, ctype, title, content, entity_names in items:
            await conn.execute(
                """
                INSERT INTO context_items (
                    id, source, source_id, content_type, title, content,
                    content_hash, t_valid, entities, relevance
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                uuid4(),
                source,
                f"sample_{uuid4().hex[:8]}",
                ctype,
                title,
                content,
                uuid4().hex[:16],
                datetime.utcnow() - timedelta(hours=2),
                entity_names,
                {"recency": 0.8, "frequency": 0.0, "source_quality": 0.9, "explicit_relevance": 0.0},
            )

        # Initialize sync state
        print("Initializing sync state...")
        for source in ["kas", "git", "browser"]:
            await conn.execute(
                """
                INSERT INTO sync_state (source, sync_status, enabled)
                VALUES ($1, 'idle', true)
                ON CONFLICT (source) DO NOTHING
                """,
                source,
            )

        print("Seed data inserted successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_data())
