#!/usr/bin/env python3
"""Check content health and quality metrics.

Usage:
    python scripts/check_content_health.py [--fix] [--verbose]
"""
import asyncio
import argparse
from datetime import datetime, timedelta
import httpx


async def check_content_health(fix: bool = False, verbose: bool = False):
    """Run comprehensive health checks on content."""
    base_url = "http://localhost:8000"
    issues = []
    warnings = []

    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        print(f"[{datetime.now().isoformat()}] Running content health checks...\n")

        # 1. Check API health
        try:
            resp = await client.get("/health")
            health = resp.json()
            print(f"[OK] API Status: {health.get('status', 'unknown')}")
            db_details = next((c['details'] for c in health.get('components', [])
                              if c['name'] == 'database'), {})
            content_count = db_details.get('content_count', 0)
            chunk_count = db_details.get('chunk_count', 0)
            print(f"     Content: {content_count}, Chunks: {chunk_count}")
        except Exception as e:
            issues.append(f"API health check failed: {e}")
            return {"issues": issues, "warnings": warnings}

        # 2. Check for orphaned chunks (chunks without content)
        # This would require a database query endpoint or direct DB access
        # For now, check ratio
        if content_count > 0:
            ratio = chunk_count / content_count
            if ratio < 1:
                warnings.append(f"Low chunk ratio ({ratio:.1f}): some content may not be indexed")
            elif ratio > 50:
                warnings.append(f"High chunk ratio ({ratio:.1f}): may indicate duplicate chunks")
            else:
                print(f"[OK] Chunk ratio: {ratio:.1f} chunks per content")

        # 3. Check entity extraction coverage
        try:
            resp = await client.get("/entities/stats")
            entity_stats = resp.json()
            total_entities = sum(s.get('count', 0) for s in entity_stats)
            print(f"[OK] Total entities: {total_entities}")

            # Check for diversity
            entity_types = [s.get('entity_type') for s in entity_stats if s.get('count', 0) > 0]
            if len(entity_types) < 3:
                warnings.append(f"Low entity type diversity: only {len(entity_types)} types")
        except Exception as e:
            warnings.append(f"Entity stats check failed: {e}")

        # 4. Test search functionality
        test_queries = ["Python", "FastAPI", "Docker", "AI"]
        search_issues = []
        for query in test_queries:
            try:
                resp = await client.get(f"/api/v1/search", params={"q": query, "limit": 3})
                results = resp.json()
                if not results.get("results"):
                    search_issues.append(query)
                elif verbose:
                    print(f"     Search '{query}': {len(results.get('results', []))} results")
            except Exception as e:
                search_issues.append(f"{query} (error: {e})")

        if search_issues:
            warnings.append(f"Search returned no results for: {search_issues}")
        else:
            print(f"[OK] Search functionality: working for {len(test_queries)} test queries")

        # 5. Check namespace distribution
        try:
            resp = await client.get("/api/v1/namespaces")
            namespaces = resp.json()
            if isinstance(namespaces, list) and len(namespaces) > 0:
                print(f"[OK] Namespaces: {len(namespaces)} active")
                if verbose:
                    for ns in namespaces[:5]:
                        print(f"     - {ns.get('name', 'unknown')}: {ns.get('content_count', 0)} items")
            else:
                warnings.append("No namespaces found")
        except Exception as e:
            if verbose:
                print(f"[WARN] Namespace check: {e}")

        # Summary
        print("\n" + "=" * 50)
        print("HEALTH CHECK SUMMARY")
        print("=" * 50)

        if issues:
            print(f"\n[CRITICAL] {len(issues)} issue(s):")
            for issue in issues:
                print(f"  - {issue}")

        if warnings:
            print(f"\n[WARNING] {len(warnings)} warning(s):")
            for warning in warnings:
                print(f"  - {warning}")

        if not issues and not warnings:
            print("\n[OK] All health checks passed!")

        return {"issues": issues, "warnings": warnings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check content health")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    asyncio.run(check_content_health(fix=args.fix, verbose=args.verbose))
