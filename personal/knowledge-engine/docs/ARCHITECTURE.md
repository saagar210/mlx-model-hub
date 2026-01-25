# Knowledge Engine - Enterprise Architecture

**Version:** 1.0.0
**Date:** 2026-01-13
**Status:** Design Complete

---

## Executive Summary

Knowledge Engine is an **enterprise-grade knowledge infrastructure** designed to serve as the foundation for AI-powered applications. Unlike traditional personal knowledge management systems, this is **infrastructure for other projects to consume** via REST API and MCP (Model Context Protocol).

### Design Principles

1. **Infrastructure First**: This is plumbing for AI projects, not an end-user application
2. **Enterprise Scale**: Designed for billions of vectors, millions of graph nodes
3. **Multi-Tenant Ready**: Namespace isolation for multiple consuming projects
4. **Cost-Optimized Performance**: Use the best tools regardless of cost
5. **Observable & Debuggable**: Full tracing, metrics, and audit logging

---

## Technology Stack

### Core Framework: Cognee

**Why Cognee over alternatives:**
- Best benchmark performance (Cognee: 0.92 precision, LightRAG: 0.85, GraphRAG: 0.78)
- Native MCP support (Anthropic partnership)
- Distributed processing via Modal
- Active development (2025+ architecture)
- Graph-native design with automatic knowledge extraction

### Graph Database: Neo4j Aura Enterprise

**Configuration:**
- **Tier**: Enterprise (SOC2, HIPAA compliant)
- **Cluster**: 3-node HA cluster for production
- **Storage**: ~$0.10/GB/month at enterprise scale
- **Query Language**: Cypher (industry standard)

**Why Neo4j:**
- Most mature graph ecosystem
- Best tooling (Bloom visualization, Data Science library)
- Comprehensive enterprise support
- Native vector index support (as of 5.11+)

### Vector Database: Qdrant Cloud

**Configuration:**
- **Tier**: Enterprise cluster
- **Replication**: 3x for HA
- **Quantization**: Scalar (4x storage reduction)
- **Expected latency**: <50ms p95 at 100M vectors

**Why Qdrant:**
- Cognee's official partner
- Best price/performance ratio
- Rust-based (memory safe, fast)
- Native multi-tenancy support
- Hybrid search (dense + sparse) built-in

### Embedding Model: Voyage AI voyage-3-large

**Configuration:**
- **Dimensions**: 1024
- **Context Length**: 32,000 tokens
- **Batch Size**: 128 texts per request
- **Cost**: $0.06 per 1M tokens

**Why Voyage AI:**
- Outperforms OpenAI text-embedding-3-large by 9.74%
- Domain-adaptive (learns from your data patterns)
- Longest context window (32K vs 8K)
- Matryoshka support (dimension reduction without retraining)

### Reranking: Cohere Rerank v3.5

**Configuration:**
- **Model**: rerank-english-v3.5
- **Max documents**: 1000 per request
- **Cost**: $2 per 1000 searches

**Why Cohere Rerank:**
- Best-in-class reranking performance
- Handles long documents (4096 tokens)
- Multi-lingual support

### LLM Tier: Claude Opus 4.5 via Anthropic API

**For knowledge extraction and Q&A:**
- Primary: Claude Opus 4.5 (best reasoning)
- Fallback: Claude Sonnet 4 (cost optimization)
- Batch: Claude Haiku 3.5 (bulk processing)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CONSUMING PROJECTS                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ LocalCrew   │  │ Dev Memory  │  │ StreamMind  │  │ Future Apps │    │
│  │ Automation  │  │ Suite       │  │             │  │             │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │                │            │
│         └────────────────┴────────────────┴────────────────┘            │
│                                   │                                      │
│                          ┌────────▼────────┐                            │
│                          │   MCP Server    │ ◄── Claude Desktop/Code    │
│                          │   (stdio/SSE)   │                            │
│                          └────────┬────────┘                            │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                         KNOWLEDGE ENGINE API                             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      FastAPI REST Gateway                        │    │
│  │   /v1/ingest  /v1/search  /v1/query  /v1/graph  /v1/memory      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│         │              │              │              │                   │
│  ┌──────▼──────┐ ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐             │
│  │   Ingest    │ │  Search   │ │   Query   │ │  Memory   │             │
│  │   Engine    │ │  Engine   │ │  Engine   │ │  Manager  │             │
│  │             │ │           │ │           │ │           │             │
│  │ - Chunking  │ │ - Hybrid  │ │ - GraphRAG│ │ - Context │             │
│  │ - Extract   │ │ - Rerank  │ │ - Agentic │ │ - Session │             │
│  │ - Embed     │ │ - Filter  │ │ - Cite    │ │ - Long    │             │
│  └──────┬──────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘             │
│         │              │              │              │                   │
│         └──────────────┴──────────────┴──────────────┘                   │
│                                   │                                      │
│  ┌────────────────────────────────▼────────────────────────────────┐    │
│  │                         COGNEE CORE                              │    │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │    │
│  │   │   Cognify    │  │    Search    │  │   Prune      │          │    │
│  │   │  (Extract)   │  │   (Query)    │  │  (Maintain)  │          │    │
│  │   └──────────────┘  └──────────────┘  └──────────────┘          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                   │                                      │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                          DATA LAYER                                      │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │
│  │   Neo4j Aura    │  │  Qdrant Cloud   │  │   PostgreSQL    │          │
│  │   Enterprise    │  │   Enterprise    │  │   (Metadata)    │          │
│  │                 │  │                 │  │                 │          │
│  │  - Knowledge    │  │  - Vectors      │  │  - Audit logs   │          │
│  │    Graph        │  │  - Hybrid idx   │  │  - Sessions     │          │
│  │  - Relations    │  │  - Multi-tenant │  │  - Config       │          │
│  │  - Entities     │  │  - Payloads     │  │  - Metrics      │          │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│                       EXTERNAL SERVICES                                  │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │
│  │   Voyage AI     │  │  Cohere Rerank  │  │  Anthropic API  │          │
│  │   Embeddings    │  │   v3.5          │  │  Claude Opus    │          │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## API Design

### REST API Endpoints

```yaml
# Ingestion
POST   /v1/ingest/document     # Ingest single document
POST   /v1/ingest/batch        # Batch ingest (async job)
GET    /v1/ingest/status/{id}  # Check batch job status
DELETE /v1/ingest/{id}         # Remove document from all stores

# Search
POST   /v1/search              # Hybrid search (vector + graph + BM25)
POST   /v1/search/vector       # Vector-only search
POST   /v1/search/graph        # Graph traversal search
POST   /v1/search/semantic     # Semantic search with reranking

# Query (RAG)
POST   /v1/query               # Full RAG pipeline with citations
POST   /v1/query/stream        # Streaming RAG response
POST   /v1/query/agentic       # Agentic RAG (multi-step reasoning)

# Graph
GET    /v1/graph/entities      # List entities
GET    /v1/graph/relations     # List relations
POST   /v1/graph/traverse      # Custom Cypher traversal
POST   /v1/graph/insights      # Extract insights from subgraph

# Memory
POST   /v1/memory/store        # Store memory
GET    /v1/memory/recall       # Recall relevant memories
POST   /v1/memory/session      # Session-scoped memory
DELETE /v1/memory/{id}         # Forget specific memory

# Admin
GET    /v1/health              # Health check
GET    /v1/metrics             # Prometheus metrics
GET    /v1/namespaces          # List namespaces (multi-tenant)
POST   /v1/namespaces          # Create namespace
```

### MCP Protocol

```typescript
// Tools exposed via MCP
tools: [
  {
    name: "knowledge_search",
    description: "Search the knowledge base with hybrid retrieval",
    inputSchema: {
      query: string,
      namespace?: string,
      limit?: number,
      filters?: object
    }
  },
  {
    name: "knowledge_query",
    description: "Ask a question with full RAG pipeline",
    inputSchema: {
      question: string,
      namespace?: string,
      include_citations?: boolean
    }
  },
  {
    name: "knowledge_ingest",
    description: "Add content to the knowledge base",
    inputSchema: {
      content: string,
      metadata?: object,
      namespace?: string
    }
  },
  {
    name: "knowledge_remember",
    description: "Store a memory for later recall",
    inputSchema: {
      content: string,
      context?: string,
      namespace?: string
    }
  },
  {
    name: "knowledge_graph_query",
    description: "Query the knowledge graph directly",
    inputSchema: {
      cypher: string,
      namespace?: string
    }
  }
]

// Resources exposed via MCP
resources: [
  {
    uri: "knowledge://entities",
    name: "Knowledge Graph Entities",
    description: "Browse all entities in the knowledge graph"
  },
  {
    uri: "knowledge://recent",
    name: "Recent Knowledge",
    description: "Recently added knowledge items"
  }
]
```

---

## Data Flow

### Ingestion Pipeline

```
Document Input
      │
      ▼
┌─────────────────┐
│ Content Parser  │ ← Detect type (PDF, MD, HTML, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Semantic Chunker│ ← AI-powered boundary detection
│ (Agentic)       │   Not fixed-size, semantic units
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Entity Extract  │ ← Cognee cognify()
│ (Graph Build)   │   Extracts entities + relations
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│Voyage │ │Neo4j  │
│Embed  │ │Graph  │
└───┬───┘ └───┬───┘
    │         │
    ▼         │
┌───────┐     │
│Qdrant │     │
│Vector │     │
└───┬───┘     │
    │         │
    └────┬────┘
         ▼
┌─────────────────┐
│ PostgreSQL      │ ← Metadata, audit log
│ (Metadata)      │
└─────────────────┘
```

### Query Pipeline

```
User Query
      │
      ▼
┌─────────────────┐
│ Query Analyzer  │ ← Classify query type, extract entities
└────────┬────────┘
         │
    ┌────┴────────────┐
    ▼                 ▼
┌───────────┐   ┌───────────┐
│ Vector    │   │ Graph     │
│ Search    │   │ Traverse  │
│ (Qdrant)  │   │ (Neo4j)   │
└─────┬─────┘   └─────┬─────┘
      │               │
      └───────┬───────┘
              ▼
┌─────────────────────┐
│ Result Fusion       │ ← RRF + Graph-aware ranking
│ (Hybrid Ranking)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Cohere Rerank       │ ← Cross-encoder reranking
│ (Top-K refinement)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Claude Generation   │ ← Answer with citations
│ (RAG Synthesis)     │
└──────────┬──────────┘
           │
           ▼
      Response
```

---

## Multi-Tenancy Design

```
┌─────────────────────────────────────────────────────┐
│                    NAMESPACE: default               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ Neo4j       │ │ Qdrant      │ │ PostgreSQL  │   │
│  │ :Default    │ │ default_*   │ │ ns=default  │   │
│  └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                    NAMESPACE: localcrew             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ Neo4j       │ │ Qdrant      │ │ PostgreSQL  │   │
│  │ :LocalCrew  │ │ localcrew_* │ │ ns=localcrew│   │
│  └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                    NAMESPACE: devmemory             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │ Neo4j       │ │ Qdrant      │ │ PostgreSQL  │   │
│  │ :DevMemory  │ │ devmemory_* │ │ ns=devmemory│   │
│  └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────┘
```

**Namespace isolation guarantees:**
- Graph data isolated by Neo4j labels
- Vector data isolated by Qdrant collection prefix
- Metadata isolated by PostgreSQL namespace column
- API keys scoped to namespace(s)

---

## Observability

### Metrics (Prometheus)

```
# Latency histograms
knowledge_engine_search_duration_seconds{method="hybrid"}
knowledge_engine_query_duration_seconds{model="claude-opus"}
knowledge_engine_ingest_duration_seconds{content_type="pdf"}

# Counters
knowledge_engine_requests_total{endpoint="/v1/search"}
knowledge_engine_tokens_used_total{model="voyage-3-large"}
knowledge_engine_graph_nodes_total{namespace="default"}

# Gauges
knowledge_engine_vector_count{namespace="default"}
knowledge_engine_active_connections{service="neo4j"}
```

### Tracing (OpenTelemetry)

```
Trace: query_abc123
├── Span: query_analyzer (15ms)
├── Span: vector_search (45ms)
│   └── Span: qdrant_query (42ms)
├── Span: graph_traverse (78ms)
│   └── Span: neo4j_cypher (75ms)
├── Span: result_fusion (12ms)
├── Span: cohere_rerank (120ms)
└── Span: claude_generate (890ms)
    └── Span: anthropic_api (885ms)
```

### Logging (Structured JSON)

```json
{
  "timestamp": "2026-01-13T10:30:00Z",
  "level": "INFO",
  "trace_id": "abc123",
  "span_id": "def456",
  "service": "knowledge-engine",
  "event": "search_completed",
  "namespace": "localcrew",
  "duration_ms": 245,
  "result_count": 10,
  "vector_candidates": 100,
  "graph_hops": 2
}
```

---

## Security

### Authentication

- **API Keys**: Scoped to namespace(s), rotatable
- **JWT**: For session-based access
- **mTLS**: For service-to-service communication

### Authorization

```yaml
roles:
  admin:
    - "*"  # All operations
  writer:
    - "ingest:*"
    - "memory:store"
    - "search:*"
    - "query:*"
  reader:
    - "search:*"
    - "query:*"
    - "memory:recall"
```

### Data Protection

- **At rest**: AES-256 encryption (cloud provider)
- **In transit**: TLS 1.3
- **PII handling**: Configurable redaction pipeline
- **Audit logging**: All mutations logged with actor

---

## Deployment

### Development (Local)

```yaml
# docker-compose.dev.yml
services:
  neo4j:
    image: neo4j:5.15-enterprise
    ports: ["7474:7474", "7687:7687"]

  qdrant:
    image: qdrant/qdrant:v1.12.0
    ports: ["6333:6333"]

  postgres:
    image: postgres:16
    ports: ["5432:5432"]

  api:
    build: .
    ports: ["8000:8000"]
    environment:
      - ENVIRONMENT=development
```

### Production

```yaml
# Infrastructure
- Neo4j Aura Enterprise (managed)
- Qdrant Cloud Enterprise (managed)
- PostgreSQL via Supabase or RDS
- API on Railway/Render/Fly.io (auto-scaling)
- Redis for rate limiting + caching

# Estimated monthly cost at scale (1M documents)
- Neo4j Aura: ~$500/month
- Qdrant Cloud: ~$200/month
- Voyage AI: ~$50/month (10M tokens)
- Cohere Rerank: ~$100/month (50K searches)
- Anthropic API: ~$200/month (variable)
- Compute: ~$100/month
# Total: ~$1,150/month
```

---

## Roadmap

### Phase 1: Foundation (Week 1-2)
- [x] Architecture design
- [ ] Project structure
- [ ] Cognee integration
- [ ] Basic API endpoints
- [ ] Docker Compose dev setup

### Phase 2: Storage Layer (Week 2-3)
- [ ] Neo4j integration
- [ ] Qdrant integration
- [ ] PostgreSQL metadata store
- [ ] Multi-tenancy implementation

### Phase 3: Intelligence (Week 3-4)
- [ ] Voyage AI embeddings
- [ ] Cohere reranking
- [ ] Hybrid search fusion
- [ ] Graph-aware retrieval

### Phase 4: MCP + API (Week 4-5)
- [ ] Full REST API
- [ ] MCP server
- [ ] Authentication/Authorization
- [ ] Rate limiting

### Phase 5: Production (Week 5-6)
- [ ] Observability stack
- [ ] Cloud deployment
- [ ] Documentation
- [ ] Client SDK

---

## References

- [Cognee Documentation](https://docs.cognee.ai/)
- [Neo4j Aura](https://neo4j.com/cloud/aura/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Voyage AI](https://docs.voyageai.com/)
- [Cohere Rerank](https://docs.cohere.com/docs/rerank)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
