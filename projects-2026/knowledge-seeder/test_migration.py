"""Test migration script for KAS integration - 3 documents only."""

import asyncio
import json
from datetime import datetime, timezone

import httpx

# KAS API base URL
KAS_URL = "http://localhost:8000"

# Test sources - using stable documentation URLs
TEST_SOURCES = [
    {
        "name": "httpx-quickstart",
        "url": "https://www.python-httpx.org/quickstart/",
        "tags": ["httpx", "python", "http-client"],
        "namespace": "frameworks",
        "priority": "P0",
    },
    {
        "name": "fastapi-first-steps",
        "url": "https://fastapi.tiangolo.com/tutorial/first-steps/",
        "tags": ["fastapi", "python", "tutorial"],
        "namespace": "frameworks",
        "priority": "P0",
    },
    {
        "name": "pipecat-introduction",
        "url": "https://docs.pipecat.ai/",
        "tags": ["pipecat", "voice", "realtime"],
        "namespace": "frameworks",
        "priority": "P0",
    },
]


async def extract_content(url: str) -> tuple[str, str]:
    """Extract content from URL using trafilatura."""
    import trafilatura

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
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

    # Extract title
    metadata = trafilatura.extract_metadata(html)
    title = metadata.title if metadata else url.split("/")[-2]

    return content or "", title or url


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
    quality_score: float,
    quality_grade: str,
) -> dict:
    """Build KAS-compliant payload."""
    return {
        "content": content,
        "title": title,
        "document_type": "markdown",
        "namespace": source["namespace"],
        "metadata": {
            "source": source["url"],
            "author": None,
            "created_at": None,
            "tags": source["tags"],
            "language": "en",
            "custom": {
                "seeder_source_id": f"{source['namespace']}:{source['name']}",
                "seeder_source_type": "url",
                "seeder_priority": source["priority"],
                "seeder_quality_score": quality_score,
                "seeder_quality_grade": quality_grade,
                "seeder_extracted_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }


async def ingest_document(payload: dict) -> dict:
    """Send document to KAS."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{KAS_URL}/api/v1/ingest/document",
            json=payload,
        )
        return r.json()


async def main():
    """Execute test migration."""
    print("=" * 60)
    print("KNOWLEDGE SEEDER - TEST MIGRATION")
    print("=" * 60)

    results = []

    for i, source in enumerate(TEST_SOURCES, 1):
        print(f"\n[{i}/3] Processing: {source['name']}")
        print(f"      URL: {source['url']}")

        try:
            # Extract
            print("      Extracting content...")
            content, title = await extract_content(source["url"])
            print(f"      Title: {title}")
            print(f"      Content length: {len(content)} chars")

            if len(content) < 100:
                print("      ERROR: Content too short")
                results.append({
                    "name": source["name"],
                    "title": title,
                    "status": "failed",
                    "error": "Content too short",
                    "chunks": 0,
                    "content_id": None,
                })
                continue

            # Score
            quality_score, quality_grade = score_quality(content)
            print(f"      Quality: {quality_score:.1f}/100 (Grade {quality_grade})")

            # Build payload
            payload = build_payload(content, title, source, quality_score, quality_grade)

            # Ingest
            print("      Ingesting to KAS...")
            response = await ingest_document(payload)
            print(f"      Response: {json.dumps(response, indent=2)}")

            if response.get("success"):
                results.append({
                    "name": source["name"],
                    "title": title,
                    "status": "success",
                    "error": None,
                    "chunks": response.get("chunks_created", 0),
                    "content_id": response.get("content_id"),
                })
            else:
                results.append({
                    "name": source["name"],
                    "title": title,
                    "status": "failed",
                    "error": response.get("message", "Unknown error"),
                    "chunks": 0,
                    "content_id": None,
                })

        except Exception as e:
            print(f"      ERROR: {e}")
            results.append({
                "name": source["name"],
                "title": source["name"],
                "status": "failed",
                "error": str(e),
                "chunks": 0,
                "content_id": None,
            })

        # Rate limit
        await asyncio.sleep(2)

    # Summary
    print("\n" + "=" * 60)
    print("TEST MIGRATION RESULTS")
    print("=" * 60)

    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    total_chunks = sum(r["chunks"] for r in results)

    print(f"\nDocuments Sent: {len(results)}")
    print(f"Succeeded: {succeeded}")
    print(f"Failed: {failed}")
    print(f"Total Chunks Created: {total_chunks}")

    print("\nIndividual Results:")
    print("-" * 60)
    for r in results:
        status_icon = "✓" if r["status"] == "success" else "✗"
        print(f"  {status_icon} {r['title'][:40]:<40} | {r['status']:8} | {r['chunks']:3} chunks | {r['content_id'] or 'N/A'}")

    if failed > 0:
        print("\nErrors:")
        for r in results:
            if r["error"]:
                print(f"  - {r['name']}: {r['error']}")

    # Return results for further processing
    return {
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "total_chunks": total_chunks,
        "results": results,
    }


if __name__ == "__main__":
    asyncio.run(main())
