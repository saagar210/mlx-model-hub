# RAG: Retrieval-Augmented Generation Fundamentals

Retrieval-Augmented Generation (RAG) enhances LLM responses by grounding them in external knowledge sources, reducing hallucinations and enabling up-to-date information retrieval.

## What is RAG?

RAG combines two components:
1. **Retrieval**: Find relevant documents from a knowledge base
2. **Generation**: Use retrieved context to generate accurate responses

```
Query → Retrieve Relevant Docs → Augment Prompt with Context → Generate Response
```

## Why RAG?

| Problem | RAG Solution |
|---------|--------------|
| Knowledge cutoff | Retrieve current information |
| Hallucinations | Ground responses in retrieved facts |
| Domain expertise | Access specialized knowledge bases |
| Source attribution | Cite retrieved documents |
| Cost | Smaller model + good retrieval beats larger model |

## RAG Architecture

### Basic Pipeline

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# 1. Setup retriever
embeddings = OpenAIEmbeddings()
vectorstore = Chroma(
    persist_directory="./db",
    embedding_function=embeddings
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# 2. Create prompt template
template = """Answer the question based only on the following context:

Context: {context}

Question: {question}

Answer:"""

prompt = ChatPromptTemplate.from_template(template)

# 3. Create chain
model = ChatOpenAI(model="gpt-4")

chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | model
    | StrOutputParser()
)

# 4. Query
response = chain.invoke("What is the capital of France?")
```

### Advanced RAG with Reranking

```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank

# Add reranking step
compressor = CohereRerank(top_n=3)
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=retriever
)

# Use in chain
chain = (
    {"context": compression_retriever, "question": RunnablePassthrough()}
    | prompt
    | model
    | StrOutputParser()
)
```

## Indexing Strategies

### Chunking

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Standard chunking
splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # Characters per chunk
    chunk_overlap=200,    # Overlap for context continuity
    separators=["\n\n", "\n", ". ", " ", ""]
)

chunks = splitter.split_documents(documents)
```

### Chunk Size Guidelines

| Content Type | Chunk Size | Overlap |
|--------------|------------|---------|
| Technical docs | 500-1000 | 100-200 |
| Articles | 1000-1500 | 200-300 |
| Code | 500-800 | 50-100 |
| Q&A pairs | 200-500 | 50 |

## Retrieval Methods

### Vector Search (Semantic)

```python
# Cosine similarity search
results = vectorstore.similarity_search(query, k=5)

# With score threshold
results = vectorstore.similarity_search_with_score(
    query,
    k=10,
    score_threshold=0.7
)
```

### Keyword Search (BM25)

```python
from langchain_community.retrievers import BM25Retriever

bm25_retriever = BM25Retriever.from_documents(documents)
bm25_retriever.k = 5

results = bm25_retriever.invoke("exact keyword match")
```

### Hybrid Search

Combines vector and keyword search for better recall:

```python
from langchain.retrievers import EnsembleRetriever

# Create hybrid retriever
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.5, 0.5]  # Equal weighting
)
```

## Query Enhancement

### Query Expansion

```python
def expand_query(query: str, llm) -> list[str]:
    """Generate query variations."""
    prompt = f"""Generate 3 alternative phrasings of this query:
    Query: {query}

    Alternatives:"""
    response = llm.invoke(prompt)
    return [query] + parse_alternatives(response)
```

### Hypothetical Document Embeddings (HyDE)

```python
def hyde_retrieval(query: str, llm, retriever):
    """Generate hypothetical answer, then retrieve similar docs."""
    # Generate hypothetical answer
    prompt = f"Write a detailed answer to: {query}"
    hypothetical = llm.invoke(prompt)

    # Retrieve using hypothetical document
    return retriever.invoke(hypothetical.content)
```

## Context Formatting

### Simple Format

```python
def format_context(docs: list) -> str:
    return "\n\n".join([doc.page_content for doc in docs])
```

### With Metadata

```python
def format_context_with_sources(docs: list) -> str:
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get('source', 'Unknown')
        formatted.append(f"[{i}] Source: {source}\n{doc.page_content}")
    return "\n\n".join(formatted)
```

## Response Generation

### Basic Prompt

```python
RAG_PROMPT = """You are a helpful assistant. Answer the question based ONLY on the following context.
If you cannot answer from the context, say "I don't have enough information."

Context:
{context}

Question: {question}

Answer:"""
```

### With Citation Instructions

```python
RAG_PROMPT_CITED = """Answer the question using ONLY the provided context.
Cite your sources using [1], [2], etc.

Context:
{context}

Question: {question}

Answer (with citations):"""
```

## Common Patterns

### Multi-Query RAG

```python
def multi_query_rag(query: str, retriever, llm):
    """Generate multiple queries, retrieve for each, deduplicate."""
    # Generate query variations
    queries = generate_queries(query, llm)

    # Retrieve for each
    all_docs = []
    for q in queries:
        all_docs.extend(retriever.invoke(q))

    # Deduplicate
    unique_docs = deduplicate_by_content(all_docs)

    return unique_docs
```

### Self-RAG (Retrieve-and-Critique)

```python
def self_rag(query: str, retriever, llm):
    """RAG with self-critique of retrieval relevance."""
    docs = retriever.invoke(query)

    # Grade each document
    relevant_docs = []
    for doc in docs:
        grade = grade_relevance(query, doc, llm)
        if grade == "relevant":
            relevant_docs.append(doc)

    return generate_with_context(query, relevant_docs, llm)
```

## Best Practices

1. **Chunk wisely**: Match chunk size to query complexity
2. **Add metadata**: Enable filtering and source tracking
3. **Use hybrid search**: Combine vector + keyword for better recall
4. **Rerank results**: Quality over quantity in final context
5. **Set score thresholds**: Filter low-quality retrievals
6. **Handle no-match**: Graceful degradation when context insufficient

## References

- Original RAG Paper: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (Lewis et al., 2020)
- LangChain RAG Tutorial: https://python.langchain.com/docs/tutorials/rag/
- LlamaIndex RAG Guide: https://docs.llamaindex.ai/en/stable/
