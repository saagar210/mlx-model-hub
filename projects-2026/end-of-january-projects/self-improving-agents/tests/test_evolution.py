"""
Tests for the Evolution Module.

Tests code self-modification capabilities including:
- Sandbox execution
- Code mutation
- Mutation strategies
- Code validation
- Rollback mechanism
- Evolution orchestration
"""

import ast
import pytest
from uuid import uuid4

from sia.evolution import (
    # Sandbox
    Sandbox,
    SandboxConfig,
    SandboxResult,
    SandboxPool,
    # Mutator
    CodeMutator,
    Mutation,
    MutationResult,
    # Strategies
    MutationStrategy,
    MutationProposal,
    RandomMutationStrategy,
    LLMGuidedStrategy,
    ErrorFixStrategy,
    EvolutionaryStrategy,
    CrossoverStrategy,
    CrossoverCandidate,
    UniformCrossover,
    get_strategy,
    list_strategies,
    # Validator
    CodeValidator,
    ValidationResult,
    ValidationIssue,
    QuickValidator,
    validate_code,
    # Rollback
    RollbackManager,
    RollbackResult,
    CodeSnapshot,
    # Orchestrator
    EvolutionOrchestrator,
    EvolutionConfig,
    EvolutionAttempt,
    EvolutionStatus,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_code():
    """Simple sample code for testing."""
    return '''
def greet(name):
    return f"Hello, {name}!"

def add(a, b):
    return a + b

class Calculator:
    def multiply(self, x, y):
        return x * y
'''


@pytest.fixture
def code_with_issues():
    """Code with various issues for validation testing."""
    return '''
import os

def dangerous():
    eval(input())  # Dangerous!
    exec("print('bad')")  # Also dangerous
    os.system("ls")  # Shell command

def bare_except():
    try:
        pass
    except:  # Bare except
        pass

def mutable_default(items=[]):
    items.append(1)
    return items
'''


@pytest.fixture
def simple_function():
    """Simple function for mutation testing."""
    return '''
def calculate(x, y):
    result = x + y
    return result
'''


# ============================================================================
# Sandbox Tests
# ============================================================================


class TestSandbox:
    """Tests for sandbox execution."""

    @pytest.mark.asyncio
    async def test_sandbox_creation(self):
        """Test sandbox can be created."""
        config = SandboxConfig(timeout_seconds=5, max_memory_mb=64)
        sandbox = Sandbox(config)
        assert sandbox.config.timeout_seconds == 5
        assert sandbox.config.max_memory_mb == 64

    @pytest.mark.asyncio
    async def test_sandbox_validate_syntax_valid(self, sample_code):
        """Test syntax validation with valid code."""
        sandbox = Sandbox()
        await sandbox.create()
        result = await sandbox.validate_syntax(sample_code)
        assert result.success
        assert result.error is None
        await sandbox.cleanup()

    @pytest.mark.asyncio
    async def test_sandbox_validate_syntax_invalid(self):
        """Test syntax validation with invalid code."""
        sandbox = Sandbox()
        result = await sandbox.validate_syntax("def broken(")
        assert not result.success
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_sandbox_check_imports_valid(self, sample_code):
        """Test import checking with valid code."""
        sandbox = Sandbox()
        await sandbox.create()
        result = await sandbox.check_imports(sample_code)
        assert result.success
        await sandbox.cleanup()

    @pytest.mark.asyncio
    async def test_sandbox_cleanup(self):
        """Test sandbox cleanup."""
        sandbox = Sandbox()
        await sandbox.cleanup()
        # Should not raise


class TestSandboxConfig:
    """Tests for sandbox configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SandboxConfig()
        assert config.timeout_seconds == 60
        assert config.max_memory_mb == 512
        assert config.network_enabled is False

    def test_custom_config(self):
        """Test custom configuration."""
        config = SandboxConfig(
            timeout_seconds=120,
            max_memory_mb=1024,
            network_enabled=True,
        )
        assert config.timeout_seconds == 120
        assert config.max_memory_mb == 1024
        assert config.network_enabled is True


# ============================================================================
# Mutator Tests
# ============================================================================


class TestCodeMutator:
    """Tests for code mutation."""

    def test_mutate_empty_mutations(self, sample_code):
        """Test mutation with no mutations."""
        mutator = CodeMutator()
        result = mutator.mutate(sample_code, [])
        assert result.syntax_valid
        assert result.mutated_code == sample_code

    def test_mutate_single_mutation(self, simple_function):
        """Test single mutation."""
        mutator = CodeMutator()
        mutation = Mutation(
            mutation_type="add",
            target="calculate",
            description="Add logging",
            mutated_code='    print("entering calculate")',
            start_line=2,
        )
        result = mutator.mutate(simple_function, [mutation])
        assert result.syntax_valid
        assert "print" in result.mutated_code

    def test_get_functions(self, sample_code):
        """Test extracting functions from code."""
        mutator = CodeMutator()
        functions = mutator.get_functions(sample_code)
        names = [f["name"] for f in functions]
        assert "greet" in names
        assert "add" in names

    def test_replace_function(self, sample_code):
        """Test replacing a function."""
        mutator = CodeMutator()
        new_func = '''def add(a, b):
    """Add two numbers."""
    return a + b'''
        result = mutator.replace_function(sample_code, "add", new_func)
        assert result.syntax_valid
        assert '"""Add two numbers."""' in result.mutated_code

    def test_add_function(self, sample_code):
        """Test adding a function."""
        mutator = CodeMutator()
        new_func = '''def subtract(a, b):
    return a - b'''
        result = mutator.add_function(sample_code, new_func, after_function="add")
        assert result.syntax_valid
        assert "def subtract" in result.mutated_code

    def test_mutation_result_diff(self, simple_function):
        """Test that mutations generate diffs."""
        mutator = CodeMutator()
        mutation = Mutation(
            mutation_type="replace",
            target="result",
            description="Change variable",
            original_code="result = x + y",
            mutated_code="result = x + y + 1",
        )
        result = mutator.mutate(simple_function, [mutation])
        assert result.syntax_valid
        assert result.unified_diff is not None or result.mutated_code != simple_function


class TestMutation:
    """Tests for Mutation dataclass."""

    def test_mutation_creation(self):
        """Test mutation creation."""
        mutation = Mutation(
            mutation_type="add",
            target="function_name",
            description="Add logging",
        )
        assert mutation.mutation_type == "add"
        assert mutation.target == "function_name"
        assert mutation.id is not None

    def test_mutation_with_code(self):
        """Test mutation with code changes."""
        mutation = Mutation(
            mutation_type="replace",
            target="variable",
            description="Change value",
            original_code="x = 1",
            mutated_code="x = 2",
        )
        assert mutation.original_code == "x = 1"
        assert mutation.mutated_code == "x = 2"


# ============================================================================
# Strategy Tests
# ============================================================================


class TestRandomMutationStrategy:
    """Tests for random mutation strategy."""

    def test_create_strategy(self):
        """Test strategy creation."""
        strategy = RandomMutationStrategy()
        assert strategy.name == "random"

    def test_propose_mutations(self, sample_code):
        """Test proposing mutations."""
        strategy = RandomMutationStrategy(mutation_rate=0.5, seed=42)
        proposals = strategy.propose_mutations(sample_code)
        assert isinstance(proposals, list)
        # May or may not generate proposals due to randomness

    def test_propose_mutations_with_seed(self, sample_code):
        """Test that seed produces deterministic-ish results."""
        strategy = RandomMutationStrategy(seed=42)
        proposals = strategy.propose_mutations(sample_code)

        # With a seed, we should get some proposals
        # (exact number varies due to internal randomness)
        assert isinstance(proposals, list)

    def test_evaluate_mutation_valid(self, sample_code):
        """Test evaluating valid mutation."""
        strategy = RandomMutationStrategy()
        score = strategy.evaluate_mutation(
            sample_code,
            sample_code,  # Same code
            {"passed": True}
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Valid code should score well

    def test_evaluate_mutation_invalid_syntax(self, sample_code):
        """Test evaluating mutation with invalid syntax."""
        strategy = RandomMutationStrategy()
        score = strategy.evaluate_mutation(
            sample_code,
            "def broken(",  # Invalid syntax
            None
        )
        assert score == 0.0


class TestLLMGuidedStrategy:
    """Tests for LLM-guided mutation strategy."""

    def test_create_strategy(self):
        """Test strategy creation."""
        strategy = LLMGuidedStrategy()
        assert strategy.name == "llm_guided"

    def test_propose_without_llm(self, sample_code):
        """Test proposing mutations without LLM client."""
        strategy = LLMGuidedStrategy()
        proposals = strategy.propose_mutations(sample_code)
        # Should fall back to rule-based suggestions
        assert isinstance(proposals, list)

    def test_detect_missing_docstrings(self, simple_function):
        """Test detecting missing docstrings."""
        strategy = LLMGuidedStrategy()
        proposals = strategy._propose_without_llm(simple_function)
        # Should find functions without docstrings
        docstring_proposals = [
            p for p in proposals
            if "docstring" in p.rationale.lower()
        ]
        assert len(docstring_proposals) > 0

    def test_detect_bare_excepts(self, code_with_issues):
        """Test detecting bare except clauses."""
        strategy = LLMGuidedStrategy()
        proposals = strategy._propose_without_llm(code_with_issues)
        bare_except_proposals = [
            p for p in proposals
            if "except" in p.rationale.lower()
        ]
        assert len(bare_except_proposals) > 0


class TestErrorFixStrategy:
    """Tests for error fix strategy."""

    def test_create_strategy(self):
        """Test strategy creation."""
        strategy = ErrorFixStrategy()
        assert strategy.name == "error_fix"

    def test_propose_name_error_fix(self):
        """Test proposing fix for NameError."""
        strategy = ErrorFixStrategy()
        code = "print(undefined_var)"
        error = "NameError: name 'undefined_var' is not defined"

        proposals = strategy._propose_common_fixes(code, error)
        assert len(proposals) > 0
        assert any("undefined_var" in str(p.mutations) for p in proposals)

    def test_propose_key_error_fix(self):
        """Test proposing fix for KeyError."""
        strategy = ErrorFixStrategy()
        code = "data['missing_key']"
        error = "KeyError: 'missing_key'"

        proposals = strategy._propose_common_fixes(code, error)
        assert len(proposals) > 0
        assert any(".get(" in str(p.mutations) for p in proposals)


class TestEvolutionaryStrategy:
    """Tests for evolutionary mutation strategy."""

    def test_create_strategy(self):
        """Test strategy creation."""
        strategy = EvolutionaryStrategy(population_size=5, generations=2)
        assert strategy.name == "evolutionary"
        assert strategy.population_size == 5
        assert strategy.generations == 2

    def test_initialize_population(self, sample_code):
        """Test population initialization."""
        strategy = EvolutionaryStrategy(population_size=5, seed=42)
        population = strategy._initialize_population(sample_code)
        assert len(population.individuals) == 5

    def test_tournament_selection(self, sample_code):
        """Test tournament selection."""
        strategy = EvolutionaryStrategy(seed=42)
        strategy.population = strategy._initialize_population(sample_code)

        # Set some fitnesses
        for i, ind in enumerate(strategy.population.individuals):
            ind.fitness = float(i) / len(strategy.population.individuals)

        selected = strategy._tournament_selection()
        assert selected is not None


class TestCrossoverStrategy:
    """Tests for crossover strategy."""

    def test_create_strategy(self):
        """Test strategy creation."""
        strategy = CrossoverStrategy()
        assert strategy.name == "crossover"

    def test_add_candidate(self):
        """Test adding candidates."""
        strategy = CrossoverStrategy()
        candidate = strategy.add_candidate(
            code="def test(): pass",
            fitness=0.8,
            source="test"
        )
        assert candidate in strategy.candidates
        assert candidate.fitness == 0.8

    def test_function_crossover(self, sample_code):
        """Test function-level crossover."""
        strategy = CrossoverStrategy(seed=42)

        code1 = '''
def func_a():
    return 1

def func_b():
    return 2
'''
        code2 = '''
def func_a():
    return 10

def func_b():
    return 20
'''
        parent1 = CrossoverCandidate(code=code1, fitness=0.5)
        parent2 = CrossoverCandidate(code=code2, fitness=0.7)

        result = strategy._function_crossover(parent1, parent2)
        # May or may not succeed depending on AST structure
        if result:
            assert result.success
            assert result.child_code


class TestStrategyRegistry:
    """Tests for strategy registry."""

    def test_list_strategies(self):
        """Test listing available strategies."""
        strategies = list_strategies()
        assert "random" in strategies
        assert "llm_guided" in strategies
        assert "evolutionary" in strategies
        assert "crossover" in strategies

    def test_get_strategy(self):
        """Test getting strategy by name."""
        strategy = get_strategy("random")
        assert isinstance(strategy, RandomMutationStrategy)

    def test_get_strategy_with_kwargs(self):
        """Test getting strategy with kwargs."""
        strategy = get_strategy("random", mutation_rate=0.5)
        assert strategy.mutation_rate == 0.5

    def test_get_unknown_strategy(self):
        """Test getting unknown strategy."""
        with pytest.raises(ValueError):
            get_strategy("unknown_strategy")


# ============================================================================
# Validator Tests
# ============================================================================


class TestCodeValidator:
    """Tests for code validation."""

    def test_validate_valid_code(self, sample_code):
        """Test validating valid code."""
        validator = CodeValidator(enable_security_checking=False)
        result = validator.validate(sample_code)
        assert result.syntax_valid
        assert result.valid

    def test_validate_syntax_error(self):
        """Test validating code with syntax error."""
        validator = CodeValidator()
        result = validator.validate("def broken(")
        assert not result.syntax_valid
        assert not result.valid

    def test_validate_security_issues(self, code_with_issues):
        """Test detecting security issues."""
        validator = CodeValidator(security_level="high", enable_security_checking=True)
        result = validator.validate(code_with_issues)
        security_issues = [i for i in result.issues if i.category == "security"]
        # Should detect at least some security issues (eval, exec, os.system)
        assert len(security_issues) > 0

    def test_validate_dangerous_patterns(self):
        """Test detecting dangerous patterns."""
        validator = CodeValidator(security_level="high")
        code = "x = eval(user_input)"
        result = validator.validate(code)
        security_issues = [i for i in result.issues if i.category == "security"]
        assert len(security_issues) > 0

    def test_validation_scores(self):
        """Test validation scores calculation."""
        # Use simple clean code without security issues
        code = "def add(a, b):\n    return a + b"
        validator = CodeValidator(enable_security_checking=False)
        result = validator.validate(code)
        assert 0.0 <= result.syntax_score <= 1.0
        assert 0.0 <= result.security_score <= 1.0
        assert 0.0 <= result.overall_score <= 1.0


class TestQuickValidator:
    """Tests for quick validation."""

    def test_is_syntactically_valid(self):
        """Test quick syntax check."""
        assert QuickValidator.is_syntactically_valid("def foo(): pass")
        assert not QuickValidator.is_syntactically_valid("def broken(")

    def test_has_dangerous_calls(self):
        """Test quick dangerous call check."""
        assert QuickValidator.has_dangerous_calls("eval(x)")
        assert QuickValidator.has_dangerous_calls("exec('code')")
        assert not QuickValidator.has_dangerous_calls("print('safe')")

    def test_get_functions(self, sample_code):
        """Test extracting function names."""
        functions = QuickValidator.get_functions(sample_code)
        assert "greet" in functions
        assert "add" in functions

    def test_get_classes(self, sample_code):
        """Test extracting class names."""
        classes = QuickValidator.get_classes(sample_code)
        assert "Calculator" in classes


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_add_issue(self):
        """Test adding validation issues."""
        result = ValidationResult(valid=True)
        result.add_issue(ValidationIssue(
            severity="error",
            category="syntax",
            message="Syntax error",
        ))
        assert not result.valid
        assert not result.syntax_valid
        assert result.error_count == 1

    def test_calculate_scores(self):
        """Test score calculation."""
        result = ValidationResult(valid=True)
        result.add_issue(ValidationIssue(
            severity="warning",
            category="security",
            message="Warning",
        ))
        result.calculate_scores()
        assert result.overall_score < 1.0


# ============================================================================
# Rollback Tests
# ============================================================================


class TestRollbackManager:
    """Tests for rollback management."""

    def test_create_snapshot(self, sample_code):
        """Test creating a snapshot."""
        manager = RollbackManager()
        snapshot = manager.create_snapshot(
            code=sample_code,
            description="Initial version",
        )
        assert snapshot.code == sample_code
        assert snapshot.is_current
        assert manager.current == snapshot

    def test_set_baseline(self, sample_code):
        """Test setting baseline."""
        manager = RollbackManager()
        snapshot = manager.set_baseline(sample_code)
        assert snapshot.is_baseline
        assert manager.baseline == snapshot

    def test_rollback_steps(self, sample_code):
        """Test rollback by steps."""
        manager = RollbackManager()

        # Create versions
        manager.create_snapshot(sample_code, description="v1")
        manager.create_snapshot(sample_code + "\n# v2", description="v2")
        manager.create_snapshot(sample_code + "\n# v3", description="v3")

        assert manager.current.version == "v3"

        # Rollback 1 step
        result = manager.rollback(steps=1)
        assert result.success
        assert manager.current.version == "v2"

    def test_rollback_to_version(self, sample_code):
        """Test rollback to specific version."""
        manager = RollbackManager()

        manager.create_snapshot(sample_code, description="v1")
        manager.create_snapshot(sample_code + "\n# v2", description="v2")
        manager.create_snapshot(sample_code + "\n# v3", description="v3")

        result = manager.rollback_to_version("v1")
        assert result.success
        assert manager.current.version == "v1"

    def test_rollback_to_baseline(self, sample_code):
        """Test rollback to baseline."""
        manager = RollbackManager()

        manager.set_baseline(sample_code, description="baseline")
        manager.create_snapshot(sample_code + "\n# v2", description="v2")

        result = manager.rollback_to_baseline()
        assert result.success
        assert manager.current.is_baseline

    def test_redo(self, sample_code):
        """Test redo after rollback."""
        manager = RollbackManager()

        manager.create_snapshot(sample_code, description="v1")
        manager.create_snapshot(sample_code + "\n# v2", description="v2")

        manager.rollback(steps=1)
        assert manager.current.version == "v1"

        result = manager.redo(steps=1)
        assert result.success
        assert manager.current.version == "v2"

    def test_list_versions(self, sample_code):
        """Test listing versions."""
        manager = RollbackManager()

        manager.create_snapshot(sample_code, description="v1")
        manager.create_snapshot(sample_code, description="v2")

        versions = manager.list_versions()
        assert len(versions) == 2
        assert versions[0]["version"] == "v1"
        assert versions[1]["version"] == "v2"

    def test_compare_versions(self, sample_code):
        """Test comparing versions."""
        manager = RollbackManager()

        manager.create_snapshot(sample_code, description="v1")
        manager.create_snapshot(sample_code + "\n# modified", description="v2")

        comparison = manager.compare_versions("v1", "v2")
        assert comparison["version1"] == "v1"
        assert comparison["version2"] == "v2"
        assert comparison["total_change"] > 0


class TestCodeSnapshot:
    """Tests for CodeSnapshot."""

    def test_snapshot_creation(self, sample_code):
        """Test snapshot creation."""
        snapshot = CodeSnapshot(code=sample_code, description="test")
        assert snapshot.code == sample_code
        assert snapshot.code_hash != ""

    def test_snapshot_hash(self, sample_code):
        """Test code hash generation."""
        snapshot1 = CodeSnapshot(code=sample_code)
        snapshot2 = CodeSnapshot(code=sample_code)
        assert snapshot1.code_hash == snapshot2.code_hash

        snapshot3 = CodeSnapshot(code=sample_code + "\n# different")
        assert snapshot1.code_hash != snapshot3.code_hash


# ============================================================================
# Orchestrator Tests
# ============================================================================


class TestEvolutionOrchestrator:
    """Tests for evolution orchestration."""

    def test_create_orchestrator(self):
        """Test orchestrator creation."""
        orchestrator = EvolutionOrchestrator()
        assert orchestrator.config is not None
        assert orchestrator.rollback_manager is not None

    def test_create_with_config(self):
        """Test orchestrator with custom config."""
        config = EvolutionConfig(
            auto_deploy=True,
            min_improvement=0.1,
        )
        orchestrator = EvolutionOrchestrator(config=config)
        assert orchestrator.config.auto_deploy is True
        assert orchestrator.config.min_improvement == 0.1

    @pytest.mark.asyncio
    async def test_evolve_basic(self, sample_code):
        """Test basic evolution."""
        config = EvolutionConfig(
            sandbox_enabled=False,  # Disable for faster testing
            auto_deploy=False,
        )
        orchestrator = EvolutionOrchestrator(config=config)

        attempt = await orchestrator.evolve(
            code=sample_code,
            agent_id="test_agent",
        )

        assert attempt is not None
        assert attempt.agent_id == "test_agent"
        assert attempt.status in EvolutionStatus

    def test_get_statistics(self):
        """Test getting statistics."""
        orchestrator = EvolutionOrchestrator()
        stats = orchestrator.get_statistics()
        assert "total_attempts" in stats
        assert "approval_rate" in stats

    def test_approve_manually(self, sample_code):
        """Test manual approval."""
        orchestrator = EvolutionOrchestrator()

        # Create an attempt manually
        attempt = EvolutionAttempt(
            agent_id="test",
            original_code=sample_code,
            status=EvolutionStatus.VALIDATING,
        )
        orchestrator.attempts.append(attempt)

        success = orchestrator.approve_manually(attempt.id, "test_user")
        assert success
        assert attempt.approved
        assert attempt.status == EvolutionStatus.APPROVED

    def test_reject_manually(self, sample_code):
        """Test manual rejection."""
        orchestrator = EvolutionOrchestrator()

        attempt = EvolutionAttempt(
            agent_id="test",
            original_code=sample_code,
            status=EvolutionStatus.VALIDATING,
        )
        orchestrator.attempts.append(attempt)

        success = orchestrator.reject_manually(attempt.id, "Too risky", "test_user")
        assert success
        assert not attempt.approved
        assert attempt.status == EvolutionStatus.REJECTED
        assert attempt.rejection_reason == "Too risky"


class TestEvolutionConfig:
    """Tests for EvolutionConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = EvolutionConfig()
        assert "llm_guided" in config.strategies
        assert config.min_validation_score == 0.8
        assert config.require_syntax_valid is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = EvolutionConfig(
            strategies=["random"],
            min_improvement=0.2,
            auto_deploy=True,
        )
        assert config.strategies == ["random"]
        assert config.min_improvement == 0.2
        assert config.auto_deploy is True


class TestEvolutionAttempt:
    """Tests for EvolutionAttempt."""

    def test_attempt_creation(self, sample_code):
        """Test attempt creation."""
        attempt = EvolutionAttempt(
            agent_id="test",
            original_code=sample_code,
        )
        assert attempt.id is not None
        assert attempt.status == EvolutionStatus.PROPOSED
        assert attempt.original_code == sample_code

    def test_attempt_with_proposal(self, sample_code):
        """Test attempt with mutation proposal."""
        mutation = Mutation(
            mutation_type="add",
            target="function",
            description="Test mutation",
        )
        proposal = MutationProposal(
            strategy="test",
            mutations=[mutation],
            rationale="Test",
        )

        attempt = EvolutionAttempt(
            agent_id="test",
            original_code=sample_code,
            proposal=proposal,
        )
        assert attempt.proposal == proposal


# ============================================================================
# Integration Tests
# ============================================================================


class TestEvolutionIntegration:
    """Integration tests for the evolution module."""

    @pytest.mark.asyncio
    async def test_full_evolution_cycle(self, sample_code):
        """Test a complete evolution cycle."""
        config = EvolutionConfig(
            strategies=["random"],
            sandbox_enabled=False,
            auto_deploy=False,
            require_human_approval=False,
            min_improvement=-1.0,  # Accept any improvement
        )
        orchestrator = EvolutionOrchestrator(config=config)

        # Run evolution
        attempt = await orchestrator.evolve(
            code=sample_code,
            agent_id="integration_test",
        )

        # Check attempt recorded
        assert len(orchestrator.attempts) == 1
        assert attempt in orchestrator.attempts

    def test_mutation_and_validation(self, sample_code):
        """Test mutation followed by validation."""
        # Generate mutation
        strategy = RandomMutationStrategy(seed=42)
        proposals = strategy.propose_mutations(sample_code)

        if proposals:
            # Apply mutation
            mutator = CodeMutator()
            result = mutator.mutate(sample_code, proposals[0].mutations)

            if result.syntax_valid:
                # Validate result
                validator = CodeValidator(enable_security_checking=False)
                validation = validator.validate(result.mutated_code)

                # Should produce valid Python (or fail gracefully)
                assert validation.syntax_valid or not result.syntax_valid

    def test_rollback_after_evolution(self, sample_code):
        """Test rollback capability after evolution."""
        manager = RollbackManager()

        # Save baseline
        manager.set_baseline(sample_code, "Original")

        # Apply mutation
        mutator = CodeMutator()
        mutation = Mutation(
            mutation_type="add",
            target="greet",
            description="Add logging",
            mutated_code='    print("log")',
            start_line=2,
        )
        result = mutator.mutate(sample_code, [mutation])

        if result.syntax_valid:
            manager.create_snapshot(result.mutated_code, "Mutated")

            # Verify we can rollback
            rollback = manager.rollback_to_baseline()
            assert rollback.success
            assert manager.current.code == sample_code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
