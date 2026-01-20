#!/usr/bin/env python3
"""Batch extract entities for content without entities.

Usage:
    python scripts/extract_entities_batch.py [--batch-size 50] [--dry-run]
"""
import asyncio
import argparse
import httpx
from datetime import datetime


async def get_content_without_entities(client: httpx.AsyncClient, limit: int = 100) -> list[dict]:
    """Get content IDs that don't have entities extracted."""
    # Use the content endpoint to get all content, then check entities
    # This is a simplified approach - in production you'd have a dedicated endpoint
    response = await client.get("/content", params={"limit": limit})
    response.raise_for_status()

    content_items = response.json()

    # Check each content for entities
    needs_extraction = []
    for item in content_items.get("items", content_items):
        content_id = item.get("id")
        if not content_id:
            continue

        # Check if content has entities
        entity_resp = await client.get(f"/entities/content/{content_id}")
        if entity_resp.status_code == 200:
            entities = entity_resp.json()
            if not entities or len(entities) == 0:
                needs_extraction.append(item)
        elif entity_resp.status_code == 404:
            needs_extraction.append(item)

    return needs_extraction


async def extract_entities_for_content(client: httpx.AsyncClient, content_id: str) -> dict:
    """Extract entities for a single content item."""
    response = await client.post(
        "/entities/extract",
        json={"content_id": content_id},
        timeout=120.0  # Extraction can take time
    )
    response.raise_for_status()
    return response.json()


async def main(batch_size: int = 50, dry_run: bool = False):
    """Run batch entity extraction."""
    base_url = "http://localhost:8000"

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        print(f"[{datetime.now().isoformat()}] Starting batch entity extraction")
        print(f"  Batch size: {batch_size}")
        print(f"  Dry run: {dry_run}")

        # Get content without entities
        print("\n[INFO] Fetching content without entities...")
        content_list = await get_content_without_entities(client, limit=batch_size)

        print(f"[INFO] Found {len(content_list)} content items without entities")

        if dry_run:
            print("\n[DRY RUN] Would extract entities for:")
            for item in content_list:
                print(f"  - {item.get('title', item.get('id', 'unknown'))}")
            return

        # Extract entities for each
        success_count = 0
        error_count = 0

        for i, item in enumerate(content_list, 1):
            content_id = item.get("id")
            title = item.get("title", content_id)

            try:
                print(f"\n[{i}/{len(content_list)}] Extracting: {title}")
                result = await extract_entities_for_content(client, content_id)
                entity_count = result.get("entity_count", 0)
                relationship_count = result.get("relationship_count", 0)
                print(f"  ✓ Extracted {entity_count} entities, {relationship_count} relationships")
                success_count += 1
            except httpx.HTTPStatusError as e:
                print(f"  ✗ Error: {e.response.status_code} - {e.response.text[:100]}")
                error_count += 1
            except Exception as e:
                print(f"  ✗ Error: {e}")
                error_count += 1

        print(f"\n[SUMMARY]")
        print(f"  Processed: {len(content_list)}")
        print(f"  Success: {success_count}")
        print(f"  Errors: {error_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch extract entities for content")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of items to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without extracting")
    args = parser.parse_args()

    asyncio.run(main(batch_size=args.batch_size, dry_run=args.dry_run))
