# Knowledge Seeder

A CLI tool and batch ingestion system for populating the Knowledge Activation System (KAS) with curated technical documentation.

## Project Status

| Metric | Value |
|--------|-------|
| **Total Documents** | 2,690 |
| **Total Chunks** | 11,846 |
| **Namespaces** | 40+ |
| **Last Updated** | January 2026 |

## Overview

Knowledge Seeder serves as the data pipeline for the Knowledge Activation System (KAS), systematically ingesting curated knowledge sources to build a comprehensive AI-ready knowledge base. The system supports multiple ingestion methods:

- **Batch API Ingestion**: Direct document ingestion via REST API
- **URL Extraction**: Web page content extraction with quality scoring
- **YouTube Transcripts**: Video transcript extraction
- **GitHub Repositories**: Documentation and README extraction
- **arXiv Papers**: Academic paper ingestion

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Knowledge Seeder                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │   Source    │───▶│   Content   │───▶│  Ingestion  │                │
│  │   Manager   │    │  Extractor  │    │   Client    │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
│         │                 │                   │                        │
│         └─────────────────┴───────────────────┘                        │
│                           │                                            │
│  ┌────────────────────────▼────────────────────────────┐              │
│  │                    State Manager                     │              │
│  │  (SQLite: tracks ingested, failed, pending)         │              │
│  └──────────────────────────────────────────────────────┘              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ HTTP POST /api/v1/ingest/batch
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   Knowledge Activation System (KAS)                     │
│                       http://localhost:8000                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │  PostgreSQL │    │   pgvector  │    │ vectorscale │                │
│  │   Storage   │    │  Embeddings │    │   Indexing  │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Namespace Taxonomy

The knowledge base is organized into the following primary namespaces:

| Namespace | Documents | Description |
|-----------|-----------|-------------|
| `default` | 865 | General/uncategorized content |
| `ai-ml` | 207 | AI/ML concepts, RAG, embeddings, agents |
| `claude` | 174 | Claude/Anthropic documentation |
| `patterns` | 173 | Design patterns, architecture |
| `infrastructure` | 173 | DevOps, Kubernetes, Docker |
| `databases` | 155 | PostgreSQL, Redis, MongoDB |
| `frameworks/python` | 150 | FastAPI, Pydantic, LangChain |
| `frameworks/javascript` | 150 | React, Next.js, TypeScript |
| `tools` | 148 | CLI tools, productivity |
| `testing` | 39 | Testing patterns, frameworks |

## Installation

```bash
# Clone the repository
cd knowledge-seeder

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

## Usage

### CLI Commands

```bash
# Validate source files
knowledge-seeder validate sources/*.yaml

# Check URL accessibility
knowledge-seeder validate sources/*.yaml --check-urls

# Test extraction (dry-run)
knowledge-seeder fetch https://example.com --dry-run

# View status
knowledge-seeder status

# Sync sources from YAML
knowledge-seeder sync sources/*.yaml --extract-only
```

### Batch API Ingestion (Python)

```python
import requests

BASE_URL = "http://localhost:8000/api/v1/ingest/batch"

def ingest_batch(documents):
    response = requests.post(
        BASE_URL,
        json={"documents": documents, "stop_on_error": False}
    )
    return response.json()

# Document format
docs = [
    {
        "content": "# Document Title\n\nContent here...",
        "title": "Document Title",
        "document_type": "markdown",
        "namespace": "namespace/path",
        "metadata": {"tags": ["tag1", "tag2", "tag3"]}
    }
]

result = ingest_batch(docs)
print(f"{result.get('succeeded', 0)} succeeded, {result.get('failed', 0)} failed")
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/stats` | GET | Get document/chunk statistics |
| `/api/v1/namespaces` | GET | List all namespaces with counts |
| `/api/v1/ingest/batch` | POST | Batch document ingestion |
| `/api/v1/ingest/source` | POST | Single source ingestion |
| `/health` | GET | Health check |

## Project Structure

```
knowledge-seeder/
├── docs/                    # Documentation
│   ├── CURRENT_STATE.md     # Current system state
│   ├── SESSION_LOG.md       # Session history
│   └── ROADMAP.md           # Future plans
├── sources/                 # Curated source definitions
│   ├── frameworks.yaml
│   ├── ai-research.yaml
│   ├── tools.yaml
│   └── ...
├── src/
│   └── knowledge_seeder/    # CLI implementation
│       ├── cli.py
│       ├── config.py
│       ├── sources/
│       ├── ingest/
│       └── state/
├── tests/
├── IMPLEMENTATION_PLAN.md   # Technical design
├── KNOWLEDGE_STRATEGY.md    # Ingestion strategy
├── DATA_ACQUISITION_ROADMAP.md
├── pyproject.toml
└── README.md
```

## Documentation

- [Current State](docs/CURRENT_STATE.md) - Current KAS statistics and namespace breakdown
- [Session Log](docs/SESSION_LOG.md) - History of ingestion sessions
- [Roadmap](docs/ROADMAP.md) - Future development plans
- [Implementation Plan](IMPLEMENTATION_PLAN.md) - Technical architecture
- [Knowledge Strategy](KNOWLEDGE_STRATEGY.md) - Content curation strategy
- [Data Acquisition Roadmap](DATA_ACQUISITION_ROADMAP.md) - Source expansion plan

## Key Accomplishments

### Critical Content Initiative (January 2026)

Successfully populated the KAS with 1,500+ technical documents covering:

- **Claude/Anthropic**: MCP, hooks, prompts, batch API, computer use, vision, streaming
- **Python Frameworks**: FastAPI, Pydantic, LangChain, LlamaIndex, async patterns
- **JavaScript Frameworks**: React hooks, Next.js, TypeScript, Zustand, React Query
- **AI/ML**: RAG patterns, embeddings, agents, evaluation, vector databases
- **Databases**: PostgreSQL, Redis, MongoDB, pgvector, connection pooling
- **Infrastructure**: Docker, Kubernetes, GitHub Actions, monitoring
- **Patterns**: DDD, hexagonal architecture, circuit breaker, saga, CQRS
- **Tools**: CLI tools, pre-commit, pytest, linting, formatting

## Contributing

1. Add sources to appropriate YAML files in `sources/`
2. Run validation: `knowledge-seeder validate sources/*.yaml`
3. Test extraction: `knowledge-seeder fetch <url> --dry-run`
4. Submit PR with source additions

## License

MIT
