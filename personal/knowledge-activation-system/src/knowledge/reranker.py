"""Local reranking using sentence-transformers.

Provides reranking capabilities using cross-encoder models like
mxbai-rerank-base-v1 or mxbai-rerank-large-v2 to improve search quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from knowledge.search import SearchResult


@dataclass
class RerankResult:
    """Reranked search result with new score."""

    result: SearchResult
    rerank_score: float
    original_score: float


class LocalReranker:
    """Local reranker using sentence-transformers cross-encoder models.

    Supports models like:
    - mixedbread-ai/mxbai-rerank-base-v1 (faster, ~100MB)
    - mixedbread-ai/mxbai-rerank-large-v2 (better quality, ~1.4GB)
    - BAAI/bge-reranker-v2-m3 (multilingual)
    """

    def __init__(
        self,
        model_name: str = "mixedbread-ai/mxbai-rerank-base-v1",
        device: str | None = None,
    ) -> None:
        """Initialize the reranker.

        Args:
            model_name: HuggingFace model name for the cross-encoder
            device: Device to use ('cpu', 'cuda', 'mps'). Auto-detected if None.
        """
        self.model_name = model_name
        self._model: Any = None
        self._device = device

    def _load_model(self) -> None:
        """Lazy load the model on first use."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise ImportError(
                "sentence-transformers required for reranking. "
                "Install with: uv pip install sentence-transformers"
            )

        # Auto-detect device
        if self._device is None:
            import torch
            if torch.backends.mps.is_available():
                self._device = "mps"  # Apple Silicon
            elif torch.cuda.is_available():
                self._device = "cuda"
            else:
                self._device = "cpu"

        self._model = CrossEncoder(
            self.model_name,
            device=self._device,
            max_length=512,
        )

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int | None = None,
    ) -> list[RerankResult]:
        """Rerank search results using cross-encoder.

        Args:
            query: Original search query
            results: Search results to rerank
            top_k: Number of top results to return (None = all)

        Returns:
            List of RerankResult sorted by rerank score
        """
        if not results:
            return []

        self._load_model()

        # Create query-document pairs
        pairs = []
        for result in results:
            text = result.chunk_text or result.title
            pairs.append([query, text])

        # Get rerank scores
        scores = self._model.predict(pairs)

        # Combine with original results
        reranked = []
        for result, score in zip(results, scores):
            reranked.append(
                RerankResult(
                    result=result,
                    rerank_score=float(score),
                    original_score=result.score,
                )
            )

        # Sort by rerank score
        reranked.sort(key=lambda x: x.rerank_score, reverse=True)

        if top_k is not None:
            reranked = reranked[:top_k]

        return reranked


# Global reranker instance (lazy loaded)
_reranker: LocalReranker | None = None


def get_reranker(
    model_name: str = "mixedbread-ai/mxbai-rerank-base-v1",
) -> LocalReranker:
    """Get or create the global reranker instance.

    Args:
        model_name: Model to use (only used on first call)

    Returns:
        LocalReranker instance
    """
    global _reranker
    if _reranker is None:
        _reranker = LocalReranker(model_name=model_name)
    return _reranker


async def rerank_results(
    query: str,
    results: list[SearchResult],
    top_k: int | None = None,
    model_name: str = "mixedbread-ai/mxbai-rerank-base-v1",
) -> list[SearchResult]:
    """Convenience function to rerank and return SearchResults.

    Args:
        query: Original search query
        results: Search results to rerank
        top_k: Number of top results to return
        model_name: Reranker model to use

    Returns:
        List of SearchResult with updated scores from reranking
    """
    reranker = get_reranker(model_name)
    reranked = reranker.rerank(query, results, top_k)

    # Update scores to reflect reranking
    output = []
    for rr in reranked:
        # Create new result with rerank score
        result = SearchResult(
            content_id=rr.result.content_id,
            title=rr.result.title,
            content_type=rr.result.content_type,
            score=rr.rerank_score,  # Use rerank score
            chunk_text=rr.result.chunk_text,
            source_ref=rr.result.source_ref,
            bm25_rank=rr.result.bm25_rank,
            vector_rank=rr.result.vector_rank,
        )
        output.append(result)

    return output


# LlamaIndex integration
class LlamaIndexReranker:
    """Reranker with LlamaIndex NodePostprocessor interface."""

    def __init__(
        self,
        model_name: str = "mixedbread-ai/mxbai-rerank-base-v1",
        top_n: int = 5,
    ) -> None:
        """Initialize LlamaIndex-compatible reranker.

        Args:
            model_name: Cross-encoder model name
            top_n: Number of nodes to return after reranking
        """
        self.model_name = model_name
        self.top_n = top_n
        self._reranker = LocalReranker(model_name=model_name)

    def postprocess_nodes(
        self,
        nodes: list[Any],
        query_bundle: Any | None = None,
        **kwargs: Any,
    ) -> list[Any]:
        """Rerank nodes using cross-encoder.

        Args:
            nodes: List of NodeWithScore objects
            query_bundle: QueryBundle with query text

        Returns:
            Reranked list of NodeWithScore
        """
        from llama_index.core.schema import NodeWithScore

        if not nodes or query_bundle is None:
            return nodes

        self._reranker._load_model()

        query = query_bundle.query_str

        # Create pairs
        pairs = []
        for node in nodes:
            text = node.node.text if hasattr(node, "node") else str(node)
            pairs.append([query, text])

        # Get scores
        scores = self._reranker._model.predict(pairs)

        # Update and sort
        reranked = []
        for node, score in zip(nodes, scores):
            if hasattr(node, "score"):
                node.score = float(score)
            reranked.append((node, float(score)))

        reranked.sort(key=lambda x: x[1], reverse=True)

        return [n for n, _ in reranked[: self.top_n]]
