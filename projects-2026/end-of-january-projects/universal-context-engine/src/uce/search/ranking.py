"""
Result ranking and fusion.

Implements Reciprocal Rank Fusion (RRF) and temporal decay.
"""

import math
from datetime import datetime, timedelta
from uuid import UUID


class RankingEngine:
    """
    Ranking engine for combining and reranking search results.
    """

    def __init__(
        self,
        rrf_k: int = 60,
        decay_half_life_hours: int = 168,
    ) -> None:
        """
        Initialize ranking engine.

        Args:
            rrf_k: RRF constant (default 60)
            decay_half_life_hours: Hours for score to decay by half (default 1 week)
        """
        self.rrf_k = rrf_k
        self.decay_half_life = decay_half_life_hours

    def rrf_fusion(self, *result_lists: list[dict]) -> list[dict]:
        """
        Combine multiple ranked lists using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) for each list

        Args:
            result_lists: Multiple lists of results with 'id' and 'score'

        Returns:
            Combined list with fused scores
        """
        scores: dict[UUID, float] = {}
        match_types: dict[UUID, list[str]] = {}
        original_scores: dict[UUID, list[float]] = {}

        for results in result_lists:
            for rank, result in enumerate(results, 1):
                item_id = result["id"]
                rrf_score = 1.0 / (self.rrf_k + rank)

                scores[item_id] = scores.get(item_id, 0.0) + rrf_score

                if item_id not in match_types:
                    match_types[item_id] = []
                    original_scores[item_id] = []

                match_type = result.get("match_type", "unknown")
                if match_type not in match_types[item_id]:
                    match_types[item_id].append(match_type)

                original_scores[item_id].append(result.get("score", 0.0))

        return [
            {
                "id": item_id,
                "score": score,
                "match_type": "+".join(match_types[item_id]),
                "original_scores": original_scores[item_id],
            }
            for item_id, score in scores.items()
        ]

    def apply_temporal_decay(
        self,
        results: list[dict],
        timestamps: dict[UUID, datetime],
        reference_time: datetime | None = None,
    ) -> list[dict]:
        """
        Apply temporal decay to scores based on age.

        Uses exponential decay: score * e^(-lambda * age_hours)
        where lambda = ln(2) / half_life

        Args:
            results: List of results with 'id' and 'score'
            timestamps: Mapping of item IDs to their timestamps
            reference_time: Time to measure age from (default: now)

        Returns:
            Results with decayed scores
        """
        ref_time = reference_time or datetime.utcnow()
        decay_lambda = math.log(2) / self.decay_half_life

        decayed = []
        for result in results:
            item_id = result["id"]
            score = result["score"]

            if item_id in timestamps:
                age_hours = (ref_time - timestamps[item_id]).total_seconds() / 3600
                decay_factor = math.exp(-decay_lambda * age_hours)
                decayed_score = score * decay_factor
            else:
                # No timestamp - apply moderate decay
                decayed_score = score * 0.7

            decayed.append({
                **result,
                "score": decayed_score,
                "original_score": score,
            })

        return decayed

    def apply_source_weights(
        self,
        results: list[dict],
        source_weights: dict[str, float],
        sources: dict[UUID, str],
    ) -> list[dict]:
        """
        Apply source quality weights to scores.

        Args:
            results: List of results
            source_weights: Mapping of source to weight (0-1)
            sources: Mapping of item IDs to their sources

        Returns:
            Results with weighted scores
        """
        weighted = []
        for result in results:
            item_id = result["id"]
            score = result["score"]

            source = sources.get(item_id, "unknown")
            weight = source_weights.get(source, 0.7)

            weighted.append({
                **result,
                "score": score * weight,
                "source_weight": weight,
            })

        return weighted

    def normalize_scores(self, results: list[dict]) -> list[dict]:
        """
        Normalize scores to 0-1 range.

        Args:
            results: List of results

        Returns:
            Results with normalized scores
        """
        if not results:
            return results

        scores = [r["score"] for r in results]
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            return [
                {**r, "score": 1.0}
                for r in results
            ]

        return [
            {
                **r,
                "score": (r["score"] - min_score) / (max_score - min_score),
                "raw_score": r["score"],
            }
            for r in results
        ]

    def rank(
        self,
        results: list[dict],
        top_k: int | None = None,
    ) -> list[dict]:
        """
        Sort results by score descending.

        Args:
            results: List of results
            top_k: Optional limit

        Returns:
            Sorted results
        """
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)

        if top_k:
            return sorted_results[:top_k]

        return sorted_results


__all__ = ["RankingEngine"]
