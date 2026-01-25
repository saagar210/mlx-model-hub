"""
Mutation Strategies for Code Evolution.

Provides various strategies for proposing code mutations:
- RandomMutationStrategy: Random exploration of code space
- LLMGuidedStrategy: LLM-based intelligent improvements
- ErrorFixStrategy: Specialized for fixing errors
- EvolutionaryStrategy: Genetic algorithm approach
- CrossoverStrategy: Combine code from multiple versions
- UniformCrossover: Uniform crossover at statement level
"""

from sia.evolution.strategies.base import MutationProposal, MutationStrategy
from sia.evolution.strategies.crossover import (
    CrossoverCandidate,
    CrossoverResult,
    CrossoverStrategy,
    UniformCrossover,
)
from sia.evolution.strategies.evolutionary import (
    EvolutionaryStrategy,
    Individual,
    Population,
)
from sia.evolution.strategies.llm_guided import ErrorFixStrategy, LLMGuidedStrategy
from sia.evolution.strategies.random import RandomMutationStrategy

__all__ = [
    # Base
    "MutationStrategy",
    "MutationProposal",
    # Random
    "RandomMutationStrategy",
    # LLM Guided
    "LLMGuidedStrategy",
    "ErrorFixStrategy",
    # Evolutionary
    "EvolutionaryStrategy",
    "Individual",
    "Population",
    # Crossover
    "CrossoverStrategy",
    "CrossoverCandidate",
    "CrossoverResult",
    "UniformCrossover",
]


# Strategy registry for easy lookup
STRATEGY_REGISTRY: dict[str, type[MutationStrategy]] = {
    "random": RandomMutationStrategy,
    "llm_guided": LLMGuidedStrategy,
    "error_fix": ErrorFixStrategy,
    "evolutionary": EvolutionaryStrategy,
    "crossover": CrossoverStrategy,
    "uniform_crossover": UniformCrossover,
}


def get_strategy(name: str, **kwargs) -> MutationStrategy:
    """
    Get a mutation strategy by name.

    Args:
        name: Strategy name ('random', 'llm_guided', 'evolutionary', etc.)
        **kwargs: Arguments to pass to strategy constructor

    Returns:
        Instantiated strategy

    Raises:
        ValueError: If strategy name is not recognized
    """
    if name not in STRATEGY_REGISTRY:
        available = ", ".join(STRATEGY_REGISTRY.keys())
        raise ValueError(f"Unknown strategy '{name}'. Available: {available}")

    return STRATEGY_REGISTRY[name](**kwargs)


def list_strategies() -> list[str]:
    """List all available strategy names."""
    return list(STRATEGY_REGISTRY.keys())
