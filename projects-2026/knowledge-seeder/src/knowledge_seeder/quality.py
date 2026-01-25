"""Content quality scoring and validation."""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityScore:
    """Quality assessment result for extracted content."""

    # Overall score (0-100)
    score: float

    # Component scores (0-100 each)
    length_score: float = 0.0
    density_score: float = 0.0
    structure_score: float = 0.0
    language_score: float = 0.0
    uniqueness_score: float = 0.0

    # Quality flags
    is_acceptable: bool = True
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    # Metadata
    word_count: int = 0
    sentence_count: int = 0
    avg_sentence_length: float = 0.0
    code_ratio: float = 0.0
    link_density: float = 0.0

    @property
    def grade(self) -> str:
        """Get letter grade for quality score."""
        if self.score >= 90:
            return "A"
        if self.score >= 80:
            return "B"
        if self.score >= 70:
            return "C"
        if self.score >= 60:
            return "D"
        return "F"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": round(self.score, 2),
            "grade": self.grade,
            "is_acceptable": self.is_acceptable,
            "components": {
                "length": round(self.length_score, 2),
                "density": round(self.density_score, 2),
                "structure": round(self.structure_score, 2),
                "language": round(self.language_score, 2),
                "uniqueness": round(self.uniqueness_score, 2),
            },
            "metrics": {
                "word_count": self.word_count,
                "sentence_count": self.sentence_count,
                "avg_sentence_length": round(self.avg_sentence_length, 2),
                "code_ratio": round(self.code_ratio, 4),
                "link_density": round(self.link_density, 4),
            },
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


class ContentQualityScorer:
    """Score content quality for knowledge extraction."""

    # Optimal ranges for scoring
    OPTIMAL_WORD_COUNT_MIN = 300
    OPTIMAL_WORD_COUNT_MAX = 50000
    OPTIMAL_SENTENCE_LENGTH_MIN = 10
    OPTIMAL_SENTENCE_LENGTH_MAX = 30
    MAX_CODE_RATIO = 0.6  # Allow up to 60% code for technical docs
    MAX_LINK_DENSITY = 0.1  # Links shouldn't dominate content

    # Weight factors for overall score
    WEIGHTS = {
        "length": 0.20,
        "density": 0.20,
        "structure": 0.25,
        "language": 0.20,
        "uniqueness": 0.15,
    }

    # Minimum acceptable score
    MIN_ACCEPTABLE_SCORE = 40

    def __init__(
        self,
        min_acceptable_score: float | None = None,
    ) -> None:
        """Initialize scorer.

        Args:
            min_acceptable_score: Minimum score to consider content acceptable
        """
        self.min_acceptable = min_acceptable_score or self.MIN_ACCEPTABLE_SCORE

    def score(self, content: str, source_type: str | None = None) -> QualityScore:
        """Score content quality.

        Args:
            content: Text content to score
            source_type: Type of source (affects scoring weights)

        Returns:
            QualityScore with detailed assessment
        """
        if not content or not content.strip():
            return QualityScore(
                score=0,
                is_acceptable=False,
                issues=["Empty or whitespace-only content"],
            )

        # Calculate component scores
        length_score, length_metrics = self._score_length(content)
        density_score = self._score_density(content, length_metrics)
        structure_score = self._score_structure(content, source_type)
        language_score = self._score_language(content, length_metrics)
        uniqueness_score = self._score_uniqueness(content)

        # Adjust weights based on source type
        weights = self._adjust_weights(source_type)

        # Calculate weighted overall score
        overall = (
            length_score * weights["length"]
            + density_score * weights["density"]
            + structure_score * weights["structure"]
            + language_score * weights["language"]
            + uniqueness_score * weights["uniqueness"]
        )

        # Collect issues and suggestions
        issues = []
        suggestions = []

        if length_metrics["word_count"] < self.OPTIMAL_WORD_COUNT_MIN:
            issues.append(f"Content too short ({length_metrics['word_count']} words)")
            suggestions.append("Consider fetching additional content or combining sources")

        if length_metrics["avg_sentence_length"] > self.OPTIMAL_SENTENCE_LENGTH_MAX:
            issues.append("Sentences are too long on average")
            suggestions.append("May contain poorly parsed content")

        if length_metrics["code_ratio"] > self.MAX_CODE_RATIO and source_type != "github":
            issues.append(f"High code ratio ({length_metrics['code_ratio']:.1%})")

        if length_metrics["link_density"] > self.MAX_LINK_DENSITY:
            issues.append(f"High link density ({length_metrics['link_density']:.1%})")
            suggestions.append("Content may be navigation-heavy")

        return QualityScore(
            score=overall,
            length_score=length_score,
            density_score=density_score,
            structure_score=structure_score,
            language_score=language_score,
            uniqueness_score=uniqueness_score,
            is_acceptable=overall >= self.min_acceptable,
            issues=issues,
            suggestions=suggestions,
            word_count=length_metrics["word_count"],
            sentence_count=length_metrics["sentence_count"],
            avg_sentence_length=length_metrics["avg_sentence_length"],
            code_ratio=length_metrics["code_ratio"],
            link_density=length_metrics["link_density"],
        )

    def _score_length(self, content: str) -> tuple[float, dict[str, Any]]:
        """Score based on content length."""
        # Word count
        words = content.split()
        word_count = len(words)

        # Sentence count (approximate)
        sentences = re.split(r"[.!?]+", content)
        sentence_count = len([s for s in sentences if s.strip()])

        # Average sentence length
        avg_sentence_length = word_count / max(sentence_count, 1)

        # Code block detection
        code_blocks = re.findall(r"```[\s\S]*?```|`[^`]+`", content)
        code_chars = sum(len(block) for block in code_blocks)
        code_ratio = code_chars / max(len(content), 1)

        # Link density
        links = re.findall(r"https?://[^\s]+|\[.*?\]\(.*?\)", content)
        link_chars = sum(len(link) for link in links)
        link_density = link_chars / max(len(content), 1)

        metrics = {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "avg_sentence_length": avg_sentence_length,
            "code_ratio": code_ratio,
            "link_density": link_density,
        }

        # Score based on optimal range
        if word_count < 50:
            score = word_count * 2  # 0-100 for 0-50 words
        elif word_count < self.OPTIMAL_WORD_COUNT_MIN:
            score = 50 + (word_count - 50) / (self.OPTIMAL_WORD_COUNT_MIN - 50) * 30
        elif word_count <= self.OPTIMAL_WORD_COUNT_MAX:
            score = 100  # Optimal range
        else:
            # Penalty for very long content (may have issues)
            excess = word_count - self.OPTIMAL_WORD_COUNT_MAX
            score = max(70, 100 - math.log10(excess + 1) * 10)

        return min(100, max(0, score)), metrics

    def _score_density(self, content: str, metrics: dict[str, Any]) -> float:
        """Score information density."""
        # Penalize high code ratio (unless it's code documentation)
        code_penalty = 0
        if metrics["code_ratio"] > self.MAX_CODE_RATIO:
            code_penalty = (metrics["code_ratio"] - self.MAX_CODE_RATIO) * 100

        # Penalize high link density
        link_penalty = 0
        if metrics["link_density"] > self.MAX_LINK_DENSITY:
            link_penalty = (metrics["link_density"] - self.MAX_LINK_DENSITY) * 200

        # Check for repetitive patterns
        lines = content.split("\n")
        unique_lines = len(set(lines))
        repetition_penalty = 0
        if len(lines) > 10:
            repetition_ratio = unique_lines / len(lines)
            if repetition_ratio < 0.5:
                repetition_penalty = (1 - repetition_ratio) * 50

        score = 100 - code_penalty - link_penalty - repetition_penalty
        return min(100, max(0, score))

    def _score_structure(self, content: str, source_type: str | None) -> float:
        """Score content structure (headings, paragraphs, lists)."""
        score = 50  # Base score

        # Check for markdown headings
        headings = re.findall(r"^#{1,6}\s+.+$", content, re.MULTILINE)
        if headings:
            score += min(20, len(headings) * 2)

        # Check for paragraphs (blank lines between text blocks)
        paragraphs = re.split(r"\n\s*\n", content)
        meaningful_paragraphs = [p for p in paragraphs if len(p.strip()) > 50]
        if len(meaningful_paragraphs) >= 3:
            score += 15

        # Check for lists
        list_items = re.findall(r"^[\s]*[-*•]\s+.+$|^\s*\d+\.\s+.+$", content, re.MULTILINE)
        if list_items:
            score += min(10, len(list_items))

        # Bonus for well-structured code documentation
        if source_type in ("github", "arxiv"):
            if "##" in content or "###" in content:
                score += 5

        return min(100, max(0, score))

    def _score_language(self, content: str, metrics: dict[str, Any]) -> float:
        """Score language quality."""
        score = 70  # Base score

        # Penalize very short or very long sentences
        avg_len = metrics["avg_sentence_length"]
        if avg_len < self.OPTIMAL_SENTENCE_LENGTH_MIN:
            score -= (self.OPTIMAL_SENTENCE_LENGTH_MIN - avg_len) * 2
        elif avg_len > self.OPTIMAL_SENTENCE_LENGTH_MAX:
            score -= (avg_len - self.OPTIMAL_SENTENCE_LENGTH_MAX)

        # Check for common boilerplate patterns
        boilerplate_patterns = [
            r"cookie",
            r"privacy policy",
            r"terms of service",
            r"subscribe to our",
            r"sign up for",
            r"follow us on",
            r"share this",
        ]
        boilerplate_count = sum(
            1 for p in boilerplate_patterns if re.search(p, content, re.IGNORECASE)
        )
        score -= boilerplate_count * 5

        # Check for proper capitalization at sentence starts
        proper_caps = re.findall(r"(?:^|[.!?]\s+)[A-Z]", content)
        if len(proper_caps) >= metrics["sentence_count"] * 0.7:
            score += 10

        return min(100, max(0, score))

    def _score_uniqueness(self, content: str) -> float:
        """Score content uniqueness (low repetition)."""
        # N-gram analysis for repetition
        words = content.lower().split()
        if len(words) < 20:
            return 50  # Not enough data

        # Check bigram repetition
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
        unique_bigrams = len(set(bigrams))
        bigram_uniqueness = unique_bigrams / len(bigrams) if bigrams else 0

        # Check for repeated phrases (3+ words)
        trigrams = [f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words) - 2)]
        trigram_counts = {}
        for t in trigrams:
            trigram_counts[t] = trigram_counts.get(t, 0) + 1
        repeated_trigrams = sum(1 for c in trigram_counts.values() if c > 2)
        trigram_penalty = min(30, repeated_trigrams * 3)

        score = bigram_uniqueness * 100 - trigram_penalty
        return min(100, max(0, score))

    def _adjust_weights(self, source_type: str | None) -> dict[str, float]:
        """Adjust scoring weights based on source type."""
        weights = self.WEIGHTS.copy()

        if source_type == "github":
            # GitHub READMEs: structure and code ratio matter more
            weights["structure"] = 0.30
            weights["density"] = 0.15
        elif source_type == "arxiv":
            # arXiv papers: language quality and structure matter more
            weights["language"] = 0.25
            weights["structure"] = 0.25
            weights["length"] = 0.15
        elif source_type == "youtube":
            # YouTube transcripts: uniqueness matters less (natural speech)
            weights["uniqueness"] = 0.10
            weights["length"] = 0.25

        return weights


def score_content(content: str, source_type: str | None = None) -> QualityScore:
    """Convenience function to score content quality.

    Args:
        content: Text content to score
        source_type: Type of source

    Returns:
        QualityScore with detailed assessment
    """
    scorer = ContentQualityScorer()
    return scorer.score(content, source_type)
