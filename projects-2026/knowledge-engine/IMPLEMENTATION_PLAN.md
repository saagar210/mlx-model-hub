# Project 1: Modern Knowledge Engine

## Overview
A state-of-the-art personal knowledge management system with GraphRAG, hybrid search, and modern embeddings.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SvelteKit Frontend                           │
│                         (Port 5173)                                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                      FastAPI/Litestar Backend                       │
│                         (Port 8000)                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │  Ingestion  │  │   Search    │  │    Q&A      │  │  GraphRAG  │ │
│  │   Service   │  │   Service   │  │   Service   │  │  Service   │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
└─────────┼────────────────┼────────────────┼───────────────┼─────────┘
          │                │                │               │
┌─────────▼────────────────▼────────────────▼───────────────▼─────────┐
│                        Core Services Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │   Nomic     │  │   ColBERT   │  │  LlamaIndex │  │  GraphRAG  │ │
│  │ Embed V2    │  │  Reranker   │  │     RAG     │  │  (MSFT)    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                       Data Layer                                    │
│  ┌────────────────────┐  ┌────────────────────┐                    │
│  │      Qdrant        │  │    PostgreSQL      │                    │
│  │  (Vector Store)    │  │   (Metadata/KG)    │                    │
│  │   Port 6333        │  │    Port 5432       │                    │
│  └────────────────────┘  └────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Component | Technology | Why |
|-----------|------------|-----|
| **Vector DB** | Qdrant | Scales to billions, superior filtering, Rust performance |
| **Embeddings** | Nomic Embed V2 | 8K context, MoE architecture, 86.2% accuracy |
| **Reranking** | ColBERT (jina-colbert-v2) | Late interaction, 8K context, scalable |
| **RAG Framework** | LlamaIndex | Best for ingestion/indexing, modular |
| **Graph** | Microsoft GraphRAG | Knowledge graph extraction, multi-hop |
| **Backend** | FastAPI or Litestar | Litestar is 2x faster, more features |
| **Frontend** | SvelteKit | 50% smaller bundles, better perf |
| **Metadata DB** | PostgreSQL | Relational data, graph storage |

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal**: Core infrastructure and data layer

#### Tasks
1. **Docker Setup**
   ```yaml
   # docker-compose.yml
   services:
     qdrant:
       image: qdrant/qdrant:latest
       ports:
         - "6333:6333"
         - "6334:6334"
       volumes:
         - qdrant_storage:/qdrant/storage

     postgres:
       image: postgres:16
       environment:
         POSTGRES_DB: knowledge_engine
         POSTGRES_USER: ke_user
         POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
       ports:
         - "5432:5432"
       volumes:
         - postgres_data:/var/lib/postgresql/data
   ```

2. **Project Structure**
   ```
   knowledge-engine/
   ├── backend/
   │   ├── src/
   │   │   ├── api/
   │   │   │   ├── routes/
   │   │   │   │   ├── ingest.py
   │   │   │   │   ├── search.py
   │   │   │   │   ├── qa.py
   │   │   │   │   └── graph.py
   │   │   │   └── app.py
   │   │   ├── services/
   │   │   │   ├── embedding.py
   │   │   │   ├── reranking.py
   │   │   │   ├── search.py
   │   │   │   ├── graphrag.py
   │   │   │   └── ingestion.py
   │   │   ├── models/
   │   │   │   ├── document.py
   │   │   │   ├── chunk.py
   │   │   │   └── entity.py
   │   │   └── config.py
   │   ├── tests/
   │   ├── pyproject.toml
   │   └── Dockerfile
   ├── frontend/
   │   ├── src/
   │   │   ├── routes/
   │   │   ├── lib/
   │   │   └── components/
   │   ├── package.json
   │   └── svelte.config.js
   ├── docker-compose.yml
   └── README.md
   ```

3. **Core Dependencies**
   ```toml
   # pyproject.toml
   [project]
   name = "knowledge-engine"
   version = "0.1.0"
   requires-python = ">=3.12"
   dependencies = [
       "fastapi>=0.115.0",
       "uvicorn>=0.30.0",
       "llama-index>=0.12.0",
       "llama-index-vector-stores-qdrant>=0.9.0",
       "llama-index-embeddings-huggingface>=0.5.0",
       "qdrant-client>=1.16.0",
       "nomic>=3.9.0",
       "graphrag>=2.7.0",
       "asyncpg>=0.30.0",
       "sqlmodel>=0.0.22",
       "pydantic>=2.10.0",
       "trafilatura>=2.0.0",
   ]
   ```

#### Deliverables
- [ ] Docker Compose running Qdrant + PostgreSQL
- [ ] FastAPI skeleton with health checks
- [ ] Qdrant connection verified
- [ ] PostgreSQL schema for metadata

---

### Phase 2: Embedding & Indexing (Week 2)
**Goal**: Document ingestion with modern embeddings

#### Tasks
1. **Nomic Embed V2 Integration**
   ```python
   # services/embedding.py
   from nomic import embed
   import numpy as np

   class EmbeddingService:
       def __init__(self, model_name: str = "nomic-embed-text-v2"):
           self.model_name = model_name

       async def embed_texts(self, texts: list[str]) -> np.ndarray:
           """Embed texts using Nomic V2 (8K context, MoE)"""
           output = embed.text(
               texts=texts,
               model=self.model_name,
               task_type="search_document"  # or "search_query" for queries
           )
           return np.array(output['embeddings'])

       async def embed_query(self, query: str) -> np.ndarray:
           """Embed query with query-specific task type"""
           output = embed.text(
               texts=[query],
               model=self.model_name,
               task_type="search_query"
           )
           return np.array(output['embeddings'][0])
   ```

2. **Chunking Strategy**
   ```python
   # services/chunking.py
   from llama_index.core.node_parser import SentenceSplitter

   class ChunkingService:
       def __init__(
           self,
           chunk_size: int = 1024,  # Larger chunks for Nomic's 8K context
           chunk_overlap: int = 200
       ):
           self.splitter = SentenceSplitter(
               chunk_size=chunk_size,
               chunk_overlap=chunk_overlap
           )

       def chunk_document(self, text: str, metadata: dict) -> list[dict]:
           """Chunk document preserving context"""
           nodes = self.splitter.get_nodes_from_documents([
               Document(text=text, metadata=metadata)
           ])
           return [
               {
                   "text": node.text,
                   "metadata": node.metadata,
                   "start_char": node.start_char_idx,
                   "end_char": node.end_char_idx,
               }
               for node in nodes
           ]
   ```

3. **Qdrant Indexing**
   ```python
   # services/indexing.py
   from qdrant_client import QdrantClient
   from qdrant_client.models import VectorParams, Distance, PointStruct

   class IndexingService:
       def __init__(self, qdrant_url: str = "http://localhost:6333"):
           self.client = QdrantClient(url=qdrant_url)
           self.collection_name = "knowledge"

       async def create_collection(self):
           """Create collection with optimal settings for Nomic V2"""
           self.client.create_collection(
               collection_name=self.collection_name,
               vectors_config=VectorParams(
                   size=768,  # Nomic V2 dimension
                   distance=Distance.COSINE,
                   on_disk=True  # For large collections
               ),
               # Enable payload indexing for filtering
               optimizers_config={
                   "indexing_threshold": 20000
               }
           )

       async def index_chunks(self, chunks: list[dict], embeddings: np.ndarray):
           """Index chunks with embeddings"""
           points = [
               PointStruct(
                   id=str(uuid4()),
                   vector=embedding.tolist(),
                   payload={
                       "text": chunk["text"],
                       "source": chunk["metadata"].get("source"),
                       "created_at": datetime.utcnow().isoformat(),
                       **chunk["metadata"]
                   }
               )
               for chunk, embedding in zip(chunks, embeddings)
           ]
           self.client.upsert(
               collection_name=self.collection_name,
               points=points
           )
   ```

#### Deliverables
- [ ] Nomic V2 embedding service working
- [ ] Chunking with configurable sizes
- [ ] Qdrant collection with proper schema
- [ ] Basic ingestion pipeline

---

### Phase 3: Hybrid Search & Reranking (Week 3)
**Goal**: Production-quality retrieval

#### Tasks
1. **Hybrid Search (Vector + BM25)**
   ```python
   # services/search.py
   from qdrant_client.models import Filter, FieldCondition, MatchValue

   class SearchService:
       def __init__(
           self,
           qdrant: QdrantClient,
           embedding_service: EmbeddingService,
           reranker: RerankerService
       ):
           self.qdrant = qdrant
           self.embedder = embedding_service
           self.reranker = reranker

       async def hybrid_search(
           self,
           query: str,
           top_k: int = 20,
           rerank_top_k: int = 5,
           filters: dict | None = None
       ) -> list[SearchResult]:
           """Hybrid search with reranking"""
           # 1. Vector search
           query_embedding = await self.embedder.embed_query(query)

           vector_results = self.qdrant.search(
               collection_name="knowledge",
               query_vector=query_embedding.tolist(),
               limit=top_k,
               query_filter=self._build_filter(filters) if filters else None
           )

           # 2. BM25 search (using Qdrant's full-text search)
           bm25_results = self.qdrant.scroll(
               collection_name="knowledge",
               scroll_filter=Filter(
                   must=[
                       FieldCondition(
                           key="text",
                           match=MatchValue(value=query)
                       )
                   ]
               ),
               limit=top_k
           )[0]

           # 3. Reciprocal Rank Fusion
           fused_results = self._rrf_fusion(vector_results, bm25_results)

           # 4. Rerank top results
           if self.reranker:
               texts = [r.payload["text"] for r in fused_results[:top_k]]
               reranked = await self.reranker.rerank(query, texts)
               return reranked[:rerank_top_k]

           return fused_results[:rerank_top_k]

       def _rrf_fusion(self, *result_lists, k: int = 60) -> list:
           """Reciprocal Rank Fusion"""
           scores = {}
           for results in result_lists:
               for rank, result in enumerate(results):
                   doc_id = result.id
                   if doc_id not in scores:
                       scores[doc_id] = {"score": 0, "result": result}
                   scores[doc_id]["score"] += 1 / (k + rank + 1)

           sorted_results = sorted(
               scores.values(),
               key=lambda x: x["score"],
               reverse=True
           )
           return [item["result"] for item in sorted_results]
   ```

2. **ColBERT Reranking**
   ```python
   # services/reranking.py
   from FlagEmbedding import FlagReranker

   class RerankerService:
       def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
           # Using BGE reranker (ColBERT-style late interaction)
           self.reranker = FlagReranker(
               model_name,
               use_fp16=True  # For M-series Macs
           )

       async def rerank(
           self,
           query: str,
           documents: list[str],
           top_k: int = 5
       ) -> list[dict]:
           """Rerank documents using cross-encoder"""
           pairs = [[query, doc] for doc in documents]
           scores = self.reranker.compute_score(pairs)

           # Sort by score
           scored_docs = list(zip(documents, scores))
           scored_docs.sort(key=lambda x: x[1], reverse=True)

           return [
               {"text": doc, "score": score}
               for doc, score in scored_docs[:top_k]
           ]
   ```

#### Deliverables
- [ ] Hybrid search (vector + BM25) working
- [ ] RRF fusion implemented
- [ ] ColBERT/BGE reranking integrated
- [ ] Search API endpoint

---

### Phase 4: GraphRAG Integration (Week 4)
**Goal**: Knowledge graph for multi-hop reasoning

#### Tasks
1. **Microsoft GraphRAG Setup**
   ```python
   # services/graphrag.py
   from graphrag.index import create_pipeline_config
   from graphrag.query import GlobalSearch, LocalSearch

   class GraphRAGService:
       def __init__(self, data_dir: str = "./graphrag_data"):
           self.data_dir = data_dir
           self.config = self._create_config()

       def _create_config(self):
           """Configure GraphRAG for local LLMs"""
           return create_pipeline_config(
               root_dir=self.data_dir,
               # Use local Ollama for entity extraction
               llm={
                   "type": "openai_chat",
                   "api_base": "http://localhost:11434/v1",
                   "model": "deepseek-r1:14b",
                   "api_key": "ollama"  # Dummy key for Ollama
               },
               embeddings={
                   "type": "openai_embedding",
                   "api_base": "http://localhost:11434/v1",
                   "model": "nomic-embed-text",
                   "api_key": "ollama"
               }
           )

       async def build_graph(self, documents: list[str]):
           """Extract entities and relationships"""
           # GraphRAG pipeline:
           # 1. Entity extraction
           # 2. Relationship extraction
           # 3. Community detection
           # 4. Summary generation
           pass  # Implementation follows GraphRAG docs

       async def query(
           self,
           query: str,
           search_type: str = "local"  # "local" or "global"
       ) -> str:
           """Query the knowledge graph"""
           if search_type == "local":
               searcher = LocalSearch(self.config)
           else:
               searcher = GlobalSearch(self.config)

           result = await searcher.search(query)
           return result.response
   ```

2. **Hybrid RAG + GraphRAG**
   ```python
   # services/qa.py
   class QAService:
       def __init__(
           self,
           search_service: SearchService,
           graphrag_service: GraphRAGService,
           llm_client: OllamaClient
       ):
           self.search = search_service
           self.graph = graphrag_service
           self.llm = llm_client

       async def answer(
           self,
           question: str,
           use_graph: bool = True
       ) -> QAResponse:
           """Answer question using hybrid RAG + GraphRAG"""
           # 1. Standard RAG retrieval
           rag_context = await self.search.hybrid_search(question)

           # 2. GraphRAG for multi-hop (if enabled)
           graph_context = ""
           if use_graph:
               graph_context = await self.graph.query(question)

           # 3. Combine contexts
           combined_context = self._merge_contexts(rag_context, graph_context)

           # 4. Generate answer
           prompt = self._build_prompt(question, combined_context)
           response = await self.llm.generate(prompt)

           return QAResponse(
               answer=response,
               sources=rag_context,
               graph_context=graph_context,
               confidence=self._calculate_confidence(response, rag_context)
           )
   ```

#### Deliverables
- [ ] GraphRAG configured for local LLMs
- [ ] Entity/relationship extraction working
- [ ] Local and global search modes
- [ ] Hybrid RAG + GraphRAG pipeline

---

### Phase 5: Content Ingestion (Week 5)
**Goal**: Multi-source content ingestion

#### Supported Sources
1. **Web Pages** (Trafilatura)
2. **YouTube** (Transcripts + Whisper fallback)
3. **PDFs** (PyMuPDF)
4. **Local Files** (Markdown, text)
5. **Obsidian Vault** (Direct integration)

```python
# services/ingestion/web.py
import trafilatura

class WebIngestionService:
    async def ingest_url(self, url: str) -> Document:
        """Extract clean content from web page"""
        downloaded = trafilatura.fetch_url(url)
        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            output_format="markdown"
        )
        return Document(
            content=content,
            source=url,
            source_type="web",
            metadata={"url": url}
        )
```

#### Deliverables
- [ ] Web ingestion with Trafilatura
- [ ] YouTube transcript extraction
- [ ] PDF parsing
- [ ] Obsidian vault sync
- [ ] Ingestion API endpoints

---

### Phase 6: SvelteKit Frontend (Week 6)
**Goal**: Modern, performant UI

#### Features
1. **Search Interface** - Hybrid search with filters
2. **Q&A Chat** - GraphRAG-powered answers
3. **Knowledge Graph Visualization** - D3.js graph view
4. **Ingestion Dashboard** - Add content sources
5. **Daily Review** - Spaced repetition (optional)

```svelte
<!-- src/routes/+page.svelte -->
<script lang="ts">
  import { searchKnowledge } from '$lib/api';
  import SearchResults from '$lib/components/SearchResults.svelte';

  let query = '';
  let results = [];
  let loading = false;

  async function handleSearch() {
    loading = true;
    results = await searchKnowledge(query);
    loading = false;
  }
</script>

<main class="container mx-auto p-4">
  <h1 class="text-3xl font-bold mb-8">Knowledge Engine</h1>

  <div class="search-box">
    <input
      type="text"
      bind:value={query}
      on:keypress={(e) => e.key === 'Enter' && handleSearch()}
      placeholder="Search your knowledge..."
      class="w-full p-4 border rounded-lg"
    />
  </div>

  {#if loading}
    <div class="loading">Searching...</div>
  {:else}
    <SearchResults {results} />
  {/if}
</main>
```

#### Deliverables
- [ ] SvelteKit project setup
- [ ] Search UI with real-time results
- [ ] Q&A interface
- [ ] Knowledge graph visualization
- [ ] Responsive design

---

## API Specification

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/url` | Ingest web page |
| POST | `/api/ingest/file` | Upload and ingest file |
| POST | `/api/ingest/youtube` | Ingest YouTube video |
| GET | `/api/search` | Hybrid search |
| POST | `/api/qa` | Ask question |
| GET | `/api/graph/entities` | Get knowledge graph entities |
| GET | `/api/graph/query` | GraphRAG query |
| GET | `/api/health` | Health check |

### Example Requests

```bash
# Search
curl -X GET "http://localhost:8000/api/search?q=RAG+best+practices&top_k=5"

# Q&A
curl -X POST "http://localhost:8000/api/qa" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the key differences between RAG and GraphRAG?"}'

# Ingest URL
curl -X POST "http://localhost:8000/api/ingest/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

---

## Configuration

```yaml
# config.yaml
database:
  qdrant:
    url: "http://localhost:6333"
    collection: "knowledge"
  postgres:
    url: "postgresql://ke_user:password@localhost:5432/knowledge_engine"

embeddings:
  model: "nomic-embed-text-v2"
  dimension: 768
  batch_size: 32

reranking:
  model: "BAAI/bge-reranker-v2-m3"
  top_k: 5

graphrag:
  llm_model: "deepseek-r1:14b"
  llm_base_url: "http://localhost:11434/v1"

chunking:
  chunk_size: 1024
  chunk_overlap: 200

search:
  hybrid_weight: 0.7  # Vector weight (1-weight = BM25 weight)
  initial_top_k: 20
  rerank_top_k: 5
```

---

## Testing Strategy

### Unit Tests
- Embedding service
- Chunking logic
- Search fusion
- Reranking

### Integration Tests
- Full ingestion pipeline
- Search + rerank pipeline
- GraphRAG queries

### Evaluation
- RAGAS metrics (see Project 7)
- Manual quality assessment

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Search latency (p95) | < 500ms |
| Reranking latency | < 200ms |
| GraphRAG query latency | < 3s |
| Retrieval accuracy (NDCG@5) | > 0.75 |
| Q&A faithfulness | > 0.85 |

---

## Timeline Summary

| Week | Phase | Key Deliverable |
|------|-------|-----------------|
| 1 | Foundation | Docker, FastAPI, Qdrant |
| 2 | Embedding | Nomic V2, chunking, indexing |
| 3 | Search | Hybrid search, reranking |
| 4 | GraphRAG | Knowledge graph, multi-hop |
| 5 | Ingestion | Multi-source ingestion |
| 6 | Frontend | SvelteKit UI |

**Total: 6 weeks to production-ready Knowledge Engine**
