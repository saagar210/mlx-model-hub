# KAS Python SDK

Python client library for the Knowledge Activation System (KAS) API.

## Installation

```bash
pip install kas-client
```

Or install from source:

```bash
cd sdk/python
pip install -e .
```

## Quick Start

### Async Client

```python
import asyncio
from kas_client import KASClient

async def main():
    async with KASClient("http://localhost:8000") as client:
        # Search the knowledge base
        results = await client.search("python dependency injection")
        for r in results.results:
            print(f"- {r.title} (score: {r.score:.2f})")

        # Ask a question
        answer = await client.ask("How does connection pooling work?")
        print(f"\nAnswer: {answer.answer}")
        print(f"Confidence: {answer.confidence}")

asyncio.run(main())
```

### Sync Client

```python
from kas_client import KASClientSync

client = KASClientSync("http://localhost:8000")

# Search
results = client.search("FastAPI patterns", limit=5)
print(f"Found {results.total} results")

# Ingest content
result = client.ingest(
    content="# My Notes\n\nSome important information...",
    title="My Notes",
    namespace="notes",
    tags=["personal", "notes"]
)
print(f"Ingested: {result.content_id}")

client.close()
```

## API Reference

### Client Initialization

```python
from kas_client import KASClient, KASClientSync

# Async client
client = KASClient(
    base_url="http://localhost:8000",  # KAS API URL
    timeout=30.0,                       # Request timeout in seconds
    api_key="optional-api-key"          # Optional API key
)

# Sync client (same parameters)
client = KASClientSync(base_url="http://localhost:8000")
```

### Search

```python
# Basic search
results = await client.search("query text")

# With options
results = await client.search(
    "query text",
    limit=10,              # Max results
    namespace="notes",     # Filter by namespace
    min_score=0.5,         # Minimum relevance score
    rerank=True            # Apply reranking
)

# Access results
for r in results.results:
    print(r.title, r.score, r.chunk_text)
```

### Batch Search

```python
# Execute multiple queries at once (max 10)
response = await client.batch_search(
    queries=["python patterns", "database optimization", "API design"],
    limit=5
)

for batch_result in response.results:
    print(f"Query: {batch_result.query}")
    for r in batch_result.results:
        print(f"  - {r.title}")
```

### Q&A

```python
answer = await client.ask(
    "How does the hybrid search algorithm work?",
    context_limit=5  # Number of context chunks
)

print(answer.answer)
print(f"Confidence: {answer.confidence} ({answer.confidence_score:.2f})")

# Citations
for citation in answer.citations:
    print(f"[{citation.index}] {citation.title}")
```

### Content Ingestion

```python
# Ingest text/markdown content
result = await client.ingest(
    content="# Title\n\nContent here...",
    title="My Document",
    namespace="notes",
    document_type="markdown",  # or "text", "code"
    tags=["tag1", "tag2"],
    source="my-app"
)

# Ingest YouTube video
result = await client.ingest_youtube(
    "dQw4w9WgXcQ",
    namespace="youtube",
    tags=["music"]
)

# Ingest web bookmark
result = await client.ingest_bookmark(
    "https://example.com/article",
    title="Optional Title Override",
    namespace="bookmarks",
    tags=["reading"]
)
```

### Namespaces

```python
namespaces = await client.list_namespaces()
for ns in namespaces:
    print(f"{ns.name}: {ns.document_count} documents")
```

### Spaced Repetition Review

```python
# Get items due for review
items = await client.get_review_items(limit=5)
for item in items:
    print(f"Review: {item.title}")
    print(f"  New: {item.is_new}, Learning: {item.is_learning}")

# Submit a review rating (1=Again, 2=Hard, 3=Good, 4=Easy)
response = await client.submit_review(
    content_id="abc123",
    rating=3  # Good
)
print(f"Next review: {response.next_review}")

# Get review statistics
stats = await client.get_review_stats()
print(f"Due now: {stats.due_now}")
print(f"Reviews today: {stats.reviews_today}")
```

### Content Management

```python
# Delete single item
await client.delete_content("content-id-123")

# Batch delete (max 100)
result = await client.batch_delete(["id1", "id2", "id3"])
print(f"Deleted: {result['deleted']}")
```

### Health Check

```python
health = await client.health()
print(f"Status: {health.status}")
print(f"Version: {health.version}")
print(f"Database: {health.services.database}")
print(f"Total content: {health.stats.total_content}")
```

## Error Handling

```python
from kas_client import (
    KASError,
    KASConnectionError,
    KASAPIError,
    KASValidationError
)

try:
    results = await client.search("query")
except KASConnectionError as e:
    print(f"Connection failed: {e}")
except KASAPIError as e:
    print(f"API error {e.status_code}: {e.message}")
except KASValidationError as e:
    print(f"Validation error: {e}")
except KASError as e:
    print(f"General KAS error: {e}")
```

## Type Safety

The SDK is fully typed and works well with mypy and IDE autocomplete:

```python
from kas_client import SearchResponse, SearchResult

async def process_results(response: SearchResponse) -> list[str]:
    return [r.title for r in response.results if r.score > 0.5]
```

## Context Manager

Both clients support context managers for automatic cleanup:

```python
# Async
async with KASClient() as client:
    results = await client.search("query")

# Sync
with KASClientSync() as client:
    results = client.search("query")
```

## License

MIT
