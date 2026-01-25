"""Tests for DSPy Optimization System."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Import optimization components
from sia.optimization import (
    # DSPy Integration
    DSPyTracer,
    # Metrics
    METRIC_REGISTRY,
    MetricResult,
    code_correctness,
    code_executes,
    composite_metric,
    decomposition_quality,
    decision_quality,
    get_metric,
    list_metrics,
    research_relevance,
    review_thoroughness,
    synthesis_coherence,
    # Modules
    MODULE_REGISTRY,
    Coder,
    DecisionMaker,
    Decomposer,
    Researcher,
    Reviewer,
    Synthesizer,
    create_module,
    get_module,
    list_modules,
    # Signatures
    SIGNATURE_REGISTRY,
    CodeGeneration,
    CodeReview,
    DecisionMaking,
    ResearchQuery,
    TaskDecomposition,
    get_signature,
    list_signatures,
    # Data Collection
    DatasetSplit,
    TrainingExample,
    # MIPROv2
    MIPROv2Config,
    OptimizationResult,
    # SIMBA
    SIMBAConfig,
    SIMBAResult,
    # Runner
    OptimizationRun,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_dspy_example():
    """Create a mock DSPy Example."""
    example = MagicMock()
    example.task = "Build a REST API"
    example.topic = "machine learning"
    example.options = ["Option A", "Option B"]
    example.inputs.return_value = ["task"]
    example.items.return_value = [("task", "Build a REST API")]
    return example


@pytest.fixture
def mock_dspy_prediction():
    """Create a mock DSPy Prediction."""
    prediction = MagicMock()
    prediction.subtasks = ["Design endpoints", "Implement handlers", "Add tests"]
    prediction.dependencies = [(1, 0), (2, 1)]
    prediction.estimated_complexity = "medium"
    prediction.code = "def hello(): pass"
    prediction.queries = ["search query 1", "search query 2"]
    prediction.sources_to_check = ["docs.example.com"]
    prediction.key_concepts = ["concept1"]
    prediction.issues = ["Bug found"]
    prediction.suggestions = ["Fix the bug"]
    prediction.security_concerns = []
    prediction.overall_quality = "good"
    prediction.synthesis = "This is a synthesized summary of the content."
    prediction.sources_used = [0, 1]
    prediction.decision = "Option A"
    prediction.reasoning = "Option A is better because it provides more flexibility."
    prediction.confidence = 0.85
    return prediction


# ============================================================================
# DSPy Tracer Tests
# ============================================================================


class TestDSPyTracer:
    """Tests for DSPyTracer."""

    def test_init(self):
        """Test tracer initialization."""
        tracer = DSPyTracer()
        assert tracer.traces == []

    def test_record(self):
        """Test recording a trace."""
        tracer = DSPyTracer()
        tracer.record(
            signature="TaskDecomposition",
            inputs={"task": "Build API"},
            outputs={"subtasks": ["a", "b"]},
            latency_ms=100.5,
            tokens=50,
        )
        assert len(tracer.traces) == 1
        assert tracer.traces[0]["signature"] == "TaskDecomposition"
        assert tracer.traces[0]["latency_ms"] == 100.5

    def test_clear(self):
        """Test clearing traces."""
        tracer = DSPyTracer()
        tracer.record("sig", {}, {}, 100)
        tracer.record("sig", {}, {}, 200)
        assert len(tracer.traces) == 2

        tracer.clear()
        assert len(tracer.traces) == 0

    def test_get_stats_empty(self):
        """Test stats with no traces."""
        tracer = DSPyTracer()
        stats = tracer.get_stats()
        assert stats["count"] == 0

    def test_get_stats_with_traces(self):
        """Test stats calculation."""
        tracer = DSPyTracer()
        tracer.record("sig1", {}, {}, 100, tokens=10)
        tracer.record("sig2", {}, {}, 200, tokens=20)
        tracer.record("sig3", {}, {}, 300, tokens=30)

        stats = tracer.get_stats()
        assert stats["count"] == 3
        assert stats["avg_latency_ms"] == 200.0
        assert stats["min_latency_ms"] == 100
        assert stats["max_latency_ms"] == 300
        assert stats["total_tokens"] == 60


# ============================================================================
# Signature Tests
# ============================================================================


class TestSignatures:
    """Tests for DSPy Signatures."""

    def test_signature_registry(self):
        """Test signature registry has expected entries."""
        assert "task_decomposition" in SIGNATURE_REGISTRY
        assert "code_generation" in SIGNATURE_REGISTRY
        assert "research_query" in SIGNATURE_REGISTRY
        assert "code_review" in SIGNATURE_REGISTRY
        assert len(SIGNATURE_REGISTRY) >= 11

    def test_get_signature(self):
        """Test getting signature by name."""
        sig = get_signature("task_decomposition")
        assert sig == TaskDecomposition

    def test_get_signature_invalid(self):
        """Test getting invalid signature."""
        with pytest.raises(ValueError, match="Unknown signature"):
            get_signature("invalid_signature")

    def test_list_signatures(self):
        """Test listing all signatures."""
        sigs = list_signatures()
        assert isinstance(sigs, list)
        assert "task_decomposition" in sigs
        assert "code_generation" in sigs


# ============================================================================
# Module Tests
# ============================================================================


class TestModules:
    """Tests for DSPy Modules."""

    def test_module_registry(self):
        """Test module registry has expected entries."""
        assert "decomposer" in MODULE_REGISTRY
        assert "coder" in MODULE_REGISTRY
        assert "researcher" in MODULE_REGISTRY
        assert "reviewer" in MODULE_REGISTRY
        assert len(MODULE_REGISTRY) >= 8

    def test_get_module(self):
        """Test getting module class by name."""
        module_class = get_module("decomposer")
        assert module_class == Decomposer

    def test_get_module_invalid(self):
        """Test getting invalid module."""
        with pytest.raises(ValueError, match="Unknown module"):
            get_module("invalid_module")

    def test_create_module(self):
        """Test creating module instance."""
        module = create_module("decomposer")
        assert isinstance(module, Decomposer)

    def test_list_modules(self):
        """Test listing all modules."""
        modules = list_modules()
        assert isinstance(modules, list)
        assert "decomposer" in modules
        assert "coder" in modules

    def test_decomposer_has_predictors(self):
        """Test Decomposer has required predictors."""
        module = Decomposer()
        assert hasattr(module, "decompose")
        assert hasattr(module, "refine")

    def test_coder_init_with_review(self):
        """Test Coder initialization with review."""
        module = Coder(with_review=True)
        assert module.review is not None

    def test_coder_init_without_review(self):
        """Test Coder initialization without review."""
        module = Coder(with_review=False)
        assert module.review is None


# ============================================================================
# Metrics Tests
# ============================================================================


class TestMetrics:
    """Tests for evaluation metrics."""

    def test_metric_registry(self):
        """Test metric registry has expected entries."""
        assert "decomposition_quality" in METRIC_REGISTRY
        assert "code_correctness" in METRIC_REGISTRY
        assert "research_relevance" in METRIC_REGISTRY
        assert len(METRIC_REGISTRY) >= 9

    def test_get_metric(self):
        """Test getting metric by name."""
        metric = get_metric("decomposition_quality")
        assert metric == decomposition_quality

    def test_get_metric_invalid(self):
        """Test getting invalid metric."""
        with pytest.raises(ValueError, match="Unknown metric"):
            get_metric("invalid_metric")

    def test_list_metrics(self):
        """Test listing all metrics."""
        metrics = list_metrics()
        assert isinstance(metrics, list)
        assert "decomposition_quality" in metrics

    def test_decomposition_quality(self, mock_dspy_example, mock_dspy_prediction):
        """Test decomposition quality metric."""
        score = decomposition_quality(mock_dspy_example, mock_dspy_prediction)
        assert 0 <= score <= 1
        assert score > 0.5  # Should be decent with valid subtasks

    def test_decomposition_quality_empty(self, mock_dspy_example):
        """Test decomposition quality with empty subtasks."""
        prediction = MagicMock()
        prediction.subtasks = []
        prediction.dependencies = []
        prediction.estimated_complexity = None

        score = decomposition_quality(mock_dspy_example, prediction)
        assert score < 0.5

    def test_code_correctness_valid(self, mock_dspy_example):
        """Test code correctness with valid code."""
        prediction = MagicMock()
        prediction.code = '''
def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"
'''
        score = code_correctness(mock_dspy_example, prediction)
        assert score == 1.0  # Should be perfect (syntax, function, docstring, type hints)

    def test_code_correctness_invalid_syntax(self, mock_dspy_example):
        """Test code correctness with invalid syntax."""
        prediction = MagicMock()
        prediction.code = "def broken( syntax"

        score = code_correctness(mock_dspy_example, prediction)
        assert score == 0.0

    def test_code_correctness_no_code(self, mock_dspy_example):
        """Test code correctness with no code."""
        prediction = MagicMock()
        prediction.code = ""

        score = code_correctness(mock_dspy_example, prediction)
        assert score == 0.0

    def test_code_executes_valid(self, mock_dspy_example):
        """Test code executes with valid code."""
        prediction = MagicMock()
        prediction.code = "x = 1 + 1"

        score = code_executes(mock_dspy_example, prediction)
        assert score == 1.0

    def test_code_executes_invalid(self, mock_dspy_example):
        """Test code executes with invalid code."""
        prediction = MagicMock()
        prediction.code = "def broken("

        score = code_executes(mock_dspy_example, prediction)
        assert score == 0.0

    def test_research_relevance(self, mock_dspy_example, mock_dspy_prediction):
        """Test research relevance metric."""
        score = research_relevance(mock_dspy_example, mock_dspy_prediction)
        assert 0 <= score <= 1

    def test_review_thoroughness(self, mock_dspy_example, mock_dspy_prediction):
        """Test review thoroughness metric."""
        score = review_thoroughness(mock_dspy_example, mock_dspy_prediction)
        assert 0 <= score <= 1
        assert score >= 0.75  # Should be high with issues, suggestions, quality, security

    def test_synthesis_coherence(self, mock_dspy_example, mock_dspy_prediction):
        """Test synthesis coherence metric."""
        score = synthesis_coherence(mock_dspy_example, mock_dspy_prediction)
        assert 0 <= score <= 1

    def test_decision_quality(self, mock_dspy_example, mock_dspy_prediction):
        """Test decision quality metric."""
        score = decision_quality(mock_dspy_example, mock_dspy_prediction)
        assert 0 <= score <= 1
        assert score >= 0.75  # Should be high with decision, reasoning, confidence

    def test_composite_metric(self, mock_dspy_example, mock_dspy_prediction):
        """Test composite metric creation."""
        combined = composite_metric([
            (decomposition_quality, 0.5),
            (code_correctness, 0.5),
        ])

        score = combined(mock_dspy_example, mock_dspy_prediction)
        assert 0 <= score <= 1


# ============================================================================
# Training Data Tests
# ============================================================================


class TestTrainingData:
    """Tests for training data collection."""

    def test_training_example_creation(self):
        """Test creating a training example."""
        example = TrainingExample(
            inputs={"task": "Build API"},
            outputs={"subtasks": ["a", "b", "c"]},
            metadata={"source": "test"},
        )
        assert example.inputs["task"] == "Build API"
        assert len(example.outputs["subtasks"]) == 3

    def test_training_example_to_dspy(self):
        """Test converting to DSPy Example."""
        example = TrainingExample(
            inputs={"task": "Build API"},
            outputs={"subtasks": ["a", "b"]},
        )
        dspy_example = example.to_dspy_example()
        # Check it has the data
        assert "task" in dict(dspy_example)
        assert "subtasks" in dict(dspy_example)

    def test_dataset_split(self):
        """Test dataset split creation."""
        examples = [
            TrainingExample(inputs={"x": i}, outputs={"y": i * 2})
            for i in range(10)
        ]

        split = DatasetSplit(
            train=examples[:7],
            validation=examples[7:8],
            test=examples[8:],
        )

        assert len(split.train) == 7
        assert len(split.validation) == 1
        assert len(split.test) == 2


# ============================================================================
# MIPROv2 Tests
# ============================================================================


class TestMIPROv2:
    """Tests for MIPROv2 optimizer."""

    def test_config_defaults(self):
        """Test config default values."""
        config = MIPROv2Config()
        assert config.num_candidates == 10
        assert config.num_trials == 20
        assert config.min_improvement == 0.05

    def test_config_custom(self):
        """Test config with custom values."""
        config = MIPROv2Config(
            num_candidates=5,
            num_trials=10,
            min_improvement=0.1,
        )
        assert config.num_candidates == 5
        assert config.num_trials == 10
        assert config.min_improvement == 0.1

    def test_optimization_result(self):
        """Test optimization result creation."""
        result = OptimizationResult(
            module_name="Decomposer",
            baseline_score=0.6,
            optimized_score=0.75,
            improvement=0.15,
            improvement_pct=0.25,
        )
        assert result.module_name == "Decomposer"
        assert result.improvement == 0.15

    def test_optimization_result_to_dict(self):
        """Test result serialization."""
        result = OptimizationResult(
            module_name="Coder",
            baseline_score=0.5,
            optimized_score=0.6,
            improvement=0.1,
        )
        data = result.to_dict()
        assert data["module_name"] == "Coder"
        assert data["baseline_score"] == 0.5
        assert "id" in data


# ============================================================================
# SIMBA Tests
# ============================================================================


class TestSIMBA:
    """Tests for SIMBA optimizer."""

    def test_config_defaults(self):
        """Test SIMBA config default values."""
        config = SIMBAConfig()
        assert config.num_iterations == 5
        assert config.batch_size == 16
        assert config.hard_case_ratio == 0.5
        assert config.patience == 2

    def test_config_custom(self):
        """Test SIMBA config with custom values."""
        config = SIMBAConfig(
            num_iterations=10,
            batch_size=32,
            hard_case_ratio=0.7,
        )
        assert config.num_iterations == 10
        assert config.batch_size == 32

    def test_simba_result(self):
        """Test SIMBA result creation."""
        result = SIMBAResult(
            module_name="Researcher",
            baseline_score=0.5,
            final_score=0.7,
            improvement=0.2,
            iteration_scores=[0.5, 0.55, 0.6, 0.65, 0.7],
        )
        assert result.module_name == "Researcher"
        assert result.final_score == 0.7
        assert len(result.iteration_scores) == 5

    def test_simba_result_to_dict(self):
        """Test SIMBA result serialization."""
        result = SIMBAResult(
            module_name="Reviewer",
            iteration_scores=[0.5, 0.6, 0.7],
        )
        data = result.to_dict()
        assert data["module_name"] == "Reviewer"
        assert "iteration_scores" in data


# ============================================================================
# Optimization Run Tests
# ============================================================================


class TestOptimizationRun:
    """Tests for OptimizationRun."""

    def test_run_creation(self):
        """Test run creation."""
        run = OptimizationRun(
            agent_name="test_agent",
            optimizer_type="miprov2",
        )
        assert run.agent_name == "test_agent"
        assert run.optimizer_type == "miprov2"
        assert run.status == "pending"

    def test_run_to_dict(self):
        """Test run serialization."""
        run = OptimizationRun(
            agent_name="my_agent",
            module_name="decomposer",
            optimizer_type="simba",
            training_examples=100,
        )
        data = run.to_dict()
        assert data["agent_name"] == "my_agent"
        assert data["optimizer_type"] == "simba"
        assert data["training_examples"] == 100

    def test_run_from_dict(self):
        """Test run deserialization."""
        data = {
            "id": str(uuid4()),
            "agent_name": "restored_agent",
            "module_name": "coder",
            "optimizer_type": "miprov2",
            "status": "completed",
            "baseline_score": 0.5,
            "optimized_score": 0.65,
            "improvement": 0.15,
            "improvement_pct": 0.3,
            "created_at": "2024-01-15T10:00:00",
        }
        run = OptimizationRun.from_dict(data)
        assert run.agent_name == "restored_agent"
        assert run.status == "completed"
        assert run.improvement == 0.15


# ============================================================================
# MetricResult Tests
# ============================================================================


class TestMetricResult:
    """Tests for MetricResult."""

    def test_creation(self):
        """Test result creation."""
        result = MetricResult(
            score=0.85,
            passed=True,
            details={"metric": "code_quality"},
            feedback="Code is well-structured",
        )
        assert result.score == 0.85
        assert result.passed is True
        assert result.feedback == "Code is well-structured"

    def test_creation_minimal(self):
        """Test minimal result creation."""
        result = MetricResult(
            score=0.5,
            passed=False,
            details={},
        )
        assert result.score == 0.5
        assert result.feedback is None
