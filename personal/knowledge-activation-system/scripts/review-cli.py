#!/usr/bin/env python3
"""
KAS Review CLI - Spaced Repetition Interface

Commands:
    python review-cli.py populate       # Add high-value content to queue
    python review-cli.py due            # Show items due for review
    python review-cli.py review         # Interactive review session
    python review-cli.py stats          # Show review statistics
"""

import argparse
import sys
from datetime import datetime

import httpx

KAS_URL = "http://localhost:8000"


def api_get(endpoint: str):
    """GET request to KAS API."""
    response = httpx.get(f"{KAS_URL}{endpoint}", timeout=30.0)
    response.raise_for_status()
    return response.json()


def api_post(endpoint: str, data: dict = None):
    """POST request to KAS API."""
    response = httpx.post(
        f"{KAS_URL}{endpoint}",
        json=data or {},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def cmd_stats():
    """Show review statistics."""
    stats = api_get("/review/stats")
    print("\n=== Review Statistics ===")
    print(f"Total Active: {stats['total_active']}")
    print(f"Due Now:      {stats['due_now']}")
    print(f"New:          {stats['new']}")
    print(f"Learning:     {stats['learning']}")
    print(f"Review:       {stats['review']}")


def cmd_due(limit: int = 10):
    """Show items due for review."""
    result = api_get(f"/review/due?limit={limit}")
    items = result.get("items", [])

    if not items:
        print("\nNo items due for review!")
        return

    print(f"\n=== {len(items)} Items Due ===\n")
    for i, item in enumerate(items, 1):
        state = "NEW" if item["is_new"] else "LEARNING" if item["is_learning"] else "REVIEW"
        print(f"{i}. [{state}] {item['title'][:50]}")
        print(f"   Type: {item['content_type']} | Due: {item['due'][:10]}")
        if item["preview_text"]:
            print(f"   Preview: {item['preview_text'][:80]}...")
        print()


def cmd_review():
    """Interactive review session."""
    result = api_get("/review/due?limit=1")
    items = result.get("items", [])

    if not items:
        print("\nNo items due for review! You're all caught up.")
        return

    item = items[0]
    print("\n" + "=" * 60)
    print(f"REVIEW: {item['title']}")
    print("=" * 60)
    print(f"\nType: {item['content_type']}")
    print(f"State: {'NEW' if item['is_new'] else 'LEARNING' if item['is_learning'] else 'REVIEW'}")

    if item["preview_text"]:
        print(f"\n{item['preview_text'][:500]}")

    # Get intervals
    intervals = api_get(f"/review/{item['content_id']}/intervals")

    print("\n--- Rate your recall ---")
    print(f"1 (Again):  {intervals['again']}")
    print(f"2 (Hard):   {intervals['hard']}")
    print(f"3 (Good):   {intervals['good']}")
    print(f"4 (Easy):   {intervals['easy']}")
    print("q (Quit)")

    rating_map = {"1": "again", "2": "hard", "3": "good", "4": "easy"}

    while True:
        choice = input("\nYour rating [1-4/q]: ").strip().lower()

        if choice == "q":
            print("Review session ended.")
            return

        if choice in rating_map:
            rating = rating_map[choice]
            result = api_post(f"/review/{item['content_id']}", {"rating": rating})
            print(f"\nRated '{rating}' - Next review: {result['new_due'][:10]}")

            # Continue with next item
            cmd_review()
            return

        print("Invalid choice. Enter 1-4 or q to quit.")


def cmd_populate(limit: int = 50):
    """Add high-value content to review queue."""
    # Get content that's not yet in review
    content_result = api_get(f"/content?page_size={limit}")
    items = content_result.get("items", [])

    # Get current review stats
    stats = api_get("/review/stats")
    current_active = stats["total_active"]

    added = 0
    skipped = 0

    print(f"\nPopulating review queue (currently {current_active} active)...\n")

    for item in items:
        try:
            result = api_post(f"/review/{item['id']}/add")
            if result.get("status") == "added":
                added += 1
                print(f"  Added: {item['title'][:50]}")
            else:
                skipped += 1
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                skipped += 1  # Already in queue
            else:
                print(f"  Error adding {item['id']}: {e}")

    print(f"\nDone! Added {added} items, skipped {skipped}.")

    # Show updated stats
    cmd_stats()


def main():
    parser = argparse.ArgumentParser(description="KAS Review CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Stats command
    subparsers.add_parser("stats", help="Show review statistics")

    # Due command
    due_parser = subparsers.add_parser("due", help="Show items due for review")
    due_parser.add_argument("--limit", "-l", type=int, default=10, help="Max items to show")

    # Review command
    subparsers.add_parser("review", help="Start interactive review session")

    # Populate command
    pop_parser = subparsers.add_parser("populate", help="Add content to review queue")
    pop_parser.add_argument("--limit", "-l", type=int, default=50, help="Max items to add")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Check KAS availability
    try:
        api_get("/health")
    except Exception as e:
        print(f"ERROR: KAS not available at {KAS_URL}")
        print(f"  {e}")
        sys.exit(1)

    # Execute command
    if args.command == "stats":
        cmd_stats()
    elif args.command == "due":
        cmd_due(args.limit)
    elif args.command == "review":
        cmd_review()
    elif args.command == "populate":
        cmd_populate(args.limit)


if __name__ == "__main__":
    main()
