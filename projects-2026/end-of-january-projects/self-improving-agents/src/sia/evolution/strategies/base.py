"""
Base Mutation Strategy.

Defines the interface for mutation strategies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sia.evolution.mutator import Mutation, MutationResult


@dataclass
class MutationProposal:
    """A proposed mutation from a strategy."""

    id: UUID = field(default_factory=uuid4)
    strategy: str = ""
    mutations: list[Mutation] = field(default_factory=list)

    # Metadata
    rationale: str = ""
    expected_improvement: str = ""
    confidence: float = 0.5
    risk_level: str = "medium"

    # For tracking
    metadata: dict[str, Any] = field(default_factory=dict)


class MutationStrategy(ABC):
    """
    Base class for mutation strategies.

    Defines the interface for generating code mutations.
    """

    def __init__(self, name: str = "base"):
        """
        Initialize strategy.

        Args:
            name: Strategy name
        """
        self.name = name

    @abstractmethod
    def propose_mutations(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> list[MutationProposal]:
        """
        Propose mutations for the given code.

        Args:
            code: Python code to mutate
            context: Additional context (execution history, etc.)

        Returns:
            List of mutation proposals
        """
        pass

    @abstractmethod
    def evaluate_mutation(
        self,
        original_code: str,
        mutated_code: str,
        test_results: dict[str, Any] | None = None,
    ) -> float:
        """
        Evaluate the quality of a mutation.

        Args:
            original_code: Original code
            mutated_code: Mutated code
            test_results: Optional test results

        Returns:
            Score from 0 to 1
        """
        pass

    def filter_proposals(
        self,
        proposals: list[MutationProposal],
        min_confidence: float = 0.5,
        max_risk: str = "high",
    ) -> list[MutationProposal]:
        """
        Filter proposals by confidence and risk.

        Args:
            proposals: List of proposals
            min_confidence: Minimum confidence threshold
            max_risk: Maximum acceptable risk level

        Returns:
            Filtered proposals
        """
        risk_levels = {"low": 0, "medium": 1, "high": 2}
        max_risk_value = risk_levels.get(max_risk, 2)

        return [
            p for p in proposals
            if p.confidence >= min_confidence
            and risk_levels.get(p.risk_level, 2) <= max_risk_value
        ]
