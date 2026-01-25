"""
Reranking Service - Rerank search results using a cross-encoder model.

Uses mxbai-rerank-large-v2 via Ollama for high-quality reranking.
"""

import time
from dataclasses import dataclass
from typing import Any

import httpx

from sia.config import SIAConfig, get_config


@dataclass
class RerankResult:
    """Result of reranking."""
    index: int
    score: float
    document: Any


@dataclass
class RerankResponse:
    """Response from reranking."""
    results: list[RerankResult]
    model: str
    latency_ms: int


class RerankService:
    """
    Rerank search results using a cross-encoder model.

    Usage:
        service = RerankService()
        results = await service.rerank(
            query="What is Python?",
            documents=["Python is a programming language", "Java is also a language"]
        )
    """

    def __init__(self, config: SIAConfig | None = None):
        self.config = config or get_config()
        self._client = httpx.AsyncClient(
            base_url=self.config.ollama.base_url,
            timeout=60.0,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def rerank(
        self,
        query: str,
        documents: list[str | dict[str, Any]],
        model: str | None = None,
        top_k: int | None = None,
        return_documents: bool = True,
    ) -> RerankResponse:
        """
        Rerank documents by relevance to query.

        Args:
            query: The query to rank against
            documents: List of documents (strings or dicts with 'content' field)
            model: Model to use (default: mxbai-rerank-large-v2)
            top_k: Return only top K results (default: all)
            return_documents: Include original documents in results

        Returns:
            RerankResponse with sorted results
        """
        model = model or self.config.rerank.model

        # Extract text from documents
        doc_texts = []
        for doc in documents:
            if isinstance(doc, str):
                doc_texts.append(doc)
            elif isinstance(doc, dict):
                doc_texts.append(doc.get("content", str(doc)))
            else:
                doc_texts.append(str(doc))

        start_time = time.time()

        # Use Ollama's generate endpoint with reranking prompt
        # Note: This is a workaround since Ollama doesn't have native rerank
        # In production, consider using a dedicated rerank endpoint
        scores = await self._score_documents(query, doc_texts, model)

        latency_ms = int((time.time() - start_time) * 1000)

        # Create results with scores
        results = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            results.append(RerankResult(
                index=i,
                score=score,
                document=doc if return_documents else None,
            ))

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)

        # Apply top_k
        if top_k:
            results = results[:top_k]

        return RerankResponse(
            results=results,
            model=model,
            latency_ms=latency_ms,
        )

    async def _score_documents(
        self,
        query: str,
        documents: list[str],
        model: str,
    ) -> list[float]:
        """
        Score documents against query.

        Uses the model to generate relevance scores.
        """
        scores = []

        for doc in documents:
            # Create a prompt that asks for relevance scoring
            prompt = f"""Rate the relevance of the following document to the query on a scale of 0 to 1.
Only respond with a single number between 0 and 1.

Query: {query}

Document: {doc}

Relevance score:"""

            try:
                response = await self._client.post(
                    "/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0,
                            "num_predict": 10,
                        },
                    },
                )
                response.raise_for_status()

                data = response.json()
                score_text = data.get("response", "0.5").strip()

                # Parse score
                try:
                    score = float(score_text.split()[0])
                    score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
                except (ValueError, IndexError):
                    score = 0.5  # Default score

                scores.append(score)

            except Exception:
                scores.append(0.5)  # Default on error

        return scores

    async def rerank_with_fusion(
        self,
        query: str,
        result_sets: list[list[dict[str, Any]]],
        content_field: str = "content",
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Rerank and fuse multiple result sets.

        Uses Reciprocal Rank Fusion (RRF) followed by reranking.

        Args:
            query: The search query
            result_sets: Multiple lists of search results
            content_field: Field containing text content
            top_k: Number of results to return

        Returns:
            Fused and reranked results
        """
        # RRF fusion
        k = 60  # RRF constant
        scores: dict[int, float] = {}  # Using hash of content as key
        documents: dict[int, dict] = {}

        for results in result_sets:
            for rank, doc in enumerate(results, start=1):
                content = doc.get(content_field, "")
                doc_id = hash(content)

                if doc_id not in scores:
                    scores[doc_id] = 0
                    documents[doc_id] = doc

                scores[doc_id] += 1 / (k + rank)

        # Sort by RRF score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        fused_docs = [documents[doc_id] for doc_id in sorted_ids[:top_k * 2]]

        # Rerank the fused results
        if fused_docs:
            rerank_response = await self.rerank(
                query=query,
                documents=fused_docs,
                top_k=top_k,
            )
            return [r.document for r in rerank_response.results if r.document]

        return []

    async def health_check(self) -> dict[str, Any]:
        """Check reranking service health."""
        try:
            result = await self.rerank(
                query="test",
                documents=["test document"],
            )
            return {
                "status": "healthy",
                "model": result.model,
                "latency_ms": result.latency_ms,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
