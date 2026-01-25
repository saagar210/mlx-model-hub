"""
Code Evolution Module.

Provides self-modification capabilities for agents:
- Sandbox: Isolated execution environment
- Mutator: Code mutation mechanisms
- Strategies: Various mutation approaches
- Validator: Code validation (syntax, types, security)
- Rollback: Version management and rollback
- Orchestrator: Full evolution cycle coordination
"""

from sia.evolution.mutator import CodeMutator, Mutation, MutationResult
from sia.evolution.orchestrator import (
    EvolutionAttempt,
    EvolutionConfig,
    EvolutionOrchestrator,
    EvolutionStatus,
    evolve_code,
)
from sia.evolution.rollback import (
    CodeSnapshot,
    IntegrityError,
    RollbackManager,
    RollbackResult,
)
from sia.evolution.sandbox import (
    RestrictedSandbox,
    Sandbox,
    SandboxConfig,
    SandboxError,
    SandboxImportError,
    SandboxManager,
    SandboxMemoryError,
    SandboxPool,
    SandboxResult,
    SandboxSecurityError,
    SandboxTimeoutError,
)
from sia.evolution.strategies import (
    CrossoverCandidate,
    CrossoverResult,
    CrossoverStrategy,
    ErrorFixStrategy,
    EvolutionaryStrategy,
    Individual,
    LLMGuidedStrategy,
    MutationProposal,
    MutationStrategy,
    Population,
    RandomMutationStrategy,
    UniformCrossover,
    get_strategy,
    list_strategies,
)
from sia.evolution.validator import (
    CodeValidator,
    QuickValidator,
    ValidationIssue,
    ValidationResult,
    validate_code,
)

__all__ = [
    # Sandbox
    "Sandbox",
    "RestrictedSandbox",
    "SandboxConfig",
    "SandboxResult",
    "SandboxPool",
    "SandboxManager",
    # Sandbox Exceptions
    "SandboxError",
    "SandboxSecurityError",
    "SandboxTimeoutError",
    "SandboxMemoryError",
    "SandboxImportError",
    # Mutator
    "CodeMutator",
    "Mutation",
    "MutationResult",
    # Strategies
    "MutationStrategy",
    "MutationProposal",
    "RandomMutationStrategy",
    "LLMGuidedStrategy",
    "ErrorFixStrategy",
    "EvolutionaryStrategy",
    "Individual",
    "Population",
    "CrossoverStrategy",
    "CrossoverCandidate",
    "CrossoverResult",
    "UniformCrossover",
    "get_strategy",
    "list_strategies",
    # Validator
    "CodeValidator",
    "ValidationResult",
    "ValidationIssue",
    "QuickValidator",
    "validate_code",
    # Rollback
    "RollbackManager",
    "RollbackResult",
    "CodeSnapshot",
    "IntegrityError",
    # Orchestrator
    "EvolutionOrchestrator",
    "EvolutionConfig",
    "EvolutionAttempt",
    "EvolutionStatus",
    "evolve_code",
]
