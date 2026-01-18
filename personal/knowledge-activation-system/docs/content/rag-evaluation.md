# RAG Evaluation: Measuring Quality with RAGAS and Beyond

Evaluating RAG systems requires measuring both retrieval quality and generation quality. RAGAS (Retrieval Augmented Generation Assessment) provides a framework for automated evaluation.

## Why Evaluate RAG?

RAG failures occur at two points:
1. **Retrieval failures**: Wrong or irrelevant documents retrieved
2. **Generation failures**: LLM misinterprets or hallucinates despite good context

Evaluation helps identify which component is failing.

## RAGAS Framework

RAGAS provides four core metrics evaluated automatically using LLMs.

### Core Metrics

| Metric | What it Measures | Range |
|--------|------------------|-------|
| **Faithfulness** | Is answer grounded in context? | 0-1 |
| **Answer Relevancy** | Does answer address the question? | 0-1 |
| **Context Precision** | Is relevant info ranked higher? | 0-1 |
| **Context Recall** | Are all relevant facts retrieved? | 0-1 |

### Installation

```bash
pip install ragas
```

### Basic Evaluation

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

# Prepare evaluation data
eval_data = {
    "question": ["What is machine learning?"],
    "answer": ["Machine learning is a subset of AI that enables systems to learn from data."],
    "contexts": [["Machine learning (ML) is a branch of artificial intelligence..."]],
    "ground_truth": ["Machine learning is a type of artificial intelligence that allows systems to learn from data without explicit programming."]
}

dataset = Dataset.from_dict(eval_data)

# Run evaluation
results = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
)

print(results)
# {'faithfulness': 0.95, 'answer_relevancy': 0.87, 'context_precision': 0.92, 'context_recall': 0.88}
```

## Metric Deep Dive

### Faithfulness

Measures if the answer is factually consistent with the retrieved context.

```python
from ragas.metrics import faithfulness

# Faithfulness = (Supported Statements) / (Total Statements)
#
# Process:
# 1. Extract claims from answer
# 2. Check each claim against context
# 3. Score = supported claims / total claims
```

**Low faithfulness indicates**: LLM hallucinating beyond context

### Answer Relevancy

Measures if the answer addresses the original question.

```python
from ragas.metrics import answer_relevancy

# Process:
# 1. Generate questions from the answer
# 2. Compare generated questions to original
# 3. Score = semantic similarity
```

**Low answer relevancy indicates**: Off-topic or incomplete answers

### Context Precision

Measures if relevant documents are ranked higher.

```python
from ragas.metrics import context_precision

# Precision@k = (Relevant items in top k) / k
# Context Precision = Mean of precision@k for all relevant items
```

**Low context precision indicates**: Retrieval ranking issues

### Context Recall

Measures if all necessary facts were retrieved.

```python
from ragas.metrics import context_recall

# Process:
# 1. Extract statements from ground truth
# 2. Check if each is in retrieved context
# 3. Score = attributed statements / total statements
```

**Low context recall indicates**: Missing relevant documents

## Retrieval-Only Metrics

Evaluate retrieval without generation.

### Mean Reciprocal Rank (MRR)

```python
def mrr_score(results: list[list[bool]]) -> float:
    """
    MRR = Mean of 1/rank of first relevant result

    Args:
        results: List of query results, each a list of relevance bools
    """
    rr_sum = 0
    for result in results:
        for rank, relevant in enumerate(result, 1):
            if relevant:
                rr_sum += 1 / rank
                break
    return rr_sum / len(results)
```

### NDCG (Normalized Discounted Cumulative Gain)

```python
import numpy as np

def dcg(relevances: list[float], k: int) -> float:
    """Discounted Cumulative Gain."""
    relevances = np.array(relevances[:k])
    positions = np.arange(1, len(relevances) + 1)
    return np.sum(relevances / np.log2(positions + 1))

def ndcg(relevances: list[float], k: int) -> float:
    """Normalized DCG."""
    ideal = sorted(relevances, reverse=True)
    return dcg(relevances, k) / dcg(ideal, k) if dcg(ideal, k) > 0 else 0
```

### Precision@K and Recall@K

```python
def precision_at_k(relevant: list[bool], k: int) -> float:
    """Precision at rank k."""
    return sum(relevant[:k]) / k

def recall_at_k(relevant: list[bool], k: int, total_relevant: int) -> float:
    """Recall at rank k."""
    return sum(relevant[:k]) / total_relevant if total_relevant > 0 else 0
```

## End-to-End Evaluation

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

def evaluate_rag_pipeline(rag_chain, test_questions, ground_truths):
    """Full RAG pipeline evaluation."""
    questions = []
    answers = []
    contexts = []

    for question in test_questions:
        # Get response from RAG chain
        response = rag_chain.invoke(question)

        questions.append(question)
        answers.append(response["answer"])
        contexts.append([doc.page_content for doc in response["context"]])

    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    })

    return evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
    )
```

## Custom Evaluation

### Semantic Similarity Scoring

```python
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

def semantic_similarity(text1: str, text2: str) -> float:
    """Compute cosine similarity between texts."""
    emb1 = model.encode(text1, convert_to_tensor=True)
    emb2 = model.encode(text2, convert_to_tensor=True)
    return util.cos_sim(emb1, emb2).item()
```

### LLM-as-Judge

```python
def llm_judge_relevance(question: str, context: str, llm) -> float:
    """Use LLM to judge context relevance."""
    prompt = f"""Rate the relevance of the context to the question on a scale of 0-1.

Question: {question}
Context: {context}

Relevance score (0-1):"""

    response = llm.invoke(prompt)
    return float(response.content.strip())
```

## Evaluation Best Practices

1. **Use diverse test sets**: Cover different query types and difficulty levels
2. **Include negative examples**: Test with queries that should return "I don't know"
3. **Human evaluation baseline**: Calibrate automated metrics against human judgment
4. **Track metrics over time**: Monitor for regression
5. **Stratify by category**: Identify weak spots in specific domains

## Diagnostic Matrix

| Faithfulness | Relevancy | Context Precision | Context Recall | Diagnosis |
|--------------|-----------|-------------------|----------------|-----------|
| Low | High | High | High | Generation issue - LLM hallucinating |
| High | Low | High | High | Prompt issue - not answering question |
| High | High | Low | High | Ranking issue - relevant docs ranked low |
| High | High | High | Low | Retrieval issue - missing relevant docs |

## Tools and Libraries

- **RAGAS**: https://github.com/explodinggradients/ragas
- **DeepEval**: https://github.com/confident-ai/deepeval
- **LangSmith**: https://smith.langchain.com (tracing + evaluation)
- **Phoenix**: https://github.com/Arize-ai/phoenix (observability)

## References

- RAGAS Paper: "RAGAS: Automated Evaluation of Retrieval Augmented Generation" (Es et al., 2023)
- RAGAS Documentation: https://docs.ragas.io
- LangChain Evaluation: https://python.langchain.com/docs/guides/evaluation/
