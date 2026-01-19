#!/usr/bin/env python3
"""
KAS RAG Evaluation Framework

Evaluates search quality using test queries with expected characteristics.
Generates metrics and reports for tracking search performance over time.

Usage:
    python evaluate.py                    # Run evaluation
    python evaluate.py --verbose          # Detailed output
    python evaluate.py --query rag-001    # Single query
    python evaluate.py --report           # Generate HTML report
    python evaluate.py --with-ragas       # Include RAGAS metrics

Metrics:
    - MRR (Mean Reciprocal Rank): Average of 1/rank_of_first_relevant
    - NDCG@K: Normalized Discounted Cumulative Gain at K
    - Precision@K, Recall@K: Classic IR metrics
    - Context Precision/Recall: RAGAS-style metrics
    - Composite Score: Weighted average of all metrics
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

# Import local metrics modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from evaluation.metrics.ir_metrics import (
    RetrievalResult,
    reciprocal_rank,
    ndcg,
    precision_at_k,
    recall_at_k,
    create_retrieval_results,
    relevance_from_keywords,
)
from evaluation.metrics.ragas_metrics import (
    context_precision,
    context_recall,
    evaluate_retrieval_only,
)

# Configuration
KAS_URL = "http://localhost:8000"
EVALUATION_DIR = Path(__file__).parent
METRICS_DIR = EVALUATION_DIR / "metrics"
REPORTS_DIR = EVALUATION_DIR / "reports"


def load_test_queries() -> dict[str, Any]:
    """Load test queries from YAML file."""
    queries_file = EVALUATION_DIR / "test_queries.yaml"
    with open(queries_file) as f:
        return yaml.safe_load(f)


def search_kas(query: str, limit: int = 5, namespace: str | None = None) -> dict[str, Any]:
    """Execute search against KAS API."""
    try:
        payload = {"query": query, "limit": limit}
        if namespace:
            payload["namespace"] = namespace
        response = httpx.post(
            f"{KAS_URL}/search",
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "results": []}


def evaluate_query(
    test_query: dict[str, Any],
    verbose: bool = False,
    with_ragas: bool = False,
) -> dict[str, Any]:
    """Evaluate a single test query with comprehensive IR and RAGAS metrics."""
    query_id = test_query["id"]
    query_text = test_query["query"]
    expected_keywords = test_query.get("expected_keywords", [])
    expected_namespaces = test_query.get("expected_namespaces", [])

    # Execute search
    results = search_kas(query_text)

    if "error" in results:
        return {
            "id": query_id,
            "query": query_text,
            "status": "error",
            "error": results["error"],
            "scores": {},
        }

    search_results = results.get("results", [])
    total_results = results.get("total", 0)

    # Calculate metrics
    scores = {}

    # 1. Basic metrics
    scores["has_results"] = 1.0 if total_results > 0 else 0.0

    # 2. IR Metrics (MRR, NDCG, Precision, Recall)
    if search_results:
        # Create RetrievalResult objects with relevance judgments based on keywords
        relevance_fn = relevance_from_keywords(expected_keywords) if expected_keywords else None
        retrieval_results = create_retrieval_results(search_results, relevance_fn)

        # Reciprocal Rank (for MRR calculation)
        scores["reciprocal_rank"] = reciprocal_rank(retrieval_results)

        # NDCG@5
        scores["ndcg@5"] = ndcg(retrieval_results, k=5)

        # Precision@3 and Precision@5
        scores["precision@3"] = precision_at_k(retrieval_results, k=3)
        scores["precision@5"] = precision_at_k(retrieval_results, k=5)

        # Recall@5
        total_relevant = sum(1 for r in retrieval_results if r.is_relevant)
        scores["recall@5"] = recall_at_k(retrieval_results, k=5, total_relevant=max(total_relevant, 1))
    else:
        scores["reciprocal_rank"] = 0.0
        scores["ndcg@5"] = 0.0
        scores["precision@3"] = 0.0
        scores["precision@5"] = 0.0
        scores["recall@5"] = 0.0

    # 3. Keyword coverage in retrieved content
    if expected_keywords and search_results:
        all_content = " ".join(
            (r.get("chunk_text") or r.get("content") or "").lower()
            for r in search_results
        )
        found_keywords = sum(1 for kw in expected_keywords if kw.lower() in all_content)
        scores["keyword_coverage"] = found_keywords / len(expected_keywords)
    else:
        scores["keyword_coverage"] = 0.0

    # 4. Namespace match
    if expected_namespaces and search_results:
        result_namespaces = {r.get("namespace") or "default" for r in search_results}
        matched = sum(
            1 for ns in expected_namespaces
            if any(ns in rns for rns in result_namespaces if rns)
        )
        scores["namespace_match"] = matched / len(expected_namespaces)
    else:
        scores["namespace_match"] = 0.0 if expected_namespaces else 1.0

    # 5. Vector similarity average
    if search_results:
        vec_sims = [r.get("vector_similarity") for r in search_results if r.get("vector_similarity")]
        scores["avg_vector_similarity"] = sum(vec_sims) / len(vec_sims) if vec_sims else 0.0
    else:
        scores["avg_vector_similarity"] = 0.0

    # 6. RAGAS-style metrics (optional)
    if with_ragas and search_results:
        contexts = [r.get("chunk_text") or "" for r in search_results if r.get("chunk_text")]
        retrieval_scores = [r.get("score", 0) for r in search_results]

        ragas_result = evaluate_retrieval_only(
            query=query_text,
            contexts=contexts,
            expected_keywords=expected_keywords,
            scores=retrieval_scores,
        )
        scores["context_precision"] = ragas_result["context_precision"]
        scores["context_recall"] = ragas_result["context_recall"]

    # Composite score (updated weights including new metrics)
    if with_ragas:
        weights = {
            "has_results": 0.05,
            "reciprocal_rank": 0.15,
            "ndcg@5": 0.15,
            "precision@5": 0.10,
            "keyword_coverage": 0.15,
            "namespace_match": 0.10,
            "context_precision": 0.15,
            "context_recall": 0.15,
        }
    else:
        weights = {
            "has_results": 0.05,
            "reciprocal_rank": 0.20,
            "ndcg@5": 0.20,
            "precision@5": 0.15,
            "keyword_coverage": 0.20,
            "namespace_match": 0.20,
        }

    scores["composite"] = sum(scores.get(k, 0) * w for k, w in weights.items())

    result = {
        "id": query_id,
        "query": query_text,
        "category": test_query.get("category", "unknown"),
        "difficulty": test_query.get("difficulty", "unknown"),
        "status": "success",
        "total_results": total_results,
        "scores": scores,
    }

    if verbose:
        result["results_preview"] = [
            {
                "title": r.get("title", ""),
                "score": r.get("score", 0),
                "namespace": r.get("namespace", ""),
            }
            for r in search_results[:3]
        ]

    return result


def run_evaluation(
    queries: list[dict[str, Any]],
    verbose: bool = False,
    with_ragas: bool = False,
) -> dict[str, Any]:
    """Run evaluation on all queries with comprehensive metrics."""
    results = []
    total_composite = 0.0
    category_scores: dict[str, list[float]] = {}

    # Collect aggregate metrics
    all_rr: list[float] = []  # For MRR calculation
    all_ndcg: list[float] = []
    all_precision: list[float] = []

    for test_query in queries:
        result = evaluate_query(test_query, verbose, with_ragas)
        results.append(result)

        if result["status"] == "success":
            score = result["scores"]["composite"]
            total_composite += score

            # Collect metrics for aggregation
            all_rr.append(result["scores"].get("reciprocal_rank", 0))
            all_ndcg.append(result["scores"].get("ndcg@5", 0))
            all_precision.append(result["scores"].get("precision@5", 0))

            category = result.get("category", "unknown")
            if category not in category_scores:
                category_scores[category] = []
            category_scores[category].append(score)

        if verbose:
            status = "PASS" if result["scores"].get("composite", 0) > 0.5 else "FAIL"
            print(f"  [{status}] {result['id']}: {result['query'][:50]}...")
            print(f"       Composite: {result['scores'].get('composite', 0):.2%}")
            print(f"       RR: {result['scores'].get('reciprocal_rank', 0):.2f}, "
                  f"NDCG@5: {result['scores'].get('ndcg@5', 0):.2f}, "
                  f"P@5: {result['scores'].get('precision@5', 0):.2f}")

    # Calculate summary statistics
    success_count = sum(1 for r in results if r["status"] == "success")
    avg_composite = total_composite / success_count if success_count > 0 else 0.0

    category_averages = {
        cat: sum(scores) / len(scores) for cat, scores in category_scores.items()
    }

    # Calculate aggregate IR metrics
    mrr = sum(all_rr) / len(all_rr) if all_rr else 0.0
    avg_ndcg = sum(all_ndcg) / len(all_ndcg) if all_ndcg else 0.0
    avg_precision = sum(all_precision) / len(all_precision) if all_precision else 0.0

    return {
        "timestamp": datetime.now().isoformat(),
        "total_queries": len(queries),
        "successful_queries": success_count,
        "avg_composite_score": avg_composite,
        "ir_metrics": {
            "mrr": mrr,
            "avg_ndcg@5": avg_ndcg,
            "avg_precision@5": avg_precision,
        },
        "category_scores": category_averages,
        "results": results,
        "with_ragas": with_ragas,
    }


def save_metrics(evaluation: dict[str, Any]) -> Path:
    """Save evaluation metrics to file."""
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    metrics_file = METRICS_DIR / f"eval_{timestamp}.json"

    with open(metrics_file, "w") as f:
        json.dump(evaluation, f, indent=2)

    return metrics_file


def generate_report(evaluation: dict[str, Any]) -> Path:
    """Generate HTML report."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = REPORTS_DIR / f"report_{timestamp}.html"

    avg_score = evaluation["avg_composite_score"]
    status_color = "green" if avg_score > 0.7 else "orange" if avg_score > 0.5 else "red"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>KAS RAG Evaluation Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 40px; }}
        .header {{ margin-bottom: 30px; }}
        .score {{ font-size: 48px; color: {status_color}; }}
        .category {{ margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 8px; }}
        .result {{ padding: 10px; margin: 5px 0; border-left: 3px solid #ccc; }}
        .pass {{ border-left-color: green; }}
        .fail {{ border-left-color: red; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>KAS RAG Evaluation Report</h1>
        <p>Generated: {evaluation['timestamp']}</p>
        <p class="score">{avg_score:.1%}</p>
        <p>Average Composite Score</p>
    </div>

    <h2>Summary</h2>
    <table>
        <tr><td>Total Queries</td><td>{evaluation['total_queries']}</td></tr>
        <tr><td>Successful</td><td>{evaluation['successful_queries']}</td></tr>
        <tr><td>Average Score</td><td>{avg_score:.2%}</td></tr>
    </table>

    <h2>Category Scores</h2>
    <table>
        <tr><th>Category</th><th>Score</th></tr>
"""
    for cat, score in sorted(evaluation["category_scores"].items()):
        html += f"        <tr><td>{cat}</td><td>{score:.2%}</td></tr>\n"

    html += """    </table>

    <h2>Individual Results</h2>
"""
    for result in evaluation["results"]:
        status = "pass" if result["scores"].get("composite", 0) > 0.5 else "fail"
        html += f"""    <div class="result {status}">
        <strong>{result['id']}</strong>: {result['query']}<br>
        Score: {result['scores'].get('composite', 0):.2%} | Category: {result.get('category', 'unknown')}
    </div>
"""

    html += """</body>
</html>"""

    with open(report_file, "w") as f:
        f.write(html)

    return report_file


def main():
    parser = argparse.ArgumentParser(description="KAS RAG Evaluation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--query", "-q", help="Evaluate single query by ID")
    parser.add_argument("--report", "-r", action="store_true", help="Generate HTML report")
    parser.add_argument("--no-save", action="store_true", help="Don't save metrics")
    parser.add_argument("--with-ragas", action="store_true", help="Include RAGAS metrics")
    args = parser.parse_args()

    # Check KAS availability
    try:
        response = httpx.get(f"{KAS_URL}/health", timeout=5.0)
        response.raise_for_status()
        health = response.json()
        # Extract document count from database component
        db_component = next((c for c in health.get("components", []) if c["name"] == "database"), {})
        doc_count = db_component.get("details", {}).get("content_count", "?")
        print(f"KAS Status: {health['status']} ({doc_count} docs)")
    except Exception as e:
        print(f"ERROR: KAS not available at {KAS_URL}")
        print(f"  {e}")
        sys.exit(1)

    # Load test queries
    data = load_test_queries()
    queries = data["queries"]

    if args.query:
        queries = [q for q in queries if q["id"] == args.query]
        if not queries:
            print(f"Query '{args.query}' not found")
            sys.exit(1)

    print(f"\nRunning evaluation on {len(queries)} queries...")
    if args.with_ragas:
        print("(Including RAGAS metrics)")
    print()

    # Run evaluation
    evaluation = run_evaluation(queries, args.verbose, args.with_ragas)

    # Display results
    print(f"\n{'=' * 60}")
    print(f"EVALUATION RESULTS")
    print(f"{'=' * 60}")
    print(f"Total Queries: {evaluation['total_queries']}")
    print(f"Successful: {evaluation['successful_queries']}")
    print(f"Average Composite Score: {evaluation['avg_composite_score']:.2%}")

    # Display IR metrics
    ir = evaluation.get("ir_metrics", {})
    print(f"\nIR Metrics:")
    print(f"  MRR (Mean Reciprocal Rank): {ir.get('mrr', 0):.3f}")
    print(f"  NDCG@5 (Normalized DCG):    {ir.get('avg_ndcg@5', 0):.3f}")
    print(f"  Precision@5:                {ir.get('avg_precision@5', 0):.3f}")

    print(f"\nCategory Scores:")
    for cat, score in sorted(evaluation["category_scores"].items()):
        status = "OK" if score > 0.5 else "NEEDS WORK"
        print(f"  {cat}: {score:.2%} [{status}]")

    # Save metrics
    if not args.no_save:
        metrics_file = save_metrics(evaluation)
        print(f"\nMetrics saved: {metrics_file}")

    # Generate report
    if args.report:
        report_file = generate_report(evaluation)
        print(f"Report generated: {report_file}")

    # Exit code based on score
    if evaluation["avg_composite_score"] < 0.5:
        sys.exit(1)


if __name__ == "__main__":
    main()
