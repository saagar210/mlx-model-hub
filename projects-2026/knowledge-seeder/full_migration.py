"""Full migration script for KAS integration.

Processes all source YAML files and ingests to KAS.
Authorization: KAS-MIGRATE-2026-01-13-APPROVED
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

# Configuration
KAS_URL = "http://localhost:8000"
SOURCES_DIR = Path("sources")
BATCH_SIZE = 20
BATCH_DELAY = 2.5  # seconds between batches
MAX_RETRIES = 3

# Namespace priority order (as specified by KAS)
NAMESPACE_ORDER = [
    "frameworks",      # P0
    "infrastructure",  # P0
    "ai-ml",          # P0
    "tools",          # P1
    "languages",      # P1
    "projects",       # P2
    "research",       # P2
    "tutorials",      # P2
    "reference",      # P3
    "archive",        # P3
]

# Map source files to namespaces
FILE_TO_NAMESPACE = {
    "frameworks.yaml": "frameworks",
    "agent-frameworks.yaml": "frameworks",
    "infrastructure.yaml": "infrastructure",
    "ai-research.yaml": "ai-ml",
    "apple-mlx.yaml": "ai-ml",
    "tools.yaml": "tools",
    "best-practices.yaml": "reference",
    "tutorials-youtube.yaml": "tutorials",
    "project-voice-ai.yaml": "projects",
    "project-browser-automation.yaml": "projects",
    "project-mcp-servers.yaml": "projects",
    "project-rag-evaluation.yaml": "projects",
}


class MigrationStats:
    """Track migration statistics."""

    def __init__(self):
        self.by_namespace: dict[str, dict[str, int]] = {}
        self.failed_docs: list[dict] = []
        self.skipped_docs: list[dict] = []
        self.total_chunks = 0

    def init_namespace(self, ns: str):
        if ns not in self.by_namespace:
            self.by_namespace[ns] = {
                "processed": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
                "chunks": 0,
            }

    def record_success(self, ns: str, chunks: int):
        self.init_namespace(ns)
        self.by_namespace[ns]["processed"] += 1
        self.by_namespace[ns]["succeeded"] += 1
        self.by_namespace[ns]["chunks"] += chunks
        self.total_chunks += chunks

    def record_failure(self, ns: str, title: str, error: str):
        self.init_namespace(ns)
        self.by_namespace[ns]["processed"] += 1
        self.by_namespace[ns]["failed"] += 1
        self.failed_docs.append({"title": title, "namespace": ns, "error": error})

    def record_skip(self, ns: str, title: str, reason: str):
        self.init_namespace(ns)
        self.by_namespace[ns]["processed"] += 1
        self.by_namespace[ns]["skipped"] += 1
        self.skipped_docs.append({"title": title, "namespace": ns, "reason": reason})

    def get_totals(self) -> dict[str, int]:
        totals = {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "chunks": 0}
        for ns_stats in self.by_namespace.values():
            for key in totals:
                totals[key] += ns_stats.get(key, 0)
        return totals


stats = MigrationStats()


async def extract_content(url: str, timeout: float = 30.0) -> tuple[str, str] | None:
    """Extract content from URL using trafilatura."""
    import trafilatura

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "KnowledgeSeeder/0.1.0"})
            r.raise_for_status()
            html = r.text

        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            include_links=False,
            favor_recall=True,
            output_format="txt",
        )

        if not content:
            content = trafilatura.extract(html) or ""

        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata else url.split("/")[-2]

        return content or "", title or url
    except httpx.HTTPStatusError as e:
        print(f"      HTTP error {e.response.status_code}: {url}")
        return None
    except Exception as e:
        print(f"      Extraction error: {e}")
        return None


def score_quality(content: str) -> tuple[float, str]:
    """Simple quality scoring."""
    word_count = len(content.split())

    if word_count < 100:
        return 20.0, "F"
    elif word_count < 300:
        return 50.0, "D"
    elif word_count < 1000:
        return 70.0, "C"
    elif word_count < 5000:
        return 85.0, "B"
    else:
        return 95.0, "A"


def build_payload(
    content: str,
    title: str,
    source: dict,
    namespace: str,
    quality_score: float,
    quality_grade: str,
) -> dict:
    """Build KAS-compliant payload."""
    return {
        "content": content,
        "title": title,
        "document_type": "markdown",
        "namespace": namespace,
        "metadata": {
            "source": source.get("url", ""),
            "author": None,
            "created_at": None,
            "tags": source.get("tags", []),
            "language": "en",
            "custom": {
                "seeder_source_id": f"{namespace}:{source.get('name', 'unknown')}",
                "seeder_source_type": "url",
                "seeder_priority": source.get("priority", "P2"),
                "seeder_quality_score": quality_score,
                "seeder_quality_grade": quality_grade,
                "seeder_extracted_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }


async def ingest_document(payload: dict, retries: int = MAX_RETRIES) -> dict:
    """Send document to KAS with retry logic."""
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(
                    f"{KAS_URL}/api/v1/ingest/document",
                    json=payload,
                )

                if r.status_code == 429:
                    print(f"      Rate limited, waiting 60s...")
                    await asyncio.sleep(60)
                    continue

                if r.status_code == 500 and attempt < retries - 1:
                    wait_time = 2 ** attempt * 5
                    print(f"      Server error, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue

                return r.json()
        except Exception as e:
            if attempt < retries - 1:
                wait_time = 2 ** attempt * 2
                print(f"      Connection error, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                return {"success": False, "message": str(e)}

    return {"success": False, "message": "Max retries exceeded"}


def load_sources_from_yaml(filepath: Path) -> list[dict]:
    """Load sources from a YAML file."""
    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)

        if not data:
            return []

        sources = data.get("sources", [])
        namespace = data.get("namespace", "general")
        priority = data.get("priority", "P2")

        # Add namespace and priority to each source
        for source in sources:
            if "namespace" not in source:
                source["namespace"] = namespace
            if "priority" not in source:
                source["priority"] = priority

        return sources
    except Exception as e:
        print(f"  Error loading {filepath}: {e}")
        return []


async def process_source(source: dict, namespace: str) -> bool:
    """Process a single source."""
    name = source.get("name", "unknown")
    url = source.get("url", "")

    print(f"    Processing: {name}")
    print(f"    URL: {url}")

    # Extract content
    result = await extract_content(url)
    if result is None:
        stats.record_skip(namespace, name, "URL unavailable or extraction failed")
        return False

    content, title = result

    if len(content) < 100:
        stats.record_skip(namespace, name, f"Content too short ({len(content)} chars)")
        return False

    # Score quality
    quality_score, quality_grade = score_quality(content)
    print(f"    Content: {len(content)} chars, Quality: {quality_grade}")

    # Build and send payload
    payload = build_payload(content, title, source, namespace, quality_score, quality_grade)
    response = await ingest_document(payload)

    if response.get("success"):
        chunks = response.get("chunks_created", 0)
        stats.record_success(namespace, chunks)
        print(f"    SUCCESS: {chunks} chunks created")
        return True
    else:
        error = response.get("message") or response.get("detail", "Unknown error")
        # Check for duplicate - treat as success
        if "duplicate" in str(error).lower():
            stats.record_success(namespace, 0)
            print(f"    DUPLICATE: Already ingested")
            return True
        stats.record_failure(namespace, name, error[:100])
        print(f"    FAILED: {error[:100]}")
        return False


async def process_namespace(namespace: str, sources: list[dict]):
    """Process all sources for a namespace."""
    print(f"\n{'='*60}")
    print(f"NAMESPACE: {namespace.upper()}")
    print(f"Sources: {len(sources)}")
    print(f"{'='*60}")

    for i, source in enumerate(sources, 1):
        print(f"\n  [{i}/{len(sources)}]")
        await process_source(source, namespace)

        # Delay between documents
        if i < len(sources):
            await asyncio.sleep(BATCH_DELAY)

    # Report namespace completion
    ns_stats = stats.by_namespace.get(namespace, {})
    totals = stats.get_totals()
    print(f"\n[SEEDER] Namespace complete: {namespace}")
    print(f"[SEEDER] Succeeded: {ns_stats.get('succeeded', 0)}, Failed: {ns_stats.get('failed', 0)}, Skipped: {ns_stats.get('skipped', 0)}")
    print(f"[SEEDER] Running total: {totals['succeeded']}/{totals['processed']}")


async def get_kas_stats() -> dict:
    """Get current KAS statistics."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{KAS_URL}/api/v1/stats")
            return r.json()
    except Exception as e:
        return {"error": str(e)}


async def verify_search(query: str) -> int:
    """Run a verification search and return result count."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{KAS_URL}/api/v1/search",
                params={"q": query, "limit": 10},
            )
            data = r.json()
            return data.get("total", 0)
    except Exception:
        return -1


async def main():
    """Execute full migration."""
    start_time = time.time()

    print("="*60)
    print("KNOWLEDGE SEEDER - FULL MIGRATION")
    print(f"Authorization: KAS-MIGRATE-2026-01-13-APPROVED")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print("="*60)

    # Load all sources grouped by namespace
    all_sources: dict[str, list[dict]] = {}

    print("\nLoading source files...")
    for yaml_file in sorted(SOURCES_DIR.glob("*.yaml")):
        namespace = FILE_TO_NAMESPACE.get(yaml_file.name, "general")
        sources = load_sources_from_yaml(yaml_file)
        print(f"  {yaml_file.name}: {len(sources)} sources -> {namespace}")

        if namespace not in all_sources:
            all_sources[namespace] = []
        all_sources[namespace].extend(sources)

    # Count total sources
    total_sources = sum(len(s) for s in all_sources.values())
    print(f"\nTotal sources to process: {total_sources}")

    # Process in priority order
    for namespace in NAMESPACE_ORDER:
        if namespace in all_sources and all_sources[namespace]:
            await process_namespace(namespace, all_sources[namespace])

    # Process any remaining namespaces not in the priority list
    for namespace, sources in all_sources.items():
        if namespace not in NAMESPACE_ORDER and sources:
            await process_namespace(namespace, sources)

    # Get final stats
    final_stats = await get_kas_stats()
    search_count = await verify_search("python framework")

    # Generate final report
    elapsed = time.time() - start_time
    totals = stats.get_totals()

    print("\n" + "="*60)
    print("KNOWLEDGE SEEDER FINAL MIGRATION REPORT")
    print("="*60)

    print(f"\n**To:** KAS")
    print(f"**Timestamp:** {datetime.now(timezone.utc).isoformat()}")
    print(f"**Phase:** Full Migration Complete")
    print(f"**Duration:** {elapsed/60:.1f} minutes")

    print(f"\n### Summary")
    print(f"- Total Sources Processed: {totals['processed']}/{total_sources}")
    print(f"- Total Succeeded: {totals['succeeded']}")
    print(f"- Total Failed: {totals['failed']}")
    print(f"- Total Skipped (unavailable): {totals['skipped']}")
    print(f"- Total Chunks Created: {stats.total_chunks}")

    print(f"\n### By Namespace")
    print("| Namespace | Processed | Succeeded | Failed | Skipped | Chunks |")
    print("|-----------|-----------|-----------|--------|---------|--------|")
    for ns in NAMESPACE_ORDER:
        if ns in stats.by_namespace:
            s = stats.by_namespace[ns]
            print(f"| {ns} | {s['processed']} | {s['succeeded']} | {s['failed']} | {s['skipped']} | {s['chunks']} |")
    # Any additional namespaces
    for ns, s in stats.by_namespace.items():
        if ns not in NAMESPACE_ORDER:
            print(f"| {ns} | {s['processed']} | {s['succeeded']} | {s['failed']} | {s['skipped']} | {s['chunks']} |")

    if stats.failed_docs:
        print(f"\n### Failed Documents ({len(stats.failed_docs)})")
        print("| Title | Namespace | Error |")
        print("|-------|-----------|-------|")
        for doc in stats.failed_docs[:20]:  # Limit to 20
            print(f"| {doc['title'][:30]} | {doc['namespace']} | {doc['error'][:40]} |")

    if stats.skipped_docs:
        print(f"\n### Skipped Documents ({len(stats.skipped_docs)})")
        print("| Title | Namespace | Reason |")
        print("|-------|-----------|--------|")
        for doc in stats.skipped_docs[:20]:  # Limit to 20
            print(f"| {doc['title'][:30]} | {doc['namespace']} | {doc['reason'][:40]} |")

    print(f"\n### Verification")
    print(f"- Final stats endpoint response: {json.dumps(final_stats)}")
    print(f"- Sample search test ('python framework'): {search_count} results")

    print(f"\n### Issues Encountered")
    if stats.failed_docs or stats.skipped_docs:
        print(f"- {len(stats.failed_docs)} documents failed due to errors")
        print(f"- {len(stats.skipped_docs)} documents skipped (URL unavailable or content too short)")
    else:
        print("None")

    success_rate = (totals['succeeded'] / totals['processed'] * 100) if totals['processed'] > 0 else 0
    print(f"\n### Migration Status")
    if success_rate >= 90:
        print(f"**COMPLETE** - {success_rate:.1f}% success rate")
    elif success_rate >= 70:
        print(f"**PARTIAL** - {success_rate:.1f}% success rate, some sources unavailable")
    else:
        print(f"**NEEDS REVIEW** - {success_rate:.1f}% success rate")

    print("\n" + "="*60)
    print("MIGRATION COMPLETE")
    print("="*60)

    return {
        "totals": totals,
        "by_namespace": stats.by_namespace,
        "failed": stats.failed_docs,
        "skipped": stats.skipped_docs,
        "final_stats": final_stats,
    }


if __name__ == "__main__":
    asyncio.run(main())
