#!/usr/bin/env python3
"""Fix embedding quality by removing duplicates and re-embedding without YAML."""

import asyncio
import argparse
import re
from pathlib import Path

from knowledge.db import get_db
from knowledge.chunking import ChunkingConfig, chunk_recursive
from knowledge.embeddings import embed_text


YAML_FRONTMATTER_PATTERN = re.compile(r'^---\n.*?\n---\n\n?', re.DOTALL)


async def analyze_issues(conn) -> dict:
    """Analyze duplicate and YAML issues."""
    # File duplicates of bookmarks
    file_dups = await conn.fetchval("""
        SELECT COUNT(DISTINCT f.id)
        FROM content f
        JOIN content b ON f.title = b.title
        WHERE f.type = 'file' AND b.type = 'bookmark'
    """)

    chunks_in_dups = await conn.fetchval("""
        SELECT COUNT(*)
        FROM chunks ch
        WHERE ch.content_id IN (
            SELECT f.id
            FROM content f
            JOIN content b ON f.title = b.title
            WHERE f.type = 'file' AND b.type = 'bookmark'
        )
    """)

    # YAML contaminated chunks
    yaml_chunks = await conn.fetchval("""
        SELECT COUNT(*) FROM chunks
        WHERE chunk_text LIKE '---\n%' OR chunk_text LIKE '---\ntype:%'
    """)

    total_chunks = await conn.fetchval("SELECT COUNT(*) FROM chunks")

    return {
        "file_duplicates": file_dups,
        "chunks_in_duplicates": chunks_in_dups,
        "yaml_chunks": yaml_chunks,
        "total_chunks": total_chunks,
    }


async def remove_file_duplicates(conn, dry_run: bool = True) -> int:
    """Remove file content that duplicates bookmark content."""
    # Get IDs of file duplicates
    file_dup_ids = await conn.fetch("""
        SELECT DISTINCT f.id, f.title, f.filepath
        FROM content f
        JOIN content b ON f.title = b.title
        WHERE f.type = 'file' AND b.type = 'bookmark'
    """)

    if dry_run:
        print(f"Would delete {len(file_dup_ids)} file duplicates")
        for row in file_dup_ids[:5]:
            print(f"  - {row['title'][:60]}")
        return len(file_dup_ids)

    # Delete chunks first (FK constraint)
    deleted_chunks = await conn.execute("""
        DELETE FROM chunks
        WHERE content_id IN (
            SELECT f.id
            FROM content f
            JOIN content b ON f.title = b.title
            WHERE f.type = 'file' AND b.type = 'bookmark'
        )
    """)
    print(f"Deleted chunks: {deleted_chunks}")

    # Delete content
    deleted_content = await conn.execute("""
        DELETE FROM content
        WHERE id IN (
            SELECT f.id
            FROM content f
            JOIN content b ON f.title = b.title
            WHERE f.type = 'file' AND b.type = 'bookmark'
        )
    """)
    print(f"Deleted content: {deleted_content}")

    return len(file_dup_ids)


async def fix_yaml_chunks(conn, dry_run: bool = True) -> int:
    """Re-embed chunks that have YAML frontmatter contamination."""
    # Find content with YAML-contaminated chunks
    affected_content = await conn.fetch("""
        SELECT DISTINCT c.id, c.title, c.filepath, c.type
        FROM content c
        JOIN chunks ch ON c.id = ch.content_id
        WHERE ch.chunk_text LIKE '---\n%'
        AND c.type = 'file'
    """)

    if dry_run:
        print(f"Would re-embed {len(affected_content)} content items with YAML contamination")
        for row in affected_content[:5]:
            print(f"  - {row['title'][:60]}")
        return len(affected_content)

    config = ChunkingConfig(chunk_size=250, chunk_overlap=40)
    fixed_count = 0

    for row in affected_content:
        content_id = row['id']
        filepath = row['filepath']

        try:
            # Read the file
            file_path = Path(filepath)
            if not file_path.exists():
                print(f"  Skipping missing file: {filepath}")
                continue

            content = file_path.read_text(encoding='utf-8')

            # Strip YAML frontmatter
            clean_content = YAML_FRONTMATTER_PATTERN.sub('', content)

            if not clean_content.strip():
                print(f"  Skipping empty content after YAML removal: {filepath}")
                continue

            # Delete old chunks
            await conn.execute("DELETE FROM chunks WHERE content_id = $1", content_id)

            # Re-chunk and embed
            chunks = chunk_recursive(clean_content, config)

            for chunk in chunks:
                embedding = await embed_text(chunk.text)
                await conn.execute("""
                    INSERT INTO chunks (content_id, chunk_index, chunk_text, embedding, source_ref, start_char, end_char)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, content_id, chunk.index, chunk.text, embedding,
                    f"{file_path.name}#chunk-{chunk.index}", chunk.start_char, chunk.end_char)

            fixed_count += 1
            print(f"  Fixed: {row['title'][:50]} ({len(chunks)} chunks)")

        except Exception as e:
            print(f"  Error processing {filepath}: {e}")

    return fixed_count


async def main():
    parser = argparse.ArgumentParser(description="Fix embedding quality issues")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Analyze without making changes (default)")
    parser.add_argument("--execute", action="store_true",
                       help="Actually execute the fixes")
    parser.add_argument("--skip-duplicates", action="store_true",
                       help="Skip duplicate removal")
    parser.add_argument("--skip-yaml", action="store_true",
                       help="Skip YAML fix")
    args = parser.parse_args()

    dry_run = not args.execute

    db = await get_db()

    async with db.transaction() as conn:
        # Analyze current state
        print("=" * 60)
        print("EMBEDDING QUALITY ANALYSIS")
        print("=" * 60)

        issues = await analyze_issues(conn)
        print(f"\nFile duplicates of bookmarks: {issues['file_duplicates']}")
        print(f"Chunks in duplicates: {issues['chunks_in_duplicates']}")
        print(f"YAML-contaminated chunks: {issues['yaml_chunks']} / {issues['total_chunks']} "
              f"({100*issues['yaml_chunks']/issues['total_chunks']:.1f}%)")

        if dry_run:
            print("\n" + "=" * 60)
            print("DRY RUN - No changes will be made")
            print("=" * 60)

        # Step 1: Remove duplicates
        if not args.skip_duplicates:
            print("\n--- Step 1: Remove File Duplicates ---")
            await remove_file_duplicates(conn, dry_run)

        # Step 2: Fix YAML chunks
        if not args.skip_yaml:
            print("\n--- Step 2: Fix YAML Contaminated Chunks ---")
            await fix_yaml_chunks(conn, dry_run)

        if dry_run:
            print("\n" + "=" * 60)
            print("To execute fixes, run with --execute flag")
            print("=" * 60)
            # Rollback transaction in dry run
            raise asyncio.CancelledError("Dry run - rolling back")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except asyncio.CancelledError:
        pass  # Expected for dry run
