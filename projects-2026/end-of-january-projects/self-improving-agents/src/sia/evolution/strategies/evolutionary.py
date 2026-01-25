"""
Evolutionary Mutation Strategy.

Applies genetic algorithm principles to code evolution.
"""

from __future__ import annotations

import ast
import copy
import random
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sia.evolution.mutator import Mutation, MutationResult
from sia.evolution.strategies.base import MutationProposal, MutationStrategy


@dataclass
class Individual:
    """An individual in the evolutionary population."""

    id: UUID = field(default_factory=uuid4)
    code: str = ""
    fitness: float = 0.0
    generation: int = 0
    parent_ids: list[UUID] = field(default_factory=list)
    mutations: list[Mutation] = field(default_factory=list)


@dataclass
class Population:
    """A population of code individuals."""

    individuals: list[Individual] = field(default_factory=list)
    generation: int = 0
    best_fitness: float = 0.0
    avg_fitness: float = 0.0


class EvolutionaryStrategy(MutationStrategy):
    """
    Applies genetic algorithm principles to evolve code.

    Uses selection, crossover, and mutation operators to
    explore the code improvement space.
    """

    def __init__(
        self,
        population_size: int = 10,
        generations: int = 5,
        mutation_rate: float = 0.2,
        crossover_rate: float = 0.7,
        elite_count: int = 2,
        tournament_size: int = 3,
        seed: int | None = None,
    ):
        """
        Initialize evolutionary strategy.

        Args:
            population_size: Size of population
            generations: Number of generations
            mutation_rate: Probability of mutation
            crossover_rate: Probability of crossover
            elite_count: Number of elite individuals to preserve
            tournament_size: Size of tournament selection
            seed: Random seed
        """
        super().__init__(name="evolutionary")
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_count = elite_count
        self.tournament_size = tournament_size

        if seed is not None:
            random.seed(seed)

        self.population: Population | None = None

    def propose_mutations(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> list[MutationProposal]:
        """
        Generate mutation proposals using evolutionary approach.

        Args:
            code: Python code to evolve
            context: Fitness function and constraints

        Returns:
            Best mutations from evolution
        """
        # Initialize population with variations
        self.population = self._initialize_population(code)

        # Evolve for specified generations
        fitness_fn = context.get("fitness_fn") if context else None

        if fitness_fn:
            for _ in range(self.generations):
                self._evaluate_population(fitness_fn)
                self._evolve_generation()

        # Return proposals from best individuals
        proposals = []
        if self.population:
            sorted_individuals = sorted(
                self.population.individuals,
                key=lambda x: x.fitness,
                reverse=True,
            )

            for individual in sorted_individuals[:5]:
                if individual.mutations:
                    proposal = MutationProposal(
                        strategy=self.name,
                        mutations=individual.mutations,
                        rationale=f"Evolved solution (generation {individual.generation})",
                        expected_improvement=f"Fitness: {individual.fitness:.3f}",
                        confidence=min(individual.fitness, 0.9),
                        risk_level="medium",
                    )
                    proposals.append(proposal)

        return proposals

    def _initialize_population(self, code: str) -> Population:
        """Initialize population with code variants."""
        population = Population()

        # First individual is the original
        original = Individual(code=code, generation=0)
        population.individuals.append(original)

        # Generate variants
        for _ in range(self.population_size - 1):
            variant = self._create_variant(code)
            population.individuals.append(variant)

        return population

    def _create_variant(self, code: str) -> Individual:
        """Create a variant of the code."""
        mutations = self._generate_random_mutations(code)
        mutated_code = self._apply_mutations(code, mutations)

        return Individual(
            code=mutated_code,
            mutations=mutations,
            generation=0,
        )

    def _generate_random_mutations(self, code: str) -> list[Mutation]:
        """Generate random mutations for code."""
        mutations = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        # Collect mutation opportunities
        opportunities = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                opportunities.append(("function", node))
            elif isinstance(node, ast.Assign):
                opportunities.append(("assignment", node))
            elif isinstance(node, ast.If):
                opportunities.append(("conditional", node))

        # Apply mutations based on rate
        for opp_type, node in opportunities:
            if random.random() < self.mutation_rate:
                mutation = self._mutate_node(opp_type, node, code)
                if mutation:
                    mutations.append(mutation)

        return mutations

    def _mutate_node(
        self,
        node_type: str,
        node: ast.AST,
        code: str,
    ) -> Mutation | None:
        """Apply mutation to a specific node."""
        lines = code.split("\n")

        if node_type == "function" and isinstance(node, ast.FunctionDef):
            mutation_options = [
                "add_logging",
                "add_docstring",
                "add_validation",
            ]
            choice = random.choice(mutation_options)

            if choice == "add_logging":
                return Mutation(
                    mutation_type="add",
                    target=node.name,
                    description=f"Add logging to {node.name}",
                    mutated_code=f'    print(f"Entering {node.name}")',
                    start_line=node.lineno,
                    confidence=0.3,
                    risk_level="low",
                )

        elif node_type == "assignment" and isinstance(node, ast.Assign):
            if node.targets and isinstance(node.targets[0], ast.Name):
                var = node.targets[0].id
                return Mutation(
                    mutation_type="add",
                    target=var,
                    description=f"Add validation for {var}",
                    mutated_code=f"    assert {var} is not None",
                    start_line=node.lineno,
                    confidence=0.2,
                    risk_level="low",
                )

        return None

    def _apply_mutations(self, code: str, mutations: list[Mutation]) -> str:
        """Apply mutations to code."""
        result = code

        for mutation in mutations:
            if mutation.mutation_type == "add" and mutation.start_line:
                lines = result.split("\n")
                lines.insert(mutation.start_line, mutation.mutated_code)
                result = "\n".join(lines)
            elif mutation.mutation_type == "replace":
                result = result.replace(
                    mutation.original_code,
                    mutation.mutated_code,
                    1,
                )

        return result

    def _evaluate_population(self, fitness_fn: Any) -> None:
        """Evaluate fitness of all individuals."""
        if not self.population:
            return

        for individual in self.population.individuals:
            try:
                individual.fitness = fitness_fn(individual.code)
            except Exception:
                individual.fitness = 0.0

        # Update population stats
        fitnesses = [i.fitness for i in self.population.individuals]
        self.population.best_fitness = max(fitnesses)
        self.population.avg_fitness = sum(fitnesses) / len(fitnesses)

    def _evolve_generation(self) -> None:
        """Evolve to next generation."""
        if not self.population:
            return

        new_individuals = []

        # Elitism - keep best individuals
        sorted_pop = sorted(
            self.population.individuals,
            key=lambda x: x.fitness,
            reverse=True,
        )
        elites = sorted_pop[: self.elite_count]
        for elite in elites:
            new_elite = Individual(
                code=elite.code,
                fitness=elite.fitness,
                generation=self.population.generation + 1,
                parent_ids=[elite.id],
                mutations=elite.mutations.copy(),
            )
            new_individuals.append(new_elite)

        # Generate rest of population
        while len(new_individuals) < self.population_size:
            # Selection
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()

            # Crossover
            if random.random() < self.crossover_rate:
                child_code = self._crossover(parent1.code, parent2.code)
            else:
                child_code = parent1.code if random.random() < 0.5 else parent2.code

            # Mutation
            mutations = []
            if random.random() < self.mutation_rate:
                mutations = self._generate_random_mutations(child_code)
                child_code = self._apply_mutations(child_code, mutations)

            child = Individual(
                code=child_code,
                generation=self.population.generation + 1,
                parent_ids=[parent1.id, parent2.id],
                mutations=mutations,
            )
            new_individuals.append(child)

        self.population.individuals = new_individuals
        self.population.generation += 1

    def _tournament_selection(self) -> Individual:
        """Select individual using tournament selection."""
        if not self.population:
            raise RuntimeError("No population")

        tournament = random.sample(
            self.population.individuals,
            min(self.tournament_size, len(self.population.individuals)),
        )
        return max(tournament, key=lambda x: x.fitness)

    def _crossover(self, code1: str, code2: str) -> str:
        """Perform crossover between two code versions."""
        try:
            tree1 = ast.parse(code1)
            tree2 = ast.parse(code2)
        except SyntaxError:
            return code1

        # Simple function-level crossover
        funcs1 = {
            n.name: n for n in ast.walk(tree1) if isinstance(n, ast.FunctionDef)
        }
        funcs2 = {
            n.name: n for n in ast.walk(tree2) if isinstance(n, ast.FunctionDef)
        }

        # Find common functions
        common = set(funcs1.keys()) & set(funcs2.keys())

        if not common:
            return code1

        # Randomly swap one function
        func_to_swap = random.choice(list(common))

        lines1 = code1.split("\n")
        lines2 = code2.split("\n")

        # Get function from code2
        func2 = funcs2[func_to_swap]
        func2_lines = lines2[func2.lineno - 1 : func2.end_lineno]

        # Replace in code1
        func1 = funcs1[func_to_swap]
        new_lines = (
            lines1[: func1.lineno - 1]
            + func2_lines
            + lines1[func1.end_lineno:]
        )

        return "\n".join(new_lines)

    def evaluate_mutation(
        self,
        original_code: str,
        mutated_code: str,
        test_results: dict[str, Any] | None = None,
    ) -> float:
        """Evaluate mutation using fitness metrics."""
        score = 0.5

        # Syntax check
        try:
            ast.parse(mutated_code)
            score += 0.2
        except SyntaxError:
            return 0.0

        # Test results
        if test_results:
            if test_results.get("passed", False):
                score += 0.2
            tests_passed = test_results.get("tests_passed", 0)
            tests_total = test_results.get("tests_run", 1)
            score += 0.1 * (tests_passed / max(tests_total, 1))

        return min(score, 1.0)
