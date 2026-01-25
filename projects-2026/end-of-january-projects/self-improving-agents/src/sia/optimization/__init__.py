"""
DSPy Optimization Module.

Provides prompt optimization using DSPy's MIPROv2 and SIMBA algorithms.
"""

from sia.optimization.data_collector import (
    DatasetSplit,
    LangfuseDataExporter,
    SyntheticDataGenerator,
    TrainingDataCollector,
    TrainingExample,
)
from sia.optimization.dspy_integration import (
    DSPyTracer,
    configure_dspy,
    get_default_lm,
    get_tracer,
)
from sia.optimization.metrics import (
    METRIC_REGISTRY,
    LLMJudge,
    MetricResult,
    code_correctness,
    code_executes,
    composite_metric,
    decision_quality,
    decomposition_quality,
    error_analysis_quality,
    get_metric,
    list_metrics,
    research_relevance,
    review_thoroughness,
    skill_extraction_quality,
    synthesis_coherence,
)
from sia.optimization.miprov2_optimizer import (
    BatchMIPROv2Optimizer,
    IncrementalMIPROv2Optimizer,
    MIPROv2Config,
    MIPROv2Optimizer,
    OptimizationResult,
)
from sia.optimization.modules import (
    MODULE_REGISTRY,
    Coder,
    DecisionMaker,
    Decomposer,
    ErrorAnalyzer,
    Researcher,
    Reviewer,
    SkillExtractor,
    Synthesizer,
    create_module,
    get_module,
    list_modules,
)
from sia.optimization.runner import (
    OptimizationRun,
    OptimizationRunner,
    ScheduledOptimizer,
)
from sia.optimization.signatures import (
    SIGNATURE_REGISTRY,
    CodeGeneration,
    CodeImprovement,
    CodeReview,
    ContentSynthesis,
    DecisionMaking,
    ErrorAnalysis,
    ResearchQuery,
    ResearchSynthesis,
    SkillExtraction,
    SubtaskRefinement,
    TaskDecomposition,
    get_signature,
    list_signatures,
)
from sia.optimization.simba_optimizer import (
    AdaptiveSIMBAOptimizer,
    SIMBAConfig,
    SIMBAOptimizer,
    SIMBAResult,
)

__all__ = [
    # DSPy Integration
    "configure_dspy",
    "get_default_lm",
    "DSPyTracer",
    "get_tracer",
    # Signatures
    "TaskDecomposition",
    "SubtaskRefinement",
    "CodeGeneration",
    "CodeImprovement",
    "ResearchQuery",
    "ResearchSynthesis",
    "CodeReview",
    "ContentSynthesis",
    "SkillExtraction",
    "DecisionMaking",
    "ErrorAnalysis",
    "SIGNATURE_REGISTRY",
    "get_signature",
    "list_signatures",
    # Modules
    "Decomposer",
    "Coder",
    "Researcher",
    "Reviewer",
    "Synthesizer",
    "SkillExtractor",
    "DecisionMaker",
    "ErrorAnalyzer",
    "MODULE_REGISTRY",
    "get_module",
    "create_module",
    "list_modules",
    # Metrics
    "MetricResult",
    "decomposition_quality",
    "code_correctness",
    "code_executes",
    "research_relevance",
    "review_thoroughness",
    "synthesis_coherence",
    "skill_extraction_quality",
    "decision_quality",
    "error_analysis_quality",
    "composite_metric",
    "LLMJudge",
    "METRIC_REGISTRY",
    "get_metric",
    "list_metrics",
    # Data Collection
    "TrainingExample",
    "DatasetSplit",
    "TrainingDataCollector",
    "SyntheticDataGenerator",
    "LangfuseDataExporter",
    # MIPROv2
    "MIPROv2Config",
    "OptimizationResult",
    "MIPROv2Optimizer",
    "BatchMIPROv2Optimizer",
    "IncrementalMIPROv2Optimizer",
    # SIMBA
    "SIMBAConfig",
    "SIMBAResult",
    "SIMBAOptimizer",
    "AdaptiveSIMBAOptimizer",
    # Runner
    "OptimizationRun",
    "OptimizationRunner",
    "ScheduledOptimizer",
]
