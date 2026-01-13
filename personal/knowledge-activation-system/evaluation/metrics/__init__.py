"""
KAS Evaluation Metrics Module

Provides standard Information Retrieval and RAG evaluation metrics:
- MRR (Mean Reciprocal Rank)
- NDCG (Normalized Discounted Cumulative Gain)
- Precision@K, Recall@K
- RAGAS-style metrics (context relevancy, faithfulness)
"""

from evaluation.metrics.ir_metrics import (
    mrr,
    ndcg,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    dcg,
    ideal_dcg,
)
from evaluation.metrics.ragas_metrics import (
    context_precision,
    context_recall,
    answer_relevancy,
    faithfulness_score,
)

__all__ = [
    # IR metrics
    "mrr",
    "ndcg",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
    "dcg",
    "ideal_dcg",
    # RAGAS metrics
    "context_precision",
    "context_recall",
    "answer_relevancy",
    "faithfulness_score",
]
