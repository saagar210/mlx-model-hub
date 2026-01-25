"""Targeted migration for fixed URLs.

Runs migration for URLs that were previously failing due to:
- LangGraph documentation moved (404)
- LlamaIndex documentation moved (404)
- GitHub tree/blob paths (extraction issues)
- OpenAI platform docs (403) - now using cookbook alternatives
"""

import asyncio
import time
from datetime import datetime, timezone

import httpx
import trafilatura

KAS_URL = "http://localhost:8000"

# Sources with fixed URLs
FIXED_SOURCES = [
    # LangGraph (moved to docs.langchain.com)
    {
        "name": "langgraph-quickstart",
        "url": "https://docs.langchain.com/oss/python/langgraph/quickstart",
        "namespace": "frameworks",
        "tags": ["langgraph", "agents", "quickstart"],
    },
    {
        "name": "langgraph-thinking-guide",
        "url": "https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph",
        "namespace": "frameworks",
        "tags": ["langgraph", "concepts", "guide"],
    },
    {
        "name": "langgraph-tutorials",
        "url": "https://docs.langchain.com/oss/python/langgraph/tutorials",
        "namespace": "frameworks",
        "tags": ["langgraph", "tutorials", "examples"],
    },
    # LlamaIndex (moved to developers.llamaindex.ai)
    {
        "name": "llamaindex-getting-started",
        "url": "https://developers.llamaindex.ai/python/framework/getting_started",
        "namespace": "frameworks",
        "tags": ["llamaindex", "quickstart", "basics"],
    },
    {
        "name": "llamaindex-learn",
        "url": "https://developers.llamaindex.ai/python/framework/learn",
        "namespace": "frameworks",
        "tags": ["llamaindex", "concepts", "tutorials"],
    },
    # GitHub raw URLs (converted from blob/tree)
    {
        "name": "ollama-readme",
        "url": "https://raw.githubusercontent.com/ollama/ollama/main/README.md",
        "namespace": "infrastructure",
        "tags": ["ollama", "local", "llm"],
    },
    {
        "name": "ollama-api",
        "url": "https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md",
        "namespace": "infrastructure",
        "tags": ["ollama", "api", "reference"],
    },
    {
        "name": "mcp-server-filesystem",
        "url": "https://raw.githubusercontent.com/modelcontextprotocol/servers/main/src/filesystem/README.md",
        "namespace": "projects",
        "tags": ["mcp", "filesystem", "example"],
    },
    {
        "name": "mcp-server-memory",
        "url": "https://raw.githubusercontent.com/modelcontextprotocol/servers/main/src/memory/README.md",
        "namespace": "projects",
        "tags": ["mcp", "memory", "example"],
    },
    {
        "name": "whisper-repo",
        "url": "https://raw.githubusercontent.com/openai/whisper/main/README.md",
        "namespace": "projects",
        "tags": ["whisper", "stt", "openai"],
    },
    # OpenAI Cookbook alternatives (replacing blocked platform.openai.com)
    {
        "name": "openai-cookbook-readme",
        "url": "https://raw.githubusercontent.com/openai/openai-cookbook/main/README.md",
        "namespace": "frameworks",
        "tags": ["openai", "cookbook", "overview"],
    },
    {
        "name": "openai-python-sdk",
        "url": "https://raw.githubusercontent.com/openai/openai-python/main/README.md",
        "namespace": "frameworks",
        "tags": ["openai", "python", "sdk"],
    },
    {
        "name": "openai-function-calling",
        "url": "https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/How_to_call_functions_with_chat_models.ipynb",
        "namespace": "frameworks",
        "tags": ["openai", "tools", "function-calling"],
    },
]


async def extract_content(url: str) -> tuple[str, str] | None:
    """Extract content from URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "KnowledgeSeeder/0.1.0"})
            r.raise_for_status()
            html = r.text

        # For raw GitHub content, return directly
        if "raw.githubusercontent.com" in url:
            return html, url.split("/")[-1]

        content = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
            output_format="txt",
        )
        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata else url.split("/")[-1]
        return content or "", title or url
    except Exception as e:
        print(f"  Error extracting {url}: {e}")
        return None


async def ingest_document(payload: dict) -> dict:
    """Send document to KAS."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{KAS_URL}/api/v1/ingest/document",
                json=payload,
            )
            return r.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


async def process_source(source: dict) -> bool:
    """Process a single source."""
    name = source["name"]
    url = source["url"]

    print(f"\n[{source['namespace']}] {name}")
    print(f"  URL: {url}")

    result = await extract_content(url)
    if result is None:
        print(f"  SKIP: Extraction failed")
        return False

    content, title = result
    if len(content) < 50:
        print(f"  SKIP: Content too short ({len(content)} chars)")
        return False

    print(f"  Content: {len(content)} chars")

    payload = {
        "content": content,
        "title": title,
        "document_type": "markdown",
        "namespace": source["namespace"],
        "metadata": {
            "source": url,
            "tags": source.get("tags", []),
            "language": "en",
            "custom": {
                "seeder_source_id": f"{source['namespace']}:{name}",
                "seeder_migrated_at": datetime.now(timezone.utc).isoformat(),
                "seeder_migration_type": "fix_migration",
            },
        },
    }

    response = await ingest_document(payload)

    if response.get("success"):
        chunks = response.get("chunks_created", 0)
        print(f"  SUCCESS: {chunks} chunks created")
        return True
    elif "duplicate" in str(response.get("message", "")).lower():
        print(f"  DUPLICATE: Already exists")
        return True
    else:
        error = response.get("message") or response.get("detail", "Unknown error")
        print(f"  FAILED: {error[:80]}")
        return False


async def main():
    """Run targeted migration."""
    print("=" * 60)
    print("FIX MIGRATION - Corrected URLs")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print(f"Sources to process: {len(FIXED_SOURCES)}")
    print("=" * 60)

    success = 0
    failed = 0

    for source in FIXED_SOURCES:
        if await process_source(source):
            success += 1
        else:
            failed += 1
        await asyncio.sleep(2)  # Rate limiting

    print("\n" + "=" * 60)
    print("FIX MIGRATION COMPLETE")
    print(f"Success: {success}/{len(FIXED_SOURCES)}")
    print(f"Failed: {failed}")
    print("=" * 60)

    # Get updated stats
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{KAS_URL}/api/v1/stats")
        stats = r.json()
        print(f"\nKAS Stats: {stats.get('total_content', 0)} documents, {stats.get('total_chunks', 0)} chunks")


if __name__ == "__main__":
    asyncio.run(main())
