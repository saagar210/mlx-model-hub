# Hybrid Search Strategies for RAG

Hybrid search combines multiple retrieval methods to achieve better recall and precision than any single method alone. The most common combination is BM25 (keyword) + vector (semantic) search.

## Why Hybrid Search?

| Search Type | Strengths | Weaknesses |
|------------|-----------|------------|
| **BM25/Keyword** | Exact matches, rare terms, acronyms | Misses synonyms, context |
| **Vector/Semantic** | Understands meaning, synonyms | Can miss exact phrases, numbers |
| **Hybrid** | Best of both worlds | More complex, requires fusion |

### Example Query Analysis

Query: "How do I configure the HNSW index in pgvector?"

- **BM25 finds**: Documents containing "HNSW", "pgvector", "configure"
- **Vector finds**: Documents about vector indexing, even with different terminology
- **Hybrid finds**: Both exact matches AND semantically similar content

## BM25 (Best Match 25)

BM25 is a probabilistic ranking function based on term frequency.

### BM25 Formula

```
score(D, Q) = Σ IDF(qi) · (f(qi, D) · (k1 + 1)) / (f(qi, D) + k1 · (1 - b + b · |D|/avgdl))
```

Where:
- `f(qi, D)` = term frequency in document
- `|D|` = document length
- `avgdl` = average document length
- `k1` = term saturation parameter (typically 1.2-2.0)
- `b` = length normalization (typically 0.75)

### PostgreSQL BM25 with pg_search

```sql
-- Enable pg_search extension
CREATE EXTENSION pg_search;

-- Create BM25 index
CALL paradedb.create_bm25(
    index_name => 'content_idx',
    table_name => 'content',
    key_field => 'id',
    text_fields => '{"title": {}, "body": {"tokenizer": "en_stem"}}'
);

-- Search
SELECT id, title, paradedb.score(id) as score
FROM content
WHERE content @@@ 'hybrid search RAG'
ORDER BY score DESC
LIMIT 10;
```

### Python BM25 Implementation

```python
from rank_bm25 import BM25Okapi
import nltk

# Prepare corpus
corpus = [doc.page_content for doc in documents]
tokenized = [nltk.word_tokenize(doc.lower()) for doc in corpus]

# Create index
bm25 = BM25Okapi(tokenized)

# Search
query_tokens = nltk.word_tokenize(query.lower())
scores = bm25.get_scores(query_tokens)
top_indices = scores.argsort()[-10:][::-1]
```

## Vector Search

Vector search finds semantically similar content using embeddings.

### PostgreSQL with pgvector

```sql
-- Enable extension
CREATE EXTENSION vector;

-- Create table with vector column
CREATE TABLE embeddings (
    id UUID PRIMARY KEY,
    content TEXT,
    embedding vector(768)  -- Dimension matches model
);

-- Create HNSW index for fast search
CREATE INDEX ON embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Cosine similarity search
SELECT id, content, 1 - (embedding <=> $1) as similarity
FROM embeddings
ORDER BY embedding <=> $1  -- <=> is cosine distance
LIMIT 10;
```

### Python Vector Search

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')

# Index documents
embeddings = model.encode([doc.page_content for doc in documents])

# Search
query_embedding = model.encode(query)
similarities = np.dot(embeddings, query_embedding)
top_indices = similarities.argsort()[-10:][::-1]
```

## Fusion Strategies

### Reciprocal Rank Fusion (RRF)

RRF combines rankings from multiple sources without requiring score normalization.

```python
def reciprocal_rank_fusion(
    rankings: list[list[str]],  # List of ranked document IDs
    k: int = 60  # Constant to prevent division by small numbers
) -> list[tuple[str, float]]:
    """
    RRF Score = Σ (1 / (k + rank))

    Args:
        rankings: Multiple ranked lists of document IDs
        k: RRF constant (default 60, per original paper)

    Returns:
        List of (doc_id, score) sorted by combined score
    """
    scores = {}

    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            if doc_id not in scores:
                scores[doc_id] = 0
            scores[doc_id] += 1 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### Weighted Score Fusion

```python
def weighted_fusion(
    bm25_results: list[tuple[str, float]],
    vector_results: list[tuple[str, float]],
    bm25_weight: float = 0.3,
    vector_weight: float = 0.7
) -> list[tuple[str, float]]:
    """Combine normalized scores with weights."""

    # Normalize scores to 0-1
    def normalize(results):
        if not results:
            return {}
        max_score = max(r[1] for r in results)
        min_score = min(r[1] for r in results)
        range_score = max_score - min_score or 1
        return {r[0]: (r[1] - min_score) / range_score for r in results}

    bm25_norm = normalize(bm25_results)
    vector_norm = normalize(vector_results)

    # Combine scores
    all_ids = set(bm25_norm.keys()) | set(vector_norm.keys())
    combined = {}

    for doc_id in all_ids:
        combined[doc_id] = (
            bm25_weight * bm25_norm.get(doc_id, 0) +
            vector_weight * vector_norm.get(doc_id, 0)
        )

    return sorted(combined.items(), key=lambda x: x[1], reverse=True)
```

## Complete Hybrid Search Implementation

```python
from dataclasses import dataclass
from typing import Optional
import asyncio

@dataclass
class SearchResult:
    doc_id: str
    content: str
    score: float
    bm25_score: Optional[float] = None
    vector_score: Optional[float] = None

async def hybrid_search(
    query: str,
    db,
    embedder,
    limit: int = 10,
    rrf_k: int = 60
) -> list[SearchResult]:
    """
    Perform hybrid search with RRF fusion.

    Args:
        query: Search query
        db: Database connection
        embedder: Embedding model
        limit: Number of results
        rrf_k: RRF constant

    Returns:
        Fused search results
    """
    # Run searches in parallel
    bm25_task = asyncio.create_task(db.bm25_search(query, limit=limit * 2))

    query_embedding = await embedder.embed(query)
    vector_task = asyncio.create_task(db.vector_search(query_embedding, limit=limit * 2))

    bm25_results, vector_results = await asyncio.gather(bm25_task, vector_task)

    # RRF fusion
    scores = {}
    metadata = {}

    for rank, (doc_id, content, bm25_score) in enumerate(bm25_results, 1):
        scores[doc_id] = 1 / (rrf_k + rank)
        metadata[doc_id] = {"content": content, "bm25_score": bm25_score}

    for rank, (doc_id, content, vector_score) in enumerate(vector_results, 1):
        if doc_id not in scores:
            scores[doc_id] = 0
            metadata[doc_id] = {"content": content}
        scores[doc_id] += 1 / (rrf_k + rank)
        metadata[doc_id]["vector_score"] = vector_score

    # Build results
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    return [
        SearchResult(
            doc_id=doc_id,
            content=metadata[doc_id]["content"],
            score=scores[doc_id],
            bm25_score=metadata[doc_id].get("bm25_score"),
            vector_score=metadata[doc_id].get("vector_score")
        )
        for doc_id in sorted_ids[:limit]
    ]
```

## Tuning Hybrid Search

### RRF k Parameter

- Lower k (20-40): More emphasis on top-ranked results
- Higher k (60-100): More balanced across ranks
- Default: k=60 from original paper

### Candidate Pool Size

```python
# Retrieve more candidates for fusion than final limit
# Typically 2-3x the desired output
bm25_candidates = limit * 2
vector_candidates = limit * 2
```

### When to Weight BM25 Higher

- Queries with specific technical terms, acronyms
- Exact phrase matching needed
- Proper nouns, code identifiers

### When to Weight Vector Higher

- Conceptual questions
- Queries using synonyms
- Cross-lingual search

## Best Practices

1. **Parallel execution**: Run BM25 and vector search concurrently
2. **Over-fetch then fuse**: Get more candidates than needed for better fusion
3. **Index both**: Maintain BM25 and vector indexes on same data
4. **Monitor hit rates**: Track which method contributes more results
5. **Add reranking**: Apply cross-encoder reranking after fusion

## References

- RRF Paper: "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods" (Cormack et al., 2009)
- BM25 Paper: "The Probabilistic Relevance Framework: BM25 and Beyond" (Robertson & Zaragoza, 2009)
- pgvector: https://github.com/pgvector/pgvector
- pg_search: https://github.com/paradedb/paradedb
