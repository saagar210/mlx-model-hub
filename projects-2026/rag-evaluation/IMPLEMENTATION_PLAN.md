# Project 7: RAG Evaluation Suite

## Overview
A comprehensive evaluation framework for testing RAG pipelines using RAGAS, DeepEval, and FlashRAG. Provides automated testing, benchmarking, and continuous evaluation for the Knowledge Engine and other RAG systems.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      RAG Evaluation Suite                           │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                        Evaluation Pipeline                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   Dataset    │  │   RAG        │  │   Metrics    │             │
│  │   Manager    │──▶│   Runner     │──▶│   Engine     │             │
│  │              │  │              │  │              │             │
│  └──────────────┘  └──────────────┘  └──────────────┘             │
│         │                 │                 │                       │
│         │                 │                 │                       │
│  ┌──────▼─────────────────▼─────────────────▼──────┐              │
│  │                   Report Generator               │              │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐         │              │
│  │  │   HTML  │  │  JSON   │  │Dashboard│         │              │
│  │  │  Report │  │  Export │  │   UI    │         │              │
│  │  └─────────┘  └─────────┘  └─────────┘         │              │
│  └──────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    RAGAS     │       │   DeepEval   │       │  FlashRAG    │
│  (Metrics)   │       │ (Test Cases) │       │ (Benchmark)  │
└──────────────┘       └──────────────┘       └──────────────┘
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Core Metrics** | RAGAS | Faithfulness, relevancy, context precision |
| **Test Framework** | DeepEval | LLM-based test cases, assertions |
| **Benchmarking** | FlashRAG | Standard RAG benchmarks |
| **Dashboard** | SvelteKit | Evaluation results visualization |
| **Storage** | SQLite + JSON | Results persistence |

## Key Metrics

### RAGAS Metrics
- **Faithfulness**: How factually accurate is the response given the context?
- **Answer Relevancy**: How relevant is the answer to the question?
- **Context Precision**: Are the retrieved contexts relevant?
- **Context Recall**: Are all relevant contexts retrieved?
- **Answer Correctness**: Overall correctness of the answer

### DeepEval Metrics
- **Hallucination**: Detection of fabricated information
- **Toxicity**: Safety and appropriateness
- **Bias**: Fairness in responses
- **Summarization**: Quality of condensed information

### Custom Metrics
- **Latency**: End-to-end response time
- **Token Efficiency**: Tokens used vs. quality
- **Source Attribution**: Correct citation of sources

## Project Structure

```
rag-evaluation/
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── datasets/
│   │   ├── __init__.py
│   │   ├── loader.py        # Dataset loading
│   │   ├── generator.py     # Synthetic data generation
│   │   └── presets.py       # Built-in test datasets
│   ├── evaluators/
│   │   ├── __init__.py
│   │   ├── ragas_eval.py    # RAGAS integration
│   │   ├── deepeval_eval.py # DeepEval integration
│   │   └── custom.py        # Custom metrics
│   ├── runners/
│   │   ├── __init__.py
│   │   ├── rag_runner.py    # RAG pipeline runner
│   │   └── batch.py         # Batch evaluation
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── generator.py     # Report generation
│   │   ├── html.py          # HTML reports
│   │   └── json_export.py   # JSON export
│   ├── dashboard/
│   │   └── (SvelteKit app)
│   └── config.py
├── datasets/
│   ├── samples/             # Sample test datasets
│   └── benchmarks/          # Standard benchmarks
├── tests/
├── pyproject.toml
└── README.md
```

## Implementation

### Phase 1: Core Framework (Week 1)

#### Dataset Manager
```python
# src/datasets/loader.py
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import json

@dataclass
class EvalSample:
    question: str
    ground_truth: str
    contexts: Optional[list[str]] = None
    metadata: Optional[dict] = None

@dataclass
class EvalDataset:
    name: str
    samples: list[EvalSample]
    description: str = ""

class DatasetLoader:
    def __init__(self, datasets_dir: Path = Path("datasets")):
        self.datasets_dir = datasets_dir

    def load_json(self, filepath: Path) -> EvalDataset:
        """Load dataset from JSON file."""
        with open(filepath) as f:
            data = json.load(f)

        samples = [
            EvalSample(
                question=s["question"],
                ground_truth=s["ground_truth"],
                contexts=s.get("contexts"),
                metadata=s.get("metadata")
            )
            for s in data["samples"]
        ]

        return EvalDataset(
            name=data.get("name", filepath.stem),
            samples=samples,
            description=data.get("description", "")
        )

    def load_csv(self, filepath: Path) -> EvalDataset:
        """Load dataset from CSV file."""
        import csv

        samples = []
        with open(filepath) as f:
            reader = csv.DictReader(f)
            for row in reader:
                samples.append(EvalSample(
                    question=row["question"],
                    ground_truth=row["ground_truth"],
                    contexts=row.get("contexts", "").split("|") if row.get("contexts") else None
                ))

        return EvalDataset(
            name=filepath.stem,
            samples=samples
        )

    def load_preset(self, preset_name: str) -> EvalDataset:
        """Load a built-in preset dataset."""
        presets = {
            "basic_qa": self._create_basic_qa(),
            "multi_hop": self._create_multi_hop(),
            "factual": self._create_factual()
        }

        if preset_name not in presets:
            raise ValueError(f"Unknown preset: {preset_name}. Available: {list(presets.keys())}")

        return presets[preset_name]

    def _create_basic_qa(self) -> EvalDataset:
        """Create basic Q&A test dataset."""
        return EvalDataset(
            name="basic_qa",
            description="Basic question-answering evaluation",
            samples=[
                EvalSample(
                    question="What is machine learning?",
                    ground_truth="Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
                ),
                EvalSample(
                    question="What is a neural network?",
                    ground_truth="A neural network is a computing system inspired by biological neural networks, consisting of interconnected nodes that process information.",
                ),
                # Add more samples...
            ]
        )

    def _create_multi_hop(self) -> EvalDataset:
        """Create multi-hop reasoning test dataset."""
        return EvalDataset(
            name="multi_hop",
            description="Multi-hop reasoning evaluation",
            samples=[
                EvalSample(
                    question="What is the capital of the country where the Eiffel Tower is located?",
                    ground_truth="Paris is the capital of France, where the Eiffel Tower is located.",
                ),
                # Add more samples...
            ]
        )

    def _create_factual(self) -> EvalDataset:
        """Create factual accuracy test dataset."""
        return EvalDataset(
            name="factual",
            description="Factual accuracy evaluation",
            samples=[]  # Load from external source
        )
```

#### Synthetic Data Generator
```python
# src/datasets/generator.py
import httpx
import json
from dataclasses import dataclass
from typing import Optional

@dataclass
class GenerationConfig:
    num_samples: int = 50
    topic: str = "general knowledge"
    difficulty: str = "medium"  # easy, medium, hard
    include_multi_hop: bool = True

class SyntheticDataGenerator:
    def __init__(self, llm_url: str = "http://localhost:11434"):
        self.llm_url = llm_url

    async def generate_dataset(self, config: GenerationConfig) -> "EvalDataset":
        """Generate synthetic evaluation dataset."""
        from datasets.loader import EvalDataset, EvalSample

        prompt = f"""Generate {config.num_samples} question-answer pairs for RAG evaluation.

Topic: {config.topic}
Difficulty: {config.difficulty}
Include multi-hop reasoning: {config.include_multi_hop}

For each pair, provide:
1. A clear question
2. A complete, factual ground truth answer
3. Optional: Relevant context passages

Return as JSON array:
[
  {{
    "question": "...",
    "ground_truth": "...",
    "contexts": ["...", "..."]
  }}
]

Generate diverse questions covering different aspects of the topic."""

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.llm_url}/api/generate",
                json={
                    "model": "deepseek-r1:14b",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )

            result = response.json()

            try:
                data = json.loads(result.get("response", "[]"))
            except json.JSONDecodeError:
                data = []

        samples = [
            EvalSample(
                question=item["question"],
                ground_truth=item["ground_truth"],
                contexts=item.get("contexts")
            )
            for item in data
        ]

        return EvalDataset(
            name=f"synthetic_{config.topic.replace(' ', '_')}",
            description=f"Synthetic dataset for {config.topic}",
            samples=samples
        )

    async def generate_from_documents(
        self,
        documents: list[str],
        num_per_doc: int = 5
    ) -> "EvalDataset":
        """Generate evaluation dataset from documents."""
        from datasets.loader import EvalDataset, EvalSample

        all_samples = []

        for doc in documents:
            prompt = f"""Based on this document, generate {num_per_doc} question-answer pairs for RAG evaluation.

Document:
{doc[:3000]}

Generate questions that:
1. Can be answered from the document
2. Vary in complexity (simple recall to inference)
3. Test different aspects of comprehension

Return as JSON array:
[
  {{
    "question": "...",
    "ground_truth": "...",
    "relevant_passage": "..."
  }}
]"""

            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.llm_url}/api/generate",
                    json={
                        "model": "deepseek-r1:14b",
                        "prompt": prompt,
                        "stream": False,
                        "format": "json"
                    }
                )

                result = response.json()

                try:
                    data = json.loads(result.get("response", "[]"))
                    for item in data:
                        all_samples.append(EvalSample(
                            question=item["question"],
                            ground_truth=item["ground_truth"],
                            contexts=[item.get("relevant_passage", doc[:500])]
                        ))
                except json.JSONDecodeError:
                    continue

        return EvalDataset(
            name="document_based",
            description="Generated from provided documents",
            samples=all_samples
        )
```

### Phase 2: RAGAS Integration (Week 1)

#### RAGAS Evaluator
```python
# src/evaluators/ragas_eval.py
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_correctness
)
from datasets import Dataset
from dataclasses import dataclass
from typing import Optional

@dataclass
class RAGASResult:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    answer_correctness: float
    detailed_scores: list[dict]

class RAGASEvaluator:
    def __init__(self, llm_model: str = "gpt-4"):
        self.metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
            answer_correctness
        ]

    def evaluate(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: list[str]
    ) -> RAGASResult:
        """Run RAGAS evaluation on RAG outputs."""

        # Prepare dataset
        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths
        }
        dataset = Dataset.from_dict(data)

        # Run evaluation
        results = evaluate(dataset, metrics=self.metrics)

        # Extract detailed per-sample scores
        detailed = []
        for i in range(len(questions)):
            detailed.append({
                "question": questions[i],
                "faithfulness": results.scores[i].get("faithfulness", 0),
                "answer_relevancy": results.scores[i].get("answer_relevancy", 0),
                "context_precision": results.scores[i].get("context_precision", 0),
                "context_recall": results.scores[i].get("context_recall", 0),
                "answer_correctness": results.scores[i].get("answer_correctness", 0)
            })

        return RAGASResult(
            faithfulness=results["faithfulness"],
            answer_relevancy=results["answer_relevancy"],
            context_precision=results["context_precision"],
            context_recall=results["context_recall"],
            answer_correctness=results["answer_correctness"],
            detailed_scores=detailed
        )

    def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str
    ) -> dict:
        """Evaluate a single RAG response."""
        result = self.evaluate(
            questions=[question],
            answers=[answer],
            contexts=[contexts],
            ground_truths=[ground_truth]
        )

        return result.detailed_scores[0]
```

### Phase 3: DeepEval Integration (Week 2)

#### DeepEval Test Cases
```python
# src/evaluators/deepeval_eval.py
from deepeval import evaluate
from deepeval.metrics import (
    HallucinationMetric,
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualRelevancyMetric,
    ToxicityMetric,
    BiasMetric
)
from deepeval.test_case import LLMTestCase
from dataclasses import dataclass
from typing import Optional

@dataclass
class DeepEvalResult:
    hallucination_score: float
    answer_relevancy: float
    faithfulness: float
    contextual_relevancy: float
    toxicity: float
    bias: float
    passed: bool
    details: dict

class DeepEvalEvaluator:
    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        self.metrics = [
            HallucinationMetric(threshold=threshold),
            AnswerRelevancyMetric(threshold=threshold),
            FaithfulnessMetric(threshold=threshold),
            ContextualRelevancyMetric(threshold=threshold),
            ToxicityMetric(threshold=0.5),  # Lower threshold for toxicity
            BiasMetric(threshold=0.5)
        ]

    def create_test_case(
        self,
        question: str,
        answer: str,
        context: list[str],
        expected_output: Optional[str] = None
    ) -> LLMTestCase:
        """Create a DeepEval test case."""
        return LLMTestCase(
            input=question,
            actual_output=answer,
            expected_output=expected_output,
            retrieval_context=context
        )

    def evaluate_test_case(self, test_case: LLMTestCase) -> DeepEvalResult:
        """Evaluate a single test case."""
        results = {}

        for metric in self.metrics:
            metric.measure(test_case)
            results[metric.__class__.__name__] = {
                "score": metric.score,
                "reason": metric.reason,
                "passed": metric.is_successful()
            }

        all_passed = all(r["passed"] for r in results.values())

        return DeepEvalResult(
            hallucination_score=results.get("HallucinationMetric", {}).get("score", 0),
            answer_relevancy=results.get("AnswerRelevancyMetric", {}).get("score", 0),
            faithfulness=results.get("FaithfulnessMetric", {}).get("score", 0),
            contextual_relevancy=results.get("ContextualRelevancyMetric", {}).get("score", 0),
            toxicity=results.get("ToxicityMetric", {}).get("score", 0),
            bias=results.get("BiasMetric", {}).get("score", 0),
            passed=all_passed,
            details=results
        )

    def evaluate_batch(
        self,
        test_cases: list[LLMTestCase]
    ) -> list[DeepEvalResult]:
        """Evaluate multiple test cases."""
        return [self.evaluate_test_case(tc) for tc in test_cases]

    def run_test_suite(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        expected_outputs: Optional[list[str]] = None
    ) -> dict:
        """Run a full test suite."""
        test_cases = []
        for i in range(len(questions)):
            tc = self.create_test_case(
                question=questions[i],
                answer=answers[i],
                context=contexts[i],
                expected_output=expected_outputs[i] if expected_outputs else None
            )
            test_cases.append(tc)

        results = self.evaluate_batch(test_cases)

        # Aggregate results
        passed_count = sum(1 for r in results if r.passed)

        return {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "pass_rate": passed_count / len(results) if results else 0,
            "avg_faithfulness": sum(r.faithfulness for r in results) / len(results) if results else 0,
            "avg_relevancy": sum(r.answer_relevancy for r in results) / len(results) if results else 0,
            "results": results
        }
```

### Phase 4: RAG Pipeline Runner (Week 2)

#### RAG Runner
```python
# src/runners/rag_runner.py
import httpx
import time
from dataclasses import dataclass
from typing import Optional, Callable
import asyncio

@dataclass
class RAGResponse:
    question: str
    answer: str
    contexts: list[str]
    latency_ms: float
    tokens_used: Optional[int] = None

class RAGRunner:
    def __init__(self, knowledge_engine_url: str = "http://localhost:8000"):
        self.base_url = knowledge_engine_url

    async def query(self, question: str) -> RAGResponse:
        """Query the RAG system and get response with contexts."""
        start_time = time.time()

        async with httpx.AsyncClient(timeout=60) as client:
            # Search for relevant contexts
            search_response = await client.get(
                f"{self.base_url}/api/search",
                params={"q": question, "top_k": 5}
            )
            search_results = search_response.json()
            contexts = [r["content"] for r in search_results.get("results", [])]

            # Get answer from QA endpoint
            qa_response = await client.post(
                f"{self.base_url}/api/qa",
                json={"question": question, "contexts": contexts}
            )
            qa_result = qa_response.json()

        latency = (time.time() - start_time) * 1000

        return RAGResponse(
            question=question,
            answer=qa_result.get("answer", ""),
            contexts=contexts,
            latency_ms=latency,
            tokens_used=qa_result.get("tokens_used")
        )

    async def batch_query(
        self,
        questions: list[str],
        concurrency: int = 5,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> list[RAGResponse]:
        """Query multiple questions with controlled concurrency."""
        semaphore = asyncio.Semaphore(concurrency)
        results = []

        async def query_with_semaphore(q: str, idx: int) -> RAGResponse:
            async with semaphore:
                result = await self.query(q)
                if progress_callback:
                    progress_callback(idx + 1, len(questions))
                return result

        tasks = [query_with_semaphore(q, i) for i, q in enumerate(questions)]
        results = await asyncio.gather(*tasks)

        return list(results)
```

#### Batch Evaluation Runner
```python
# src/runners/batch.py
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import json
from pathlib import Path

from datasets.loader import EvalDataset
from runners.rag_runner import RAGRunner, RAGResponse
from evaluators.ragas_eval import RAGASEvaluator, RAGASResult
from evaluators.deepeval_eval import DeepEvalEvaluator

@dataclass
class EvaluationRun:
    run_id: str
    timestamp: datetime
    dataset_name: str
    total_samples: int
    avg_latency_ms: float
    ragas_results: Optional[RAGASResult]
    deepeval_results: Optional[dict]
    raw_responses: list[RAGResponse]

class BatchEvaluator:
    def __init__(
        self,
        rag_runner: RAGRunner,
        ragas_evaluator: RAGASEvaluator,
        deepeval_evaluator: DeepEvalEvaluator,
        output_dir: Path = Path("evaluation_results")
    ):
        self.rag_runner = rag_runner
        self.ragas = ragas_evaluator
        self.deepeval = deepeval_evaluator
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)

    async def run_evaluation(
        self,
        dataset: EvalDataset,
        run_ragas: bool = True,
        run_deepeval: bool = True
    ) -> EvaluationRun:
        """Run full evaluation on a dataset."""
        run_id = f"{dataset.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Get questions and ground truths
        questions = [s.question for s in dataset.samples]
        ground_truths = [s.ground_truth for s in dataset.samples]

        # Run RAG queries
        print(f"Running {len(questions)} queries...")
        responses = await self.rag_runner.batch_query(
            questions,
            progress_callback=lambda i, t: print(f"  Progress: {i}/{t}")
        )

        # Extract answers and contexts
        answers = [r.answer for r in responses]
        contexts = [r.contexts for r in responses]
        avg_latency = sum(r.latency_ms for r in responses) / len(responses)

        # Run RAGAS evaluation
        ragas_results = None
        if run_ragas:
            print("Running RAGAS evaluation...")
            ragas_results = self.ragas.evaluate(
                questions=questions,
                answers=answers,
                contexts=contexts,
                ground_truths=ground_truths
            )

        # Run DeepEval evaluation
        deepeval_results = None
        if run_deepeval:
            print("Running DeepEval evaluation...")
            deepeval_results = self.deepeval.run_test_suite(
                questions=questions,
                answers=answers,
                contexts=contexts,
                expected_outputs=ground_truths
            )

        # Create evaluation run
        evaluation = EvaluationRun(
            run_id=run_id,
            timestamp=datetime.now(),
            dataset_name=dataset.name,
            total_samples=len(dataset.samples),
            avg_latency_ms=avg_latency,
            ragas_results=ragas_results,
            deepeval_results=deepeval_results,
            raw_responses=responses
        )

        # Save results
        self._save_results(evaluation)

        return evaluation

    def _save_results(self, evaluation: EvaluationRun):
        """Save evaluation results to disk."""
        output_file = self.output_dir / f"{evaluation.run_id}.json"

        data = {
            "run_id": evaluation.run_id,
            "timestamp": evaluation.timestamp.isoformat(),
            "dataset_name": evaluation.dataset_name,
            "total_samples": evaluation.total_samples,
            "avg_latency_ms": evaluation.avg_latency_ms,
            "ragas": {
                "faithfulness": evaluation.ragas_results.faithfulness if evaluation.ragas_results else None,
                "answer_relevancy": evaluation.ragas_results.answer_relevancy if evaluation.ragas_results else None,
                "context_precision": evaluation.ragas_results.context_precision if evaluation.ragas_results else None,
                "context_recall": evaluation.ragas_results.context_recall if evaluation.ragas_results else None,
                "answer_correctness": evaluation.ragas_results.answer_correctness if evaluation.ragas_results else None,
            } if evaluation.ragas_results else None,
            "deepeval": {
                "pass_rate": evaluation.deepeval_results.get("pass_rate") if evaluation.deepeval_results else None,
                "avg_faithfulness": evaluation.deepeval_results.get("avg_faithfulness") if evaluation.deepeval_results else None,
                "avg_relevancy": evaluation.deepeval_results.get("avg_relevancy") if evaluation.deepeval_results else None,
            } if evaluation.deepeval_results else None,
            "responses": [
                {
                    "question": r.question,
                    "answer": r.answer,
                    "latency_ms": r.latency_ms
                }
                for r in evaluation.raw_responses
            ]
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"Results saved to: {output_file}")
```

### Phase 5: Report Generation (Week 3)

#### HTML Report Generator
```python
# src/reports/html.py
from pathlib import Path
from datetime import datetime
from jinja2 import Template

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>RAG Evaluation Report - {{ run_id }}</title>
    <style>
        body { font-family: -apple-system, sans-serif; margin: 40px; }
        .header { border-bottom: 2px solid #333; padding-bottom: 20px; }
        .metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }
        .metric-card { background: #f5f5f5; padding: 20px; border-radius: 8px; }
        .metric-value { font-size: 32px; font-weight: bold; color: #2563eb; }
        .metric-label { color: #666; margin-top: 5px; }
        .score-good { color: #16a34a; }
        .score-medium { color: #ca8a04; }
        .score-bad { color: #dc2626; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f5f5f5; }
        .chart { height: 300px; margin: 20px 0; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <h1>RAG Evaluation Report</h1>
        <p>Run ID: {{ run_id }}</p>
        <p>Dataset: {{ dataset_name }} ({{ total_samples }} samples)</p>
        <p>Timestamp: {{ timestamp }}</p>
    </div>

    <h2>Summary Metrics</h2>
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-value {{ 'score-good' if avg_latency < 1000 else 'score-medium' if avg_latency < 3000 else 'score-bad' }}">
                {{ "%.0f"|format(avg_latency) }}ms
            </div>
            <div class="metric-label">Avg Latency</div>
        </div>
        {% if ragas %}
        <div class="metric-card">
            <div class="metric-value {{ 'score-good' if ragas.faithfulness > 0.8 else 'score-medium' if ragas.faithfulness > 0.6 else 'score-bad' }}">
                {{ "%.1f"|format(ragas.faithfulness * 100) }}%
            </div>
            <div class="metric-label">Faithfulness</div>
        </div>
        <div class="metric-card">
            <div class="metric-value {{ 'score-good' if ragas.answer_relevancy > 0.8 else 'score-medium' if ragas.answer_relevancy > 0.6 else 'score-bad' }}">
                {{ "%.1f"|format(ragas.answer_relevancy * 100) }}%
            </div>
            <div class="metric-label">Answer Relevancy</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{{ "%.1f"|format(ragas.context_precision * 100) }}%</div>
            <div class="metric-label">Context Precision</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{{ "%.1f"|format(ragas.context_recall * 100) }}%</div>
            <div class="metric-label">Context Recall</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{{ "%.1f"|format(ragas.answer_correctness * 100) }}%</div>
            <div class="metric-label">Answer Correctness</div>
        </div>
        {% endif %}
    </div>

    {% if deepeval %}
    <h2>DeepEval Results</h2>
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-value {{ 'score-good' if deepeval.pass_rate > 0.8 else 'score-bad' }}">
                {{ "%.1f"|format(deepeval.pass_rate * 100) }}%
            </div>
            <div class="metric-label">Pass Rate</div>
        </div>
    </div>
    {% endif %}

    <h2>Sample Results</h2>
    <table>
        <tr>
            <th>Question</th>
            <th>Answer (truncated)</th>
            <th>Latency</th>
        </tr>
        {% for r in responses[:20] %}
        <tr>
            <td>{{ r.question[:100] }}...</td>
            <td>{{ r.answer[:100] }}...</td>
            <td>{{ "%.0f"|format(r.latency_ms) }}ms</td>
        </tr>
        {% endfor %}
    </table>

    <canvas id="metricsChart" class="chart"></canvas>
    <script>
        {% if ragas %}
        new Chart(document.getElementById('metricsChart'), {
            type: 'radar',
            data: {
                labels: ['Faithfulness', 'Answer Relevancy', 'Context Precision', 'Context Recall', 'Answer Correctness'],
                datasets: [{
                    label: 'RAGAS Scores',
                    data: [
                        {{ ragas.faithfulness }},
                        {{ ragas.answer_relevancy }},
                        {{ ragas.context_precision }},
                        {{ ragas.context_recall }},
                        {{ ragas.answer_correctness }}
                    ],
                    backgroundColor: 'rgba(37, 99, 235, 0.2)',
                    borderColor: 'rgb(37, 99, 235)',
                    pointBackgroundColor: 'rgb(37, 99, 235)'
                }]
            },
            options: {
                scales: {
                    r: { min: 0, max: 1 }
                }
            }
        });
        {% endif %}
    </script>
</body>
</html>
"""

class HTMLReportGenerator:
    def __init__(self, output_dir: Path = Path("reports")):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.template = Template(HTML_TEMPLATE)

    def generate(self, evaluation: "EvaluationRun") -> Path:
        """Generate HTML report from evaluation results."""
        html = self.template.render(
            run_id=evaluation.run_id,
            dataset_name=evaluation.dataset_name,
            total_samples=evaluation.total_samples,
            timestamp=evaluation.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            avg_latency=evaluation.avg_latency_ms,
            ragas=evaluation.ragas_results,
            deepeval=evaluation.deepeval_results,
            responses=evaluation.raw_responses
        )

        output_file = self.output_dir / f"{evaluation.run_id}.html"
        output_file.write_text(html)

        return output_file
```

### Phase 6: CLI Interface (Week 3)

#### Main CLI
```python
# src/main.py
import asyncio
import click
from pathlib import Path

from datasets.loader import DatasetLoader
from datasets.generator import SyntheticDataGenerator, GenerationConfig
from runners.rag_runner import RAGRunner
from runners.batch import BatchEvaluator
from evaluators.ragas_eval import RAGASEvaluator
from evaluators.deepeval_eval import DeepEvalEvaluator
from reports.html import HTMLReportGenerator

@click.group()
def cli():
    """RAG Evaluation Suite - Comprehensive RAG pipeline testing."""
    pass

@cli.command()
@click.option("--dataset", "-d", required=True, help="Dataset file or preset name")
@click.option("--output", "-o", default="results", help="Output directory")
@click.option("--ragas/--no-ragas", default=True, help="Run RAGAS evaluation")
@click.option("--deepeval/--no-deepeval", default=True, help="Run DeepEval evaluation")
@click.option("--rag-url", default="http://localhost:8000", help="Knowledge Engine URL")
def evaluate(dataset, output, ragas, deepeval, rag_url):
    """Run evaluation on a dataset."""
    async def run():
        loader = DatasetLoader()

        # Load dataset
        if Path(dataset).exists():
            ds = loader.load_json(Path(dataset))
        else:
            ds = loader.load_preset(dataset)

        click.echo(f"Loaded dataset: {ds.name} ({len(ds.samples)} samples)")

        # Initialize evaluators
        rag_runner = RAGRunner(rag_url)
        batch_evaluator = BatchEvaluator(
            rag_runner=rag_runner,
            ragas_evaluator=RAGASEvaluator() if ragas else None,
            deepeval_evaluator=DeepEvalEvaluator() if deepeval else None,
            output_dir=Path(output)
        )

        # Run evaluation
        result = await batch_evaluator.run_evaluation(
            ds,
            run_ragas=ragas,
            run_deepeval=deepeval
        )

        # Generate report
        report_gen = HTMLReportGenerator(Path(output))
        report_path = report_gen.generate(result)

        click.echo(f"\nEvaluation complete!")
        click.echo(f"Results: {output}/{result.run_id}.json")
        click.echo(f"Report: {report_path}")

        # Print summary
        if result.ragas_results:
            click.echo(f"\nRAGAS Scores:")
            click.echo(f"  Faithfulness: {result.ragas_results.faithfulness:.2%}")
            click.echo(f"  Answer Relevancy: {result.ragas_results.answer_relevancy:.2%}")
            click.echo(f"  Context Precision: {result.ragas_results.context_precision:.2%}")

    asyncio.run(run())

@cli.command()
@click.option("--topic", "-t", required=True, help="Topic for generated questions")
@click.option("--samples", "-n", default=50, help="Number of samples to generate")
@click.option("--output", "-o", required=True, help="Output file path")
def generate(topic, samples, output):
    """Generate synthetic evaluation dataset."""
    async def run():
        generator = SyntheticDataGenerator()
        config = GenerationConfig(
            num_samples=samples,
            topic=topic
        )

        click.echo(f"Generating {samples} samples for topic: {topic}")
        dataset = await generator.generate_dataset(config)

        # Save to file
        import json
        output_path = Path(output)
        with open(output_path, "w") as f:
            json.dump({
                "name": dataset.name,
                "description": dataset.description,
                "samples": [
                    {
                        "question": s.question,
                        "ground_truth": s.ground_truth,
                        "contexts": s.contexts
                    }
                    for s in dataset.samples
                ]
            }, f, indent=2)

        click.echo(f"Generated {len(dataset.samples)} samples")
        click.echo(f"Saved to: {output_path}")

    asyncio.run(run())

@cli.command()
@click.argument("results_dir")
def compare(results_dir):
    """Compare multiple evaluation runs."""
    import json

    results_path = Path(results_dir)
    runs = []

    for f in results_path.glob("*.json"):
        with open(f) as file:
            runs.append(json.load(file))

    if not runs:
        click.echo("No results found")
        return

    # Sort by timestamp
    runs.sort(key=lambda x: x["timestamp"])

    click.echo("\nEvaluation Run Comparison")
    click.echo("=" * 80)
    click.echo(f"{'Run ID':<30} {'Faithfulness':<15} {'Relevancy':<15} {'Latency':<15}")
    click.echo("-" * 80)

    for run in runs:
        ragas = run.get("ragas", {})
        click.echo(
            f"{run['run_id']:<30} "
            f"{ragas.get('faithfulness', 0):.2%:<15} "
            f"{ragas.get('answer_relevancy', 0):.2%:<15} "
            f"{run['avg_latency_ms']:.0f}ms"
        )

if __name__ == "__main__":
    cli()
```

---

## Usage

### Run Evaluation
```bash
# Evaluate with built-in dataset
python -m rag_evaluation evaluate -d basic_qa

# Evaluate with custom dataset
python -m rag_evaluation evaluate -d my_dataset.json

# Evaluate without DeepEval (RAGAS only)
python -m rag_evaluation evaluate -d basic_qa --no-deepeval
```

### Generate Test Data
```bash
# Generate synthetic dataset
python -m rag_evaluation generate -t "machine learning" -n 100 -o ml_dataset.json
```

### Compare Runs
```bash
# Compare evaluation runs
python -m rag_evaluation compare results/
```

---

## Timeline

| Week | Task |
|------|------|
| Week 1 | Dataset management + RAGAS integration |
| Week 2 | DeepEval integration + RAG runner |
| Week 3 | Report generation + CLI + Dashboard |

**Total: 3 weeks**
