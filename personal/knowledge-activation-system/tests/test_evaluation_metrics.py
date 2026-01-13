"""Tests for evaluation metrics (P30)."""

import pytest
import sys
from pathlib import Path

# Add evaluation to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.metrics.ir_metrics import (
    RetrievalResult,
    reciprocal_rank,
    mrr,
    precision_at_k,
    recall_at_k,
    dcg,
    ideal_dcg,
    ndcg,
    average_precision,
    mean_average_precision,
    create_retrieval_results,
    relevance_from_keywords,
)
from evaluation.metrics.ragas_metrics import (
    context_precision,
    context_recall,
    answer_relevancy,
    faithfulness_score,
    evaluate_rag,
    evaluate_retrieval_only,
    RAGEvalInput,
)


# =============================================================================
# IR Metrics Tests
# =============================================================================


class TestReciprocalRank:
    """Test Reciprocal Rank calculation."""

    def test_first_result_relevant(self):
        results = [
            RetrievalResult("doc1", 0.9, True, 2),
            RetrievalResult("doc2", 0.7, False, 0),
        ]
        assert reciprocal_rank(results) == 1.0

    def test_second_result_relevant(self):
        results = [
            RetrievalResult("doc1", 0.9, False, 0),
            RetrievalResult("doc2", 0.7, True, 1),
        ]
        assert reciprocal_rank(results) == 0.5

    def test_third_result_relevant(self):
        results = [
            RetrievalResult("doc1", 0.9, False, 0),
            RetrievalResult("doc2", 0.7, False, 0),
            RetrievalResult("doc3", 0.5, True, 1),
        ]
        assert reciprocal_rank(results) == pytest.approx(1 / 3)

    def test_no_relevant_results(self):
        results = [
            RetrievalResult("doc1", 0.9, False, 0),
            RetrievalResult("doc2", 0.7, False, 0),
        ]
        assert reciprocal_rank(results) == 0.0

    def test_empty_results(self):
        assert reciprocal_rank([]) == 0.0


class TestMRR:
    """Test Mean Reciprocal Rank calculation."""

    def test_mrr_multiple_queries(self):
        query_results = [
            [RetrievalResult("doc1", 0.9, True, 1)],  # RR = 1.0
            [RetrievalResult("doc1", 0.9, False, 0), RetrievalResult("doc2", 0.7, True, 1)],  # RR = 0.5
            [RetrievalResult("doc1", 0.9, False, 0), RetrievalResult("doc2", 0.7, False, 0), RetrievalResult("doc3", 0.5, True, 1)],  # RR = 0.333
        ]
        expected = (1.0 + 0.5 + 1/3) / 3
        assert mrr(query_results) == pytest.approx(expected)

    def test_mrr_empty(self):
        assert mrr([]) == 0.0


class TestPrecisionAtK:
    """Test Precision@K calculation."""

    def test_precision_all_relevant(self):
        results = [
            RetrievalResult("doc1", 0.9, True, 1),
            RetrievalResult("doc2", 0.8, True, 1),
            RetrievalResult("doc3", 0.7, True, 1),
        ]
        assert precision_at_k(results, k=3) == 1.0

    def test_precision_none_relevant(self):
        results = [
            RetrievalResult("doc1", 0.9, False, 0),
            RetrievalResult("doc2", 0.8, False, 0),
        ]
        assert precision_at_k(results, k=2) == 0.0

    def test_precision_partial(self):
        results = [
            RetrievalResult("doc1", 0.9, True, 1),
            RetrievalResult("doc2", 0.8, False, 0),
            RetrievalResult("doc3", 0.7, True, 1),
            RetrievalResult("doc4", 0.6, False, 0),
        ]
        assert precision_at_k(results, k=4) == 0.5

    def test_precision_k_larger_than_results(self):
        results = [
            RetrievalResult("doc1", 0.9, True, 1),
            RetrievalResult("doc2", 0.8, True, 1),
        ]
        # P@5 with only 2 results: 2/5 = 0.4
        assert precision_at_k(results, k=5) == 0.4


class TestRecallAtK:
    """Test Recall@K calculation."""

    def test_recall_all_found(self):
        results = [
            RetrievalResult("doc1", 0.9, True, 1),
            RetrievalResult("doc2", 0.8, True, 1),
            RetrievalResult("doc3", 0.7, True, 1),
        ]
        # All 3 relevant found in top 3
        assert recall_at_k(results, k=3, total_relevant=3) == 1.0

    def test_recall_partial(self):
        results = [
            RetrievalResult("doc1", 0.9, True, 1),
            RetrievalResult("doc2", 0.8, False, 0),
            RetrievalResult("doc3", 0.7, True, 1),
        ]
        # 2 out of 4 relevant docs found
        assert recall_at_k(results, k=3, total_relevant=4) == 0.5


class TestNDCG:
    """Test NDCG calculation."""

    def test_ndcg_perfect_ranking(self):
        # Results already in perfect order
        results = [
            RetrievalResult("doc1", 0.9, True, 2),  # Highly relevant
            RetrievalResult("doc2", 0.8, True, 1),  # Relevant
            RetrievalResult("doc3", 0.7, False, 0),  # Not relevant
        ]
        assert ndcg(results) == 1.0

    def test_ndcg_worst_ranking(self):
        # Relevant results at the bottom
        results = [
            RetrievalResult("doc1", 0.9, False, 0),
            RetrievalResult("doc2", 0.8, False, 0),
            RetrievalResult("doc3", 0.7, True, 2),
        ]
        # Should be less than perfect
        assert ndcg(results) < 1.0

    def test_ndcg_no_relevant(self):
        results = [
            RetrievalResult("doc1", 0.9, False, 0),
            RetrievalResult("doc2", 0.8, False, 0),
        ]
        assert ndcg(results) == 0.0


class TestCreateRetrievalResults:
    """Test helper function for creating RetrievalResult objects."""

    def test_from_search_results_default(self):
        search_results = [
            {"content_id": "1", "score": 0.8, "chunk_text": "test"},
            {"content_id": "2", "score": 0.2, "chunk_text": "other"},
        ]
        results = create_retrieval_results(search_results)

        assert len(results) == 2
        assert results[0].is_relevant is True  # score > 0.3
        assert results[1].is_relevant is False  # score < 0.3

    def test_from_search_results_with_keywords(self):
        search_results = [
            {"content_id": "1", "score": 0.8, "chunk_text": "python dependency injection"},
            {"content_id": "2", "score": 0.7, "chunk_text": "unrelated topic"},
        ]

        relevance_fn = relevance_from_keywords(["python", "dependency", "injection"])
        results = create_retrieval_results(search_results, relevance_fn)

        assert results[0].is_relevant is True
        assert results[0].relevance_grade == 2  # High overlap
        assert results[1].is_relevant is False


# =============================================================================
# RAGAS Metrics Tests
# =============================================================================


class TestContextPrecision:
    """Test Context Precision calculation."""

    def test_high_precision(self):
        query = "How to use FastAPI dependency injection?"
        contexts = [
            "FastAPI dependency injection is done using Depends()",
            "The dependency injection system in FastAPI is powerful",
        ]

        score = context_precision(query, contexts)
        assert score > 0.5

    def test_low_precision(self):
        query = "How to use FastAPI dependency injection?"
        contexts = [
            "JavaScript async await patterns",
            "React hooks tutorial",
        ]

        score = context_precision(query, contexts)
        assert score < 0.3

    def test_with_expected_keywords(self):
        query = "dependency injection"
        contexts = ["Using Depends() for DI patterns"]
        keywords = ["Depends", "injection", "pattern"]

        score = context_precision(query, contexts, keywords)
        assert score > 0.4

    def test_empty_contexts(self):
        assert context_precision("query", []) == 0.0


class TestContextRecall:
    """Test Context Recall calculation."""

    def test_high_recall(self):
        contexts = [
            "RAG uses retrieval augmented generation",
            "The context is retrieved and used for generation",
        ]
        keywords = ["retrieval", "augmented", "generation", "context"]

        score = context_recall(contexts, keywords)
        assert score > 0.7

    def test_low_recall(self):
        contexts = ["Unrelated topic about cooking"]
        keywords = ["retrieval", "augmented", "generation"]

        score = context_recall(contexts, keywords)
        assert score < 0.2

    def test_empty_keywords(self):
        contexts = ["Some context"]
        assert context_recall(contexts, []) == 1.0


class TestAnswerRelevancy:
    """Test Answer Relevancy calculation."""

    def test_relevant_answer(self):
        query = "How does FastAPI dependency injection work?"
        answer = "FastAPI uses Depends() for dependency injection. You can inject database connections and services."

        score = answer_relevancy(query, answer, ["Depends", "injection"])
        assert score > 0.5

    def test_hedging_answer(self):
        query = "How does X work?"
        answer = "I don't know how X works."

        score = answer_relevancy(query, answer)
        # Hedging reduces confidence score component
        assert score < 0.6

    def test_no_answer(self):
        assert answer_relevancy("query", None) == 0.0


class TestFaithfulness:
    """Test Faithfulness calculation."""

    def test_grounded_answer(self):
        answer = "FastAPI uses the Depends function for dependency injection."
        contexts = [
            "FastAPI's Depends() function enables dependency injection",
            "Dependencies are declared using Depends",
        ]

        score = faithfulness_score(answer, contexts)
        assert score > 0.6

    def test_ungrounded_answer(self):
        answer = "FastAPI uses Spring-style @Autowired annotations."
        contexts = [
            "FastAPI uses Depends() for injection",
        ]

        score = faithfulness_score(answer, contexts)
        assert score < 0.5

    def test_no_context(self):
        assert faithfulness_score("answer", []) == 0.0


class TestEvaluateRetrievalOnly:
    """Test combined retrieval evaluation."""

    def test_good_retrieval(self):
        result = evaluate_retrieval_only(
            query="FastAPI dependency injection",
            contexts=[
                "FastAPI dependency injection uses Depends()",
                "Inject database connections with Depends",
            ],
            expected_keywords=["FastAPI", "Depends", "injection"],
            scores=[0.9, 0.8],
        )

        assert result["context_precision"] > 0.5
        assert result["context_recall"] > 0.5
        assert result["average"] > 0.5


class TestRAGEvalInput:
    """Test full RAG evaluation."""

    def test_full_evaluation(self):
        input_data = RAGEvalInput(
            query="How does RAG work?",
            retrieved_contexts=[
                "RAG combines retrieval with generation",
                "Retrieval augmented generation improves LLM outputs",
            ],
            generated_answer="RAG works by first retrieving relevant documents, then using them to generate answers.",
            expected_keywords=["retrieval", "generation", "RAG"],
        )

        result = evaluate_rag(input_data)

        assert 0 <= result.context_precision <= 1
        assert 0 <= result.context_recall <= 1
        assert 0 <= result.answer_relevancy <= 1
        assert 0 <= result.faithfulness <= 1
        assert 0 <= result.aggregate_score <= 1
