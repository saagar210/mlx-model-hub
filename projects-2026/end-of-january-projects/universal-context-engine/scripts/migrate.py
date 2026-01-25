#!/usr/bin/env python3
"""Run database migrations."""

import asyncio
import sys
from pathlib import Path

import asyncpg

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uce.core.config import settings


async def run_migrations() -> None:
    """Execute all migration files in order."""
    migrations_dir = Path(__file__).parent.parent / "migrations"

    # Get connection URL (convert from SQLAlchemy format)
    db_url = settings.database_url.replace("+asyncpg", "")

    print(f"Connecting to database...")
    conn = await asyncpg.connect(db_url)

    try:
        # Get migration files in order
        migration_files = sorted(migrations_dir.glob("*.sql"))

        for migration_file in migration_files:
            print(f"Running migration: {migration_file.name}")
            sql = migration_file.read_text()

            try:
                await conn.execute(sql)
                print(f"  ✓ {migration_file.name} completed")
            except asyncpg.exceptions.DuplicateTableError:
                print(f"  - {migration_file.name} skipped (already exists)")
            except asyncpg.exceptions.DuplicateObjectError:
                print(f"  - {migration_file.name} skipped (object exists)")
            except Exception as e:
                print(f"  ✗ {migration_file.name} failed: {e}")
                raise

        print("\nAll migrations completed successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
