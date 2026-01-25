# Knowledge Seeder - Claude Code Instructions

## Project Overview

Knowledge Seeder is a CLI tool and batch ingestion system for populating the Knowledge Activation System (KAS) with curated technical documentation. The KAS is a PostgreSQL-based knowledge base with vector search capabilities (pgvector, vectorscale).

## Key Information

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `http://localhost:8000/api/v1/stats` | GET | System statistics |
| `http://localhost:8000/api/v1/namespaces` | GET | List all namespaces |
| `http://localhost:8000/api/v1/ingest/batch` | POST | Batch document ingestion |
| `http://localhost:8000/health` | GET | Health check |

### Current State (January 2026)

- **Total Documents**: 2,690
- **Total Chunks**: 11,846
- **Primary Namespaces**: claude, ai-ml, patterns, infrastructure, databases, frameworks/python, frameworks/javascript, tools

## Batch Ingestion Pattern

Use Python scripts for batch ingestion (avoid curl with complex JSON):

```python
import requests

BASE_URL = "http://localhost:8000/api/v1/ingest/batch"

def ingest_batch(documents):
    response = requests.post(
        BASE_URL,
        json={"documents": documents, "stop_on_error": False}
    )
    return response.json()

docs = [
    {
        "content": "# Title\n\nContent here...",
        "title": "Document Title",
        "document_type": "markdown",
        "namespace": "namespace/path",
        "metadata": {"tags": ["tag1", "tag2", "tag3"]}
    }
]

result = ingest_batch(docs)
print(f"{result.get('succeeded', 0)} succeeded, {result.get('failed', 0)} failed")
```

## Document Format Requirements

- **content**: Markdown content (minimum 100 words recommended)
- **title**: Clear, descriptive title
- **document_type**: Usually "markdown"
- **namespace**: Follow taxonomy (see below)
- **metadata.tags**: Minimum 3 relevant tags

## Namespace Taxonomy

```
claude/              # Claude/Anthropic documentation
ai-ml/               # AI/ML concepts, RAG, embeddings
patterns/            # Design patterns, architecture
infrastructure/      # DevOps, Kubernetes, Docker
databases/           # PostgreSQL, Redis, MongoDB
frameworks/python/   # FastAPI, Pydantic, LangChain
frameworks/javascript/ # React, Next.js, TypeScript
tools/               # CLI tools, productivity
testing/             # Testing patterns
security/            # Security patterns
```

## Common Tasks

### Check Current Stats
```bash
curl -s http://localhost:8000/api/v1/stats | python3 -m json.tool
```

### Get Namespace Breakdown
```bash
curl -s http://localhost:8000/api/v1/namespaces | python3 -c "
import sys, json
data = json.load(sys.stdin)
ns = data.get('namespaces', data)
for n in sorted(ns, key=lambda x: x.get('document_count', 0), reverse=True)[:20]:
    print(f\"{n['name']}: {n['document_count']} docs\")
"
```

### Batch Ingest Documents
1. Create Python script with documents array
2. Use `requests.post()` to the batch endpoint
3. Check response for succeeded/failed counts

## Avoiding Common Issues

1. **JSON Escape Errors**: Use Python scripts instead of curl for complex content
2. **Special Characters**: Python triple-quotes handle all special chars
3. **Batch Size**: Process 5-10 documents per batch for reliability
4. **Tags**: Always include minimum 3 relevant tags

## Project Structure

```
knowledge-seeder/
├── docs/                    # Documentation
│   ├── CURRENT_STATE.md     # System statistics
│   ├── SESSION_LOG.md       # Session history
│   └── ROADMAP.md           # Future plans
├── sources/                 # YAML source definitions
├── src/knowledge_seeder/    # CLI implementation
├── IMPLEMENTATION_PLAN.md   # Technical architecture
├── KNOWLEDGE_STRATEGY.md    # Content strategy
└── DATA_ACQUISITION_ROADMAP.md
```

## When Adding Content

1. Choose appropriate namespace from taxonomy
2. Include minimum 3 descriptive tags
3. Use markdown format with headers
4. Include code examples where applicable
5. Process in batches of 5-10 documents
6. Verify ingestion via stats endpoint

## Key Files to Reference

- `docs/CURRENT_STATE.md` - Current system state
- `docs/ROADMAP.md` - Future plans and targets
- `KNOWLEDGE_STRATEGY.md` - Content curation guidelines
- `sources/*.yaml` - Existing source definitions
